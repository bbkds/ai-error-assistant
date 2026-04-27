# Architecture & Technical Reference

---

## System Overview

```
Browser
  └─> Nginx :80
        ├─> /api/*  →  FastAPI :8000
        │               ├─> PostgreSQL  (ORM via SQLAlchemy)
        │               ├─> Redis       (Celery broker + results)
        │               └─> Celery Worker
        │                     └─> ML Model (TF-IDF + LogReg)
        └─> /*      →  Streamlit :8501

Prometheus :9090  ←  scrapes /metrics from FastAPI
Grafana :3000     ←  reads Prometheus
```

---

## Network Isolation

```
frontend_net:  Nginx ↔ UI ↔ API ↔ Prometheus ↔ Grafana
backend_net:   API ↔ Redis ↔ Celery Worker ↔ PostgreSQL
```

UI and Nginx have **no route** to Redis or PostgreSQL — they only talk to the API.

---

## Request Flow

```
1. User submits error text in UI
2. POST /api/analyze → Pydantic validates → Celery task enqueued → 202 + task_id
3. UI polls GET /api/tasks/{id} every 2s (shows spinner)
4. Worker picks up task → loads ML model (lazy) → inference ~5ms
5. Worker saves result to PostgreSQL → pushes to Redis result backend
6. Poll returns status=success with full result
7. UI renders category, severity, confidence, recommendations + charts
```

---

## ML Model

**Algorithm:** TF-IDF + Logistic Regression
**Why:** No GPU needed, ~5ms inference, 5MB model file, interpretable, sufficient accuracy for structured error text.

**Pipeline:**
```python
TfidfVectorizer(ngram_range=(1,4), max_features=20_000, sublinear_tf=True, min_df=1)
LogisticRegression(C=10.0, max_iter=2000, class_weight="balanced", solver="lbfgs")
```

**Dataset:** 450 rows — ~60% natural language descriptions, ~40% actual exception messages. Stratified 80/20 train/test split.

**Categories & Severity:**

| Category | Severity |
|----------|----------|
| `memory` | critical |
| `null_pointer` | high |
| `database` | high |
| `authentication` | high |
| `network` | medium |
| `permission` | medium |
| `timeout` | medium |
| `runtime` | medium |
| `syntax` | low |
| `type_error` | low |

**Model lifecycle:**
```
Container start
  └─> entrypoint.sh
        ├─> alembic upgrade head
        ├─> if no model → train_model.py (~10s) → saved to volume model_data
        └─> uvicorn starts → lifespan() → ml_service.load() → model in API memory

Worker start (after API healthy)
  └─> first task → _ensure_model() → loads from same volume into worker memory
```

**Isolation:** The API never touches sklearn directly. It only calls `ml_service.predict(text)` which returns a plain dict. The ML class is fully encapsulated in `app/ml_service.py`.

---

## Database

**Schema:**
```sql
CREATE TABLE analyses (
    id              SERIAL PRIMARY KEY,
    input_text      TEXT NOT NULL,
    source          VARCHAR(100),
    category        VARCHAR(100),
    severity        VARCHAR(50),
    confidence      FLOAT,           -- 0.0 to 1.0
    explanation     TEXT,
    recommendations TEXT,            -- JSON-encoded list
    task_id         VARCHAR(200),    -- Celery task reference
    created_at      TIMESTAMP
);
```

All queries go through SQLAlchemy ORM — no raw SQL anywhere.

**Migrations** run automatically on startup via `alembic upgrade head`. Version history is in `api/alembic/versions/`.

**Direct access:**
```bash
psql -h localhost -p 5432 -U appuser -d errorassistant
# password: secret123

SELECT category, COUNT(*), ROUND(AVG(confidence)::numeric, 2) FROM analyses GROUP BY category;
```

---

## API

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| POST | `/api/analyze` | 202 | Enqueue async analysis |
| GET | `/api/tasks/{id}` | 200 | Poll task status |
| GET | `/api/history` | 200 | Recent analyses (newest first) |
| GET | `/api/analysis/{id}` | 200 | Single result by ID |
| GET | `/api/health` | 200 | DB + Redis + model check |
| GET | `/metrics` | 200 | Prometheus metrics |

**Error responses** are always clean JSON — no HTML tracebacks exposed to clients.

| Scenario | Code |
|----------|------|
| Invalid input | 422 |
| Not found | 404 |
| Server error | 500 |

---

## Logging

Daily rotating logs written to `logs/<YYYY-MM-DD>/`:

```
logs/
└── 2026-04-26/
    ├── app.log       API: startup, requests, inference timing
    └── worker.log    Worker: task start/end, model load, errors
```

- Rotates at **midnight UTC**
- Keeps **30 days** of history
- Also streams to stdout (visible in `docker logs`)

---

## Docker & Volumes

**Layer caching** — deps installed before source copy so rebuilds are fast:
```dockerfile
COPY requirements.txt .
RUN pip install ...   # cached unless requirements change
COPY . .              # only invalidated on code change
```

**Volumes:**

| Volume | Purpose |
|--------|---------|
| `postgres_data` | DB persistence |
| `redis_data` | Redis AOF persistence |
| `model_data` | Trained model shared between api + worker |
| `prometheus_data` | Metrics history |
| `grafana_data` | Dashboard state |
| `./logs` (bind) | Daily log files on host |

**Startup order:**
```
postgres ──healthy──┐
                    ├──> api ──healthy──> worker
redis    ──healthy──┘                └──> ui ──> nginx
```

All `depends_on` use `condition: service_healthy` — services wait for real readiness, not just process start.

---

## Monitoring

**Prometheus** scrapes `/metrics` every 15s. Key metrics:

| Metric | Description |
|--------|-------------|
| `http_requests_total` | Requests by endpoint + status code |
| `http_request_duration_seconds` | Response time histogram |
| `http_requests_in_progress` | Active requests |

**Grafana** dashboard (auto-provisioned, no manual setup):
- Request rate (RPS)
- p95 response time
- Total analyses submitted

---

## Health Check

`GET /api/health` verifies three subsystems:

```json
{"status": "ok", "db": "ok", "redis": "ok", "model": "ok"}
```

- `db` — executes `SELECT 1`
- `redis` — sends `PING`
- `model` — checks `ml_service.is_ready`

Returns `"degraded"` if any subsystem fails, so the Compose healthcheck gates dependent services correctly.