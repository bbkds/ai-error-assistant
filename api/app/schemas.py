"""Strict Pydantic v2 schemas — types + constraints + examples."""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=10,
        max_length=10_000,
        description="Raw error log or stack trace",
        examples=["NullPointerException at com.example.Service:42"],
    )
    source: str = Field(default="unknown", max_length=100)

    @field_validator("text")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class TaskResponse(BaseModel):
    task_id: str
    status: str = "pending"
    message: str = "Task enqueued"


class AnalysisResult(BaseModel):
    id: int
    task_id: Optional[str]
    input_text: str
    source: str
    category: str
    severity: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    recommendations: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    model: str
