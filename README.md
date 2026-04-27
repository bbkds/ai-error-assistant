# 🔍 AI  Error Assistant

An async error log classification system powered by **TF-IDF + Logistic Regression**. Paste any error log or stack trace — the ML model predicts the category, severity, confidence, and recommendations.

Built with FastAPI · Celery · Streamlit · PostgreSQL · Redis · Nginx · Prometheus · Grafana · Docker Compose.

---

## Quick Start

```bash
git clone https://github.com/your-username/ai-backend-error-assistant.git
cd ai-backend-error-assistant

docker compose up --build -d
```

On first run the API container automatically:
1. Runs Alembic DB migrations
2. Trains the ML model (~10s)
3. Starts serving

Open **http://localhost** in your browser.

---

## Services & Ports

| Service | URL | Notes |
|---------|-----|-------|
| App (UI) | http://localhost | Main entry via Nginx |
| API Docs | http://localhost/api/docs | Swagger UI |
| Health | http://localhost/api/health | DB + Redis + model status |
| Metrics | http://localhost/metrics | Prometheus scrape endpoint |
| Grafana | http://localhost:3000 | admin / admin |
| PostgreSQL | localhost:5432 | Direct DB access |

---

## API Reference

**Analyze an error log**
```bash
curl -X POST http://localhost/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "the process ran out of memory and was killed", "source": "backend"}'
# → 202 {"task_id": "abc123", "status": "pending"}
```

**Poll for result**
```bash
curl http://localhost/api/tasks/abc123
# → {"status": "success", "result": {"category": "memory", "severity": "critical", ...}}
```

**View history**
```bash
curl http://localhost/api/history?limit=20
```

**Health check**
```bash
curl http://localhost/api/health
# → {"status": "ok", "db": "ok", "redis": "ok", "model": "ok"}
```

---

## Environment Variables

All config lives in `.env` — no hardcoded values anywhere.

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `appuser` | DB username |
| `POSTGRES_PASSWORD` | `secret123` | DB password |
| `POSTGRES_DB` | `errorassistant` | DB name |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Grafana login |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Logs

Logs are written to `logs/<YYYY-MM-DD>/` and rotate daily at midnight UTC.

```
logs/
└── 2026-04-26/
    ├── app.log       ← API logs
    └── worker.log    ← Celery worker / inference logs
```

```bash
# Live tail
docker exec ai-backend-error-assistant-api-1 tail -f /app/logs/$(date +%Y-%m-%d)/app.log
```

---

## Useful Commands

```bash
# Start
docker compose up --build -d

# Stop
docker compose down

# Fresh start (wipe all data)
docker compose down -v

# Force model retrain
docker compose down
docker volume rm ai-backend-error-assistant_model_data
docker compose up --build -d

# View API logs
docker logs -f ai-backend-error-assistant-api-1

# Connect to DB
psql -h localhost -p 5432 -U appuser -d errorassistant
# password: secret123
```

---

## Project Structure

```
├── api/                  FastAPI backend + ML + migrations
│   ├── app/
│   │   ├── main.py       Entry point, lifespan, error handlers
│   │   ├── config.py     Settings from .env
│   │   ├── database.py   SQLAlchemy engine + session
│   │   ├── models.py     ORM models
│   │   ├── schemas.py    Pydantic v2 schemas
│   │   ├── ml_service.py Isolated ML inference class
│   │   ├── celery_app.py Celery factory
│   │   ├── tasks.py      Async Celery tasks
│   │   └── routers/      API endpoints
│   ├── alembic/          DB migrations
│   ├── data/             Training dataset (450 rows)
│   └── scripts/          train_model.py
├── worker/               Celery worker container
├── ui/                   Streamlit frontend
├── nginx/                Reverse proxy + rate limiting
├── monitoring/           Prometheus + Grafana config
├── logs/                 Daily rotating logs (git-ignored)
├── .env                  Pre-filled safe defaults
└── docker-compose.yml
```

---

## Requirements Coverage

| Criterion | Status |
|-----------|--------|
| FastAPI + lifespan model loading | ✅ |
| Celery async tasks + Redis broker + polling | ✅ |
| Pydantic v2 strict schemas | ✅ |
| Custom error handlers + correct HTTP codes | ✅ |
| Isolated ML class (`predict()` only) | ✅ |
| Resource management + inference logging | ✅ |
| Streamlit UI calling ≥ 3 endpoints | ✅ |
| REST-only UI (no direct backend imports) | ✅ |
| Spinner + progress bar while waiting | ✅ |
| UI network isolation (no DB/Redis access) | ✅ |
| Graceful 503 error handling in UI | ✅ |
| Plotly charts (pie, bar, scatter, gauge) | ✅ |
| Nginx single entry point :80 | ✅ |
| `/api/*` → backend, `/` → UI routing | ✅ |
| Rate limiting (5 req/min per IP) | ✅ |
| SQLAlchemy ORM, zero raw SQL | ✅ |
| Alembic versioned migrations | ✅ |
| Dockerfiles with layer caching | ✅ |
| Isolated networks (frontend / backend) | ✅ |
| Volumes for DB, Redis, model, logs | ✅ |
| `depends_on` with `service_healthy` | ✅ |
| Stateless API (state in Redis/DB) | ✅ |
| Graceful shutdown (SIGTERM) | ✅ |
| `/health` checks DB + Redis + model | ✅ |
| Compose healthchecks on all services | ✅ |
| Prometheus metrics + Grafana dashboard | ✅ |