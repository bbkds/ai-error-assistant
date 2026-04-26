"""Deep health check — DB, Redis, and ML model."""
import logging
import redis as redis_lib
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.ml_service import ml_service
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ops"])


@router.get("/api/health", response_model=HealthResponse)
def health():
    """Checks DB (SELECT 1), Redis (PING), and model loaded flag."""
    # DB
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        db_ok = "ok"
    except Exception as e:
        logger.error("DB health: %s", e)
        db_ok = "error"

    # Redis
    try:
        redis_lib.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        redis_ok = "ok"
    except Exception as e:
        logger.error("Redis health: %s", e)
        redis_ok = "error"

    model_ok = "ok" if ml_service.is_ready else "fallback"
    overall = "ok" if db_ok == "ok" and redis_ok == "ok" else "degraded"
    return HealthResponse(status=overall, db=db_ok, redis=redis_ok, model=model_ok)
