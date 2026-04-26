#!/usr/bin/env python3
"""
Train TF-IDF + Logistic Regression error classifier.
Called automatically by entrypoint.sh if model file is absent.
Output: /app/models/error_classifier.joblib
"""
import logging
import os
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Paths work both inside Docker (/app/...) and locally (relative)
# BASE_DIR = Path(__file__).resolve().parent.parent  # api/
# DATA_PATH = BASE_DIR / "data" / "errors_dataset.csv"
# MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/models"))
# MODEL_PATH = MODEL_DIR / "error_classifier.joblib"

DATA_PATH = Path("/app/data/errors_dataset.csv") # hardcoded Docker paths
MODEL_DIR = Path("/app/models")
MODEL_PATH = MODEL_DIR / "error_classifier.joblib"


def train() -> None:
    logger.info("Loading dataset from %s", DATA_PATH)
    df = pd.read_csv(DATA_PATH)
    logger.info("Dataset: %d rows  categories: %s", len(df), df["category"].unique().tolist())

    X, y = df["text"], df["category"]

    # Stratified split preserves class proportions in small dataset
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info("Train=%d  Test=%d", len(X_train), len(X_test))

    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 4),        # capture longer natural phrases
                max_features=20_000,
                sublinear_tf=True,
                min_df=1,                  # small dataset — keep all terms
                analyzer="word",
                token_pattern=r"(?u)\b\w+\b",
            ),
        ),
        (
            "clf",
            LogisticRegression(
                C=10.0,
                max_iter=2000,
                class_weight="balanced",
                solver="lbfgs",
            ),
        ),
    ])
    logger.info("Training...")
    pipeline.fit(X_train, y_train)

    report = classification_report(y_test, pipeline.predict(X_test))
    logger.info("Evaluation:\n%s", report)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    logger.info("Model saved → %s", MODEL_PATH)


if __name__ == "__main__":
    train()
