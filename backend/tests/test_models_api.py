from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_train_valid_model(auth_client: AsyncClient):
    """Train request with valid model_type should return 202."""
    res = await auth_client.post("/api/v1/models/train", json={
        "model_type": "random_forest",
        "task": "classification",
        "hyperparameters": {"n_estimators": 10, "max_depth": 5},
    })
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "queued"
    assert "run_id" in data
    assert "model_id" in data


@pytest.mark.asyncio
async def test_train_lstm_model(auth_client: AsyncClient):
    """Train request with lstm_attention should return 202."""
    res = await auth_client.post("/api/v1/models/train", json={
        "model_type": "lstm_attention",
        "task": "disruption_prediction",
    })
    assert res.status_code == 202
    data = res.json()
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
async def test_list_runs_empty(auth_client: AsyncClient):
    """List runs returns empty list when no training has been done."""
    res = await auth_client.get("/api/v1/models/runs")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_runs_after_train(auth_client: AsyncClient):
    """After training, the run should appear in the list."""
    train_res = await auth_client.post("/api/v1/models/train", json={
        "model_type": "random_forest",
        "task": "classification",
    })
    assert train_res.status_code == 202

    res = await auth_client.get("/api/v1/models/runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) == 1
    assert runs[0]["status"] == "queued"
    assert runs[0]["id"] == train_res.json()["run_id"]


@pytest.mark.asyncio
async def test_get_run_not_found(auth_client: AsyncClient):
    """Requesting a non-existent run should return 404."""
    res = await auth_client.get("/api/v1/models/runs/99999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_run_after_train(auth_client: AsyncClient):
    """Retrieve a specific run by ID after training."""
    train_res = await auth_client.post("/api/v1/models/train", json={
        "model_type": "transformer",
        "task": "classification",
        "hyperparameters": {"d_model": 64},
    })
    run_id = train_res.json()["run_id"]

    res = await auth_client.get(f"/api/v1/models/runs/{run_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == run_id
    assert data["status"] == "queued"
    assert data["hyperparams_json"] == {"d_model": 64}


@pytest.mark.asyncio
async def test_train_unauthenticated(client: AsyncClient):
    """Train endpoint should reject unauthenticated requests."""
    res = await client.post("/api/v1/models/train", json={
        "model_type": "random_forest",
        "task": "classification",
    })
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_runs_unauthenticated(client: AsyncClient):
    """Runs list endpoint should reject unauthenticated requests."""
    res = await client.get("/api/v1/models/runs")
    assert res.status_code in (401, 403)
