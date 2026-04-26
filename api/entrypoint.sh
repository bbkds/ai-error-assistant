#!/bin/sh
set -e

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Checking for trained model..."
if [ ! -f /app/models/error_classifier.joblib ]; then
    echo "==> Model not found — training now (this takes ~10s)..."
    python /app/scripts/train_model.py
    echo "==> Model trained and saved."
else
    echo "==> Model already exists, skipping training."
fi

echo "==> Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
