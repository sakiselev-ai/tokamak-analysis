from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

ML_INFERENCE_DURATION = Histogram(
    "ml_inference_duration_seconds",
    "ML inference duration",
    ["model_type"],
)
ML_TRAINING_DURATION = Histogram(
    "ml_training_duration_seconds",
    "ML training duration",
    ["model_type"],
)
