FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install deps from worker's own requirements
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now COPY from api/ works because context is the project root
COPY api/app ./app

CMD ["celery", "-A", "app.celery_app:celery_app", "worker", \
     "--loglevel=info", "--concurrency=2"]