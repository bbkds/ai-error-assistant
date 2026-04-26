"""
ML service — fully isolated inference module.
The API only calls ml_service.predict(text); it never touches sklearn directly.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

logger = logging.getLogger(__name__)

# Maps predicted category → human severity level
SEVERITY_MAP = {
    "null_pointer": "high", "memory": "critical", "database": "high",
    "network": "medium", "authentication": "high", "permission": "medium",
    "timeout": "medium", "syntax": "low", "type_error": "low",
    "runtime": "medium", "unknown": "low",
}

EXPLANATIONS = {
    "null_pointer": "A null/None reference was dereferenced. Check object initialisation.",
    "memory": "Memory allocation failure or heap exhaustion detected.",
    "database": "Database connectivity or query execution issue.",
    "network": "Network communication failure (timeout, refused, DNS).",
    "authentication": "Authentication or authorisation failure.",
    "permission": "Insufficient permissions to access a resource.",
    "timeout": "An operation exceeded its allowed time limit.",
    "syntax": "Code or configuration syntax error.",
    "type_error": "Incorrect type used in an operation.",
    "runtime": "General runtime exception.",
    "unknown": "Could not determine a specific error category.",
}

RECOMMENDATIONS = {
    "null_pointer": ["Add null/None guards before dereferencing", "Use Optional types and defensive checks", "Review object initialisation flow"],
    "memory": ["Profile heap usage with a memory profiler", "Check for memory leaks in long-running tasks", "Increase heap limits if justified"],
    "database": ["Verify connection string and credentials", "Check connection pool exhaustion", "Review slow query logs"],
    "network": ["Check service discovery / DNS resolution", "Verify firewall rules and port availability", "Implement retry with exponential back-off"],
    "authentication": ["Rotate compromised credentials", "Check token expiry and refresh logic", "Review IAM policies"],
    "permission": ["Check filesystem / resource permissions", "Run the service under the correct user", "Audit security group / ACL settings"],
    "timeout": ["Increase timeout thresholds if justified", "Optimise the slow operation", "Add circuit breaker pattern"],
    "syntax": ["Run a linter on the affected file", "Review recent config/code changes"],
    "type_error": ["Add type annotations and run mypy", "Validate input types at API boundaries"],
    "runtime": ["Review the full stack trace for root cause", "Add structured exception logging"],
    "unknown": ["Collect more context from surrounding logs", "Enable DEBUG logging temporarily"],
}


class MLService:
    """Loads and runs the TF-IDF + LogReg pipeline."""

    MODEL_PATH = Path("/app/models/error_classifier.joblib")

    def __init__(self) -> None:
        self._pipeline = None
        self._ready = False

    def load(self) -> None:
        """Called once at app startup via lifespan."""
        if not self.MODEL_PATH.exists():
            logger.warning("Model not found at %s — using rule-based fallback", self.MODEL_PATH)
            return
        t = time.perf_counter()
        self._pipeline = joblib.load(self.MODEL_PATH)
        self._ready = True
        logger.info("Model loaded in %.2fs", time.perf_counter() - t)

    @property
    def is_ready(self) -> bool:
        return self._ready

    def predict(self, text: str) -> dict:
        """Run inference; fall back to keyword rules if model unavailable."""
        t = time.perf_counter()

        if self._ready:
            category = self._pipeline.predict([text])[0]
            confidence = float(np.max(self._pipeline.predict_proba([text])[0]))
        else:
            category, confidence = self._rule_based(text)

        elapsed = time.perf_counter() - t
        logger.info("Inference %.3fs  category=%s  confidence=%.2f", elapsed, category, confidence)

        return {
            "category": category,
            "severity": SEVERITY_MAP.get(category, "low"),
            "confidence": confidence,
            "explanation": EXPLANATIONS.get(category, EXPLANATIONS["unknown"]),
            "recommendations": json.dumps(RECOMMENDATIONS.get(category, RECOMMENDATIONS["unknown"])),
        }

    @staticmethod
    def _rule_based(text: str) -> tuple:
        """Keyword heuristic fallback — used when model file is absent."""
        t = text.lower()
        rules = [
            (["nullpointerexception","null pointer","nonetype object has no attribute"], "null_pointer"),
            (["outofmemory","heap space","memoryerror","cannot allocate"], "memory"),
            (["sqlexception","psycopg2","operationalerror","connection refused 5432","duplicate key"], "database"),
            (["connectionrefused","connection timed out","urlerror","socket.timeout","econnrefused"], "network"),
            (["401","403","unauthorized","forbidden","invalid token","jwt"], "authentication"),
            (["permissionerror","permission denied","eacces","access denied"], "permission"),
            (["timeout","timed out","deadline exceeded","timeouted"], "timeout"),
            (["syntaxerror","unexpected token","jsondecodeerror","parse error"], "syntax"),
            (["typeerror","classcastexception","invalidcastexception"], "type_error"),
            (["runtimeerror","runtime error"], "runtime"),
        ]
        for keywords, cat in rules:
            if any(k in t for k in keywords):
                return cat, 0.75
        return "unknown", 0.50


# Module-level singleton imported by tasks.py and routers
ml_service = MLService()
