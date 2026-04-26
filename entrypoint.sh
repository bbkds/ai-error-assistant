#!/bin/sh
set -e

export PYTHONPATH=/app

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Checking for trained model..."
if [ ! -f /app/models/error_classifier.joblib ]; then
    echo "==> Training model..."
    python /app/scripts/train_model.py
    echo "==> Model trained."
else
    echo "==> Model already cached."
fi

echo "==> Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2