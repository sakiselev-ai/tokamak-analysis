from __future__ import annotations

import os
import time

import numpy as np
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from service.metrics import CONTENT_TYPE_LATEST, ML_INFERENCE_DURATION, ML_TRAINING_DURATION, generate_latest

from service.data.dataset import get_sample_dataset
from service.data.fair_mast_loader import load_disruption_labels, load_shots, make_disruption_labels
from service.data.metrics import compute_metrics, format_confusion_matrix
from service.data.preprocessing import prepare_batch, prepare_features
from service.training.trainer import create_model, load_model

logger = structlog.get_logger()

app = FastAPI(title="Tokamak ML Service", version="1.0.0")

# Cache for loaded models
_model_cache: dict[str, object] = {}


class PredictRequest(BaseModel):
    data: dict
    model_path: str | None = None
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


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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

        seq_len = request.hyperparameters.get("sequence_length", 200)
        n_features = request.hyperparameters.get("input_size", 39)

        if request.shot_ids:
            # Load real data from FAIR-MAST
            shots_data, loaded_ids = load_shots(request.shot_ids)
            if not shots_data:
                raise HTTPException(
                    status_code=404,
                    detail="No valid shots could be loaded from the provided shot_ids",
                )
            X = prepare_batch(
                [{"signals": s} for s in shots_data],
                sequence_length=seq_len,
            )
            # Load real disruption labels from FAIR-MAST
            disruption_times = load_disruption_labels(loaded_ids)
            y = make_disruption_labels(loaded_ids, disruption_times)

            logger.info(
                "disruption_labels_loaded",
                n_disrupted=int(y.sum()),
                n_stable=int(len(y) - y.sum()),
            )

            from service.data.dataset import build_dataset
            dataset = build_dataset(X, y)
        else:
            # Use synthetic sample data for testing / development
            dataset = get_sample_dataset(
                n_samples=200,
                seq_len=seq_len,
                n_features=n_features,
                task=request.task,
            )

        # Train the model
        if request.model_type == "random_forest":
            X_tr, y_tr = dataset.flat_train()
            X_v, y_v = dataset.flat_val()
            X_te, y_te = dataset.flat_test()
        else:
            X_tr, y_tr = dataset.X_train, dataset.y_train
            X_v, y_v = dataset.X_val, dataset.y_val
            X_te, y_te = dataset.X_test, dataset.y_test

        train_metrics = model.fit(X_tr, y_tr, X_v, y_v)

        # Compute proper test metrics
        y_pred = model.predict(X_te)
        y_proba = model.predict_proba(X_te)
        test_metrics = compute_metrics(y_te, y_pred, y_proba)
        cm = format_confusion_matrix(y_te, y_pred)

        # Save model to persistent directory
        save_dir = "/tmp/tokamak_models"
        os.makedirs(save_dir, exist_ok=True)
        ext = ".joblib" if request.model_type == "random_forest" else ".pt"
        run_tag = f"_run{request.run_id}" if request.run_id else ""
        save_path = os.path.join(
            save_dir, f"{request.model_type}_{request.task}{run_tag}{ext}"
        )
        model.save(save_path)

        logger.info(
            "training_completed",
            model_type=request.model_type,
            test_metrics=test_metrics,
        )

        return {
            "status": "completed",
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
            "confusion_matrix": cm,
            "model_path": save_path,
            "metadata": model.metadata(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("training_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


_DEFAULT_MODEL_PATHS: dict[str, str] = {
    "random_forest": "models/rf_baseline.joblib",
    "lstm_attention": "models/lstm_attention.pt",
    "transformer": "models/transformer.pt",
}


def _get_model(model_type: str, model_path: str | None):
    """Load model with caching. Falls back to default paths if model_path doesn't exist."""
    cache_key = f"{model_type}:{model_path}"
    if cache_key not in _model_cache:
        actual_path = model_path or ""
        if not actual_path or not os.path.exists(actual_path):
            fallback = _DEFAULT_MODEL_PATHS.get(model_type)
            if fallback and os.path.exists(fallback):
                logger.warning("model_path_fallback", original=model_path, fallback=fallback)
                actual_path = fallback
                cache_key = f"{model_type}:{actual_path}"
            else:
                # Train a quick model on synthetic data as last resort
                logger.warning("model_not_found_training_synthetic", model_type=model_type)
                dataset = get_sample_dataset(n_samples=100, seq_len=200, n_features=20, task="classification")
                model = create_model(model_type)
                if model_type == "random_forest":
                    X_tr, y_tr = dataset.flat_train()
                    model.fit(X_tr, y_tr)
                else:
                    model.fit(dataset.X_train, dataset.y_train)
                _model_cache[cache_key] = model
                return model
        if cache_key not in _model_cache:
            _model_cache[cache_key] = load_model(model_type, actual_path)
    return _model_cache[cache_key]
