from __future__ import annotations

import os
import tempfile
import time

import numpy as np
import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from service.data.preprocessing import prepare_features
from service.training.trainer import create_model, load_model

logger = structlog.get_logger()

app = FastAPI(title="Tokamak ML Service", version="1.0.0")

# Cache for loaded models
_model_cache: dict[str, object] = {}


class PredictRequest(BaseModel):
    data: dict
    model_path: str
    model_type: str
    threshold: float = 0.7


class TrainRequest(BaseModel):
    model_type: str
    task: str
    hyperparameters: dict = {}
    shot_ids: list[int] = []
    run_id: int | None = None


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ml"}


@app.post("/api/v1/predict/classify")
async def classify(request: PredictRequest):
    try:
        # Prepare features
        features = prepare_features(request.data.get("signals", {}))

        # Load or get cached model
        model = _get_model(request.model_type, request.model_path)

        start = time.perf_counter()
        prediction = model.predict(features)
        proba = model.predict_proba(features)
        inference_ms = (time.perf_counter() - start) * 1000

        label = "stable" if prediction[0] == 0 else "unstable"
        confidence = float(proba[0].max())

        logger.info("classification_done", label=label, confidence=confidence, inference_ms=inference_ms)

        return {
            "label": label,
            "confidence": confidence,
            "inference_time_ms": inference_ms,
        }
    except Exception as e:
        logger.error("classification_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/predict/disruption")
async def predict_disruption(request: PredictRequest):
    try:
        features = prepare_features(request.data.get("signals", {}))
        model = _get_model(request.model_type, request.model_path)

        start = time.perf_counter()
        proba = model.predict_proba(features)
        inference_ms = (time.perf_counter() - start) * 1000

        probabilities = proba[:, 1].tolist() if proba.ndim > 1 else proba.tolist()

        # Generate timestamps (normalized)
        n_steps = len(probabilities)
        timestamps = list(np.linspace(0, 1, n_steps))

        # Check if warning should be issued
        max_prob = max(probabilities)
        warning_issued = max_prob > request.threshold
        warning_time_ms = None
        if warning_issued:
            warning_idx = next(i for i, p in enumerate(probabilities) if p > request.threshold)
            warning_time_ms = timestamps[warning_idx] * 1000

        return {
            "timestamps": timestamps,
            "probabilities": probabilities,
            "warning_issued": warning_issued,
            "warning_time_ms": warning_time_ms,
            "max_probability": max_prob,
            "inference_time_ms": inference_ms,
        }
    except Exception as e:
        logger.error("disruption_prediction_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/train")
async def train(request: TrainRequest):
    try:
        logger.info("training_started", model_type=request.model_type, task=request.task)

        model = create_model(request.model_type, request.hyperparameters or None)

        # For now, generate synthetic data for testing
        # In production, this would load from FAIR-MAST via shot_ids
        n_samples = 100
        seq_len = request.hyperparameters.get("sequence_length", 200)
        n_features = request.hyperparameters.get("input_size", 39)

        X = np.random.randn(n_samples, seq_len, n_features).astype(np.float32)
        y = np.random.randint(0, 2, n_samples).astype(np.float32)

        # For RF, flatten features
        if request.model_type == "random_forest":
            X_flat = X.reshape(n_samples, -1)
            split = int(0.8 * n_samples)
            metrics = model.fit(X_flat[:split], y[:split], X_flat[split:], y[split:])
        else:
            split = int(0.8 * n_samples)
            metrics = model.fit(X[:split], y[:split], X[split:], y[split:])

        # Save model
        save_dir = tempfile.mkdtemp()
        ext = ".joblib" if request.model_type == "random_forest" else ".pt"
        save_path = os.path.join(save_dir, f"{request.model_type}_{request.task}{ext}")
        model.save(save_path)

        logger.info("training_completed", model_type=request.model_type, metrics=metrics)

        return {
            "status": "completed",
            "metrics": metrics,
            "model_path": save_path,
            "metadata": model.metadata(),
        }
    except Exception as e:
        logger.error("training_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _get_model(model_type: str, model_path: str):
    """Load model with caching."""
    cache_key = f"{model_type}:{model_path}"
    if cache_key not in _model_cache:
        _model_cache[cache_key] = load_model(model_type, model_path)
    return _model_cache[cache_key]
