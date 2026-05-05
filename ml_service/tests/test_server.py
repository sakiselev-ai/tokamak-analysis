from __future__ import annotations

from unittest.mock import patch

import numpy as np
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
    assert "final_train_loss" in data["train_metrics"]


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


def _make_fake_shot(n_signals: int = 5, n_steps: int = 100) -> dict[str, dict]:
    """Create a minimal fake shot data dict with random signals."""
    rng = np.random.RandomState(0)
    signals = {}
    for i in range(n_signals):
        signals[f"signal_{i}"] = {
            "timestamps": np.linspace(0, 1, n_steps).tolist(),
            "values": rng.randn(n_steps).tolist(),
            "units": "arb",
        }
    return signals


@pytest.mark.asyncio
async def test_train_with_real_labels(ml_client: AsyncClient):
    """Train endpoint should use real disruption labels when shot_ids are provided."""
    fake_shots = [_make_fake_shot() for _ in range(10)]
    disruption_times = {
        100: 0.5,    # disrupted
        101: None,   # stable
        102: 0.3,    # disrupted
        103: None,   # stable
        104: None,   # stable
        105: 0.8,    # disrupted
        106: None,   # stable
        107: None,   # stable
        108: 0.2,    # disrupted
        109: None,   # stable
    }
    shot_ids = list(range(100, 110))

    with patch("service.server.load_shots", return_value=(fake_shots, shot_ids)) as mock_load, \
         patch("service.server.load_disruption_labels", return_value=disruption_times) as mock_labels:
        res = await ml_client.post("/api/v1/train", json={
            "model_type": "random_forest",
            "task": "classification",
            "shot_ids": shot_ids,
            "hyperparameters": {
                "n_estimators": 5,
                "max_depth": 3,
                "random_state": 42,
                "input_size": 5,
                "sequence_length": 10,
            },
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert "model_path" in data

        mock_load.assert_called_once_with(shot_ids)
        mock_labels.assert_called_once_with(shot_ids)


@pytest.mark.asyncio
async def test_train_synthetic_fallback(ml_client: AsyncClient):
    """Train endpoint should use synthetic data when shot_ids is empty."""
    res = await ml_client.post("/api/v1/train", json={
        "model_type": "random_forest",
        "task": "classification",
        "shot_ids": [],
        "hyperparameters": {
            "n_estimators": 5,
            "max_depth": 3,
            "random_state": 42,
            "input_size": 5,
            "sequence_length": 10,
        },
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_train_no_valid_shots_returns_404(ml_client: AsyncClient):
    """Train endpoint should return 404 when all shots fail to load."""
    with patch("service.server.load_shots", return_value=([], [])):
        res = await ml_client.post("/api/v1/train", json={
            "model_type": "random_forest",
            "task": "classification",
            "shot_ids": [999999],
            "hyperparameters": {},
        })
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_train_disruption_labels_all_stable(ml_client: AsyncClient):
    """Training should work even when all shots are stable (no disruptions)."""
    fake_shots = [_make_fake_shot() for _ in range(6)]
    # All shots stable
    disruption_times = {i: None for i in range(200, 206)}
    shot_ids = list(range(200, 206))

    with patch("service.server.load_shots", return_value=(fake_shots, shot_ids)), \
         patch("service.server.load_disruption_labels", return_value=disruption_times):
        res = await ml_client.post("/api/v1/train", json={
            "model_type": "random_forest",
            "task": "classification",
            "shot_ids": shot_ids,
            "hyperparameters": {
                "n_estimators": 5,
                "max_depth": 3,
                "random_state": 42,
                "input_size": 5,
                "sequence_length": 10,
            },
        })
        assert res.status_code == 200
        assert res.json()["status"] == "completed"
