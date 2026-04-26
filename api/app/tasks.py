"""
Celery tasks — ML inference runs here.
# Логирование — настроено логирование времени всех этапов работы приложения
"""
import json
import logging
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from celery.signals import after_setup_logger, after_setup_task_logger

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Analysis
from app.ml_service import ml_service

def _add_file_handler(logger, **kwargs):
    from datetime import datetime, timezone

    # logs/2026-04-26/worker.log
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    LOG_DIR = Path("/app/logs") / today
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = TimedRotatingFileHandler(
        filename=str(LOG_DIR / "worker.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.namer = lambda name: str(
        Path("/app/logs") / datetime.now(timezone.utc).strftime("%Y-%m-%d") / "worker.log"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

# Hook into Celery's logging signals — fires after Celery configures logging
after_setup_logger.connect(_add_file_handler)
after_setup_task_logger.connect(_add_file_handler)


def _ensure_model():
    """Load model if not already loaded — called at start of every task."""
    if not ml_service.is_ready:
        logging.getLogger(__name__).info("Model not loaded yet — loading now...")
        ml_service.load()


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def analyze_error(self, text: str, source: str) -> dict:
    """Async task: run ML inference and persist result to DB."""
    _ensure_model()

    logger.info("Task %s started source=%s len=%d model_ready=%s",
                self.request.id, source, len(text), ml_service.is_ready)
    t = time.perf_counter()

    try:
        prediction = ml_service.predict(text)

        db = SessionLocal()
        try:
            record = Analysis(
                input_text=text,
                source=source,
                task_id=self.request.id,
                **prediction,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            analysis_id = record.id
        finally:
            db.close()

        logger.info("Task %s done in %.2fs  id=%d  category=%s",
                    self.request.id, time.perf_counter() - t,
                    analysis_id, prediction["category"])
        return {"analysis_id": analysis_id, "category": prediction["category"]}

    except Exception as exc:
        logger.error("Task %s failed: %s", self.request.id, exc, exc_info=True)
        raise self.retry(exc=exc)