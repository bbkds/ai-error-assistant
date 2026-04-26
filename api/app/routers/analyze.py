"""Analysis endpoints: submit, poll, history, detail."""
import json
import logging
from typing import List

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis
from app.schemas import AnalyzeRequest, AnalysisResult, TaskResponse, TaskStatusResponse
from app.tasks import analyze_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_analysis(payload: AnalyzeRequest):
    """Enqueue async Celery task; return task_id immediately (202 Accepted)."""
    task = analyze_error.delay(payload.text, payload.source)
    logger.info("Enqueued task %s", task.id)
    return TaskResponse(task_id=task.id)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """Polling endpoint — call every few seconds until status == success."""
    result = AsyncResult(task_id)
    s = result.status.lower()  # pending | started | success | failure

    if s == "success":
        aid = result.result.get("analysis_id")
        obj = db.query(Analysis).filter(Analysis.id == aid).first()
        if not obj:
            raise HTTPException(404, "Analysis record not found")
        return TaskStatusResponse(task_id=task_id, status="success", result=_schema(obj))

    if s == "failure":
        return TaskStatusResponse(task_id=task_id, status="failure", error=str(result.result))

    return TaskStatusResponse(task_id=task_id, status=s)


@router.get("/history", response_model=List[AnalysisResult])
def get_history(limit: int = 50, db: Session = Depends(get_db)):
    """Most recent analyses, newest first."""
    rows = db.query(Analysis).order_by(Analysis.created_at.desc()).limit(limit).all()
    return [_schema(r) for r in rows]


@router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    obj = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not obj:
        raise HTTPException(404, "Not found")
    return _schema(obj)


def _schema(obj: Analysis) -> AnalysisResult:
    """ORM → Pydantic; decode JSON recommendations list."""
    return AnalysisResult(
        id=obj.id, task_id=obj.task_id, input_text=obj.input_text,
        source=obj.source, category=obj.category, severity=obj.severity,
        confidence=obj.confidence, explanation=obj.explanation,
        recommendations=json.loads(obj.recommendations),
        created_at=obj.created_at,
    )
