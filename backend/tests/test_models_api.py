from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient


def _mock_celery():
    """Return a patch that prevents Celery from trying to connect to Redis."""
    mock_result = MagicMock()
    mock_result.id = "fake-celery-task-id"
    return patch("app.api.models.train_model_task.delay", return_value=mock_result)


async def _train_model(auth_client: AsyncClient, model_type: str = "random_forest", task: str = "classification", hyperparams: dict | None = None) -> dict:
    """Helper to train and return response JSON."""
    payload = {"model_type": model_type, "task": task}
    if hyperparams:
        payload["hyperparameters"] = hyperparams
    with _mock_celery():
        res = await auth_client.post("/api/v1/models/train", json=payload)
    assert res.status_code == 202
    return res.json()


# ────────────────────────────────────────────────────────────────
# Train
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_train_valid_model(auth_client: AsyncClient):
    """Train request with valid model_type should return 202."""
    data = await _train_model(auth_client)
    assert data["status"] == "queued"
    assert "run_id" in data
    assert "model_id" in data


@pytest.mark.asyncio
async def test_train_lstm_model(auth_client: AsyncClient):
    """Train request with lstm_attention should return 202."""
    data = await _train_model(auth_client, model_type="lstm_attention", task="disruption_prediction")
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_train_invalid_model_type(auth_client: AsyncClient):
    """Train request with invalid model_type should return 422."""
    res = await auth_client.post("/api/v1/models/train", json={
        "model_type": "nonexistent_model",
        "task": "classification",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_train_invalid_task(auth_client: AsyncClient):
    """Train request with invalid task should return 422."""
    res = await auth_client.post("/api/v1/models/train", json={
        "model_type": "random_forest",
        "task": "invalid_task",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_train_unauthenticated(client: AsyncClient):
    """Train endpoint should reject unauthenticated requests."""
    res = await client.post("/api/v1/models/train", json={
        "model_type": "random_forest",
        "task": "classification",
    })
    assert res.status_code in (401, 403)


# ────────────────────────────────────────────────────────────────
# List models
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_models_empty(auth_client: AsyncClient):
    """List models returns empty when no models trained."""
    res = await auth_client.get("/api/v1/models/")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_models_after_train(auth_client: AsyncClient):
    """After training, model should appear in the list."""
    train_data = await _train_model(auth_client)
    res = await auth_client.get("/api/v1/models/")
    assert res.status_code == 200
    models = res.json()
    assert len(models) >= 1
    model_ids = [m["id"] for m in models]
    assert train_data["model_id"] in model_ids


@pytest.mark.asyncio
async def test_list_models_pagination(auth_client: AsyncClient):
    """List models should support skip/limit."""
    await _train_model(auth_client, model_type="random_forest", task="classification")
    await _train_model(auth_client, model_type="lstm_attention", task="disruption_prediction")

    res = await auth_client.get("/api/v1/models/?skip=0&limit=1")
    assert res.status_code == 200
    assert len(res.json()) == 1


# ────────────────────────────────────────────────────────────────
# Model versions
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_model_versions(auth_client: AsyncClient):
    """List versions for a specific model."""
    train_data = await _train_model(auth_client)
    model_id = train_data["model_id"]

    res = await auth_client.get(f"/api/v1/models/{model_id}/versions")
    assert res.status_code == 200
    versions = res.json()
    assert len(versions) >= 1


@pytest.mark.asyncio
async def test_list_model_versions_not_found(auth_client: AsyncClient):
    """Versions for non-existent model should return 404."""
    res = await auth_client.get("/api/v1/models/99999/versions")
    assert res.status_code == 404


# ────────────────────────────────────────────────────────────────
# Activate model
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_model(auth_client: AsyncClient):
    """Activate a model version."""
    train_data = await _train_model(auth_client)
    model_id = train_data["model_id"]

    res = await auth_client.put(f"/api/v1/models/{model_id}/activate")
    assert res.status_code == 200
    data = res.json()
    assert data["is_active"] is True
    assert data["id"] == model_id


@pytest.mark.asyncio
async def test_activate_model_not_found(auth_client: AsyncClient):
    """Activate non-existent model should return 404."""
    res = await auth_client.put("/api/v1/models/99999/activate")
    assert res.status_code == 404


# ────────────────────────────────────────────────────────────────
# Runs
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_runs_empty(auth_client: AsyncClient):
    """List runs returns empty list when no training has been done."""
    res = await auth_client.get("/api/v1/models/runs")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_runs_after_train(auth_client: AsyncClient):
    """After training, the run should appear in the list."""
    train_data = await _train_model(auth_client)

    res = await auth_client.get("/api/v1/models/runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) == 1
    assert runs[0]["status"] == "queued"
    assert runs[0]["id"] == train_data["run_id"]


@pytest.mark.asyncio
async def test_get_run_not_found(auth_client: AsyncClient):
    """Requesting a non-existent run should return 404."""
    res = await auth_client.get("/api/v1/models/runs/99999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_run_after_train(auth_client: AsyncClient):
    """Retrieve a specific run by ID after training."""
    train_data = await _train_model(auth_client, model_type="transformer", task="classification", hyperparams={"d_model": 64})
    run_id = train_data["run_id"]

    res = await auth_client.get(f"/api/v1/models/runs/{run_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == run_id
    assert data["status"] == "queued"
    assert data["hyperparams_json"] == {"d_model": 64}


@pytest.mark.asyncio
async def test_list_runs_unauthenticated(client: AsyncClient):
    """Runs list endpoint should reject unauthenticated requests."""
    res = await client.get("/api/v1/models/runs")
    assert res.status_code in (401, 403)


# ────────────────────────────────────────────────────────────────
# Training status
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_training_status(auth_client: AsyncClient):
    """Get training status for a run with a celery task id."""
    train_data = await _train_model(auth_client)
    run_id = train_data["run_id"]

    # Mock celery AsyncResult to avoid Redis connection
    mock_async_result = MagicMock()
    mock_async_result.state = "PROGRESS"
    mock_async_result.info = {"progress": 50}

    with patch("app.api.models.celery_app.AsyncResult", return_value=mock_async_result):
        res = await auth_client.get(f"/api/v1/models/runs/{run_id}/status")

    assert res.status_code == 200
    data = res.json()
    assert data["run_id"] == run_id
    assert data["state"] == "PROGRESS"


@pytest.mark.asyncio
async def test_training_status_success(auth_client: AsyncClient):
    """Training status when celery task succeeded."""
    train_data = await _train_model(auth_client)
    run_id = train_data["run_id"]

    mock_async_result = MagicMock()
    mock_async_result.state = "SUCCESS"
    mock_async_result.result = {"accuracy": 0.95}

    with patch("app.api.models.celery_app.AsyncResult", return_value=mock_async_result):
        res = await auth_client.get(f"/api/v1/models/runs/{run_id}/status")

    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "SUCCESS"
    assert data["progress"] == 100.0
    assert data["info"] == {"accuracy": 0.95}


@pytest.mark.asyncio
async def test_training_status_failure(auth_client: AsyncClient):
    """Training status when celery task failed."""
    train_data = await _train_model(auth_client)
    run_id = train_data["run_id"]

    mock_async_result = MagicMock()
    mock_async_result.state = "FAILURE"
    mock_async_result.result = Exception("Training error")

    with patch("app.api.models.celery_app.AsyncResult", return_value=mock_async_result):
        res = await auth_client.get(f"/api/v1/models/runs/{run_id}/status")

    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "FAILURE"
    assert "error" in data["info"]


@pytest.mark.asyncio
async def test_training_status_not_found(auth_client: AsyncClient):
    """Training status for non-existent run should return 404."""
    res = await auth_client.get("/api/v1/models/runs/99999/status")
    assert res.status_code == 404
