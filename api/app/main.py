"""
FastAPI entry point.
Lifespan: load ML model once at startup (Model-in-App pattern).
"""
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.ml_service import ml_service
from app.routers import analyze, health

def setup_logging():
    from datetime import datetime, timezone

    # logs/2026-04-26/app.log
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    LOG_DIR = Path("/app/logs") / today
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    file_handler = TimedRotatingFileHandler(
        filename=str(LOG_DIR / "app.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.namer = lambda name: str(
        Path("/app/logs") / datetime.now(timezone.utc).strftime("%Y-%m-%d") / "app.log"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model into memory at startup; yield; then shutdown."""
    logger.info("Startup — loading ML model...")
    ml_service.load()
    logger.info("Model ready=%s", ml_service.is_ready)
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title="AI Backend Error Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# Expose /metrics for Prometheus scraping
Instrumentator().instrument(app).expose(app)

app.include_router(analyze.router)
app.include_router(health.router)


@app.exception_handler(Exception)
async def _generic(request: Request, exc: Exception):
    """Return clean JSON on unhandled errors — no HTML tracebacks."""
    logger.error("Unhandled %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
