from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from service.server import app


@pytest_asyncio.fixture
async def ml_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(ml_client: AsyncClient):
    res = await ml_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ml"


@pytest.mark.asyncio
async def test_train_rf(ml_client: AsyncClient):
    res = await ml_client.post("/api/v1/train", json={
        "model_type": "random_forest",
        "task": "classification",
        "hyperparameters": {
            "n_estimators": 10,
            "max_depth": 5,
            "random_state": 42,
            "input_size": 5,
            "sequence_length": 10,
        },
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert "test_metrics" in data or "metrics" in data
    assert "model_path" in data
    assert "metadata" in data
    assert data["metadata"]["architecture"] == "RandomForest"


@pytest.mark.asyncio
async def test_train_rf_returns_metrics(ml_client: AsyncClient):
    res = await ml_client.post("/api/v1/train", json={
        "model_type": "random_forest",
        "task": "classification",
        "hyperparameters": {
            "n_estimators": 5,
            "max_depth": 3,
            "random_state": 0,
            "input_size": 5,
            "sequence_length": 10,
        },
    })
    assert res.status_code == 200
    data = res.json()
    test_metrics = data.get("test_metrics", data.get("metrics", {}))
    assert "accuracy" in test_metrics or "train_accuracy" in test_metrics


@pytest.mark.asyncio
async def test_train_lstm(ml_client: AsyncClient):
    res = await ml_client.post("/api/v1/train", json={
        "model_type": "lstm_attention",
        "task": "classification",
        "hyperparameters": {
            "input_size": 5,
            "hidden_size": 16,
            "num_layers": 1,
            "bidirectional": True,
            "dropout": 0.0,
            "attention_heads": 2,
            "sequence_length": 10,
            "learning_rate": 1e-3,
            "batch_size": 16,
            "epochs": 1,
            "early_stopping_patience": 2,
            "weight_decay": 0.0,
        },
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert "final_train_loss" in data["metrics"]


@pytest.mark.asyncio
async def test_train_transformer(ml_client: AsyncClient):
    res = await ml_client.post("/api/v1/train", json={
        "model_type": "transformer",
        "task": "disruption_prediction",
        "hyperparameters": {
            "input_size": 5,
            "d_model": 16,
            "num_heads": 2,
            "num_layers": 1,
            "dim_feedforward": 32,
            "dropout": 0.0,
            "sequence_length": 10,
            "learning_rate": 1e-3,
            "warmup_steps": 5,
            "batch_size": 16,
            "epochs": 1,
            "early_stopping_patience": 2,
            "weight_decay": 0.0,
        },
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_train_invalid_model_type(ml_client: AsyncClient):
    res = await ml_client.post("/api/v1/train", json={
        "model_type": "nonexistent",
        "task": "classification",
        "hyperparameters": {},
    })
    assert res.status_code == 500


@pytest.mark.asyncio
async def test_classify_no_model(ml_client: AsyncClient):
    """Classify endpoint should return 500 when model path is invalid."""
    res = await ml_client.post("/api/v1/predict/classify", json={
        "data": {"signals": {}},
        "model_path": "/nonexistent/model.joblib",
        "model_type": "random_forest",
    })
    assert res.status_code == 500


@pytest.mark.asyncio
async def test_disruption_no_model(ml_client: AsyncClient):
    """Disruption endpoint should return 500 when model path is invalid."""
    res = await ml_client.post("/api/v1/predict/disruption", json={
        "data": {"signals": {}},
        "model_path": "/nonexistent/model.joblib",
        "model_type": "random_forest",
        "threshold": 0.7,
    })
    assert res.status_code == 500
