from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

MOCK_SIGNALS = {
    "signal_a": {"timestamps": [0.0, 0.1, 0.2], "values": [1.0, 2.0, 3.0], "units": "eV", "description": "Test"},
}


@pytest.mark.asyncio
async def test_classify_no_model_available(auth_client: AsyncClient):
    """Classify should return 404 when no trained model exists."""
    # First, load an experiment so the experiment_id is valid
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        load_res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})
        experiment_id = load_res.json()["id"]

    res = await auth_client.post("/api/v1/predictions/classify", json={
        "experiment_id": experiment_id,
    })
    assert res.status_code == 404
    assert "model" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_disruption_no_model_available(auth_client: AsyncClient):
    """Disruption prediction should return 404 when no trained model exists."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        load_res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})
        experiment_id = load_res.json()["id"]

    res = await auth_client.post("/api/v1/predictions/disruption", json={
        "experiment_id": experiment_id,
    })
    assert res.status_code == 404
    assert "model" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_classify_experiment_not_found(auth_client: AsyncClient):
    """Classify should return 404 when experiment does not exist."""
    res = await auth_client.post("/api/v1/predictions/classify", json={
        "experiment_id": 99999,
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_disruption_experiment_not_found(auth_client: AsyncClient):
    """Disruption prediction should return 404 when experiment does not exist."""
    res = await auth_client.post("/api/v1/predictions/disruption", json={
        "experiment_id": 99999,
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_classify_unauthenticated(client: AsyncClient):
    """Classify endpoint should reject unauthenticated requests."""
    res = await client.post("/api/v1/predictions/classify", json={
        "experiment_id": 1,
    })
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_disruption_unauthenticated(client: AsyncClient):
    """Disruption endpoint should reject unauthenticated requests."""
    res = await client.post("/api/v1/predictions/disruption", json={
        "experiment_id": 1,
    })
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_classify_invalid_threshold(auth_client: AsyncClient):
    """Disruption request with out-of-range threshold should return 422."""
    res = await auth_client.post("/api/v1/predictions/disruption", json={
        "experiment_id": 1,
        "threshold": 1.5,
    })
    assert res.status_code == 422
