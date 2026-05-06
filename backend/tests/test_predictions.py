from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, Response

MOCK_SIGNALS = {
    "signal_a": {"timestamps": [0.0, 0.1, 0.2], "values": [1.0, 2.0, 3.0], "units": "eV", "description": "Test"},
}

MOCK_CLASSIFY_RESULT = {
    "label": "stable",
    "confidence": 0.92,
}

MOCK_DISRUPTION_RESULT = {
    "timestamps": [0.0, 0.1, 0.2],
    "probabilities": [0.1, 0.5, 0.95],
    "warning_issued": True,
    "warning_time_ms": 150.0,
    "max_probability": 0.95,
}


async def _load_experiment(auth_client: AsyncClient) -> int:
    """Helper to load a test experiment and return its id."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        load_res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})
        return load_res.json()["id"]


async def _create_model(auth_client: AsyncClient, task: str = "classification") -> int:
    """Helper to create a model via training endpoint and return model_id."""
    mock_result = MagicMock()
    mock_result.id = "fake-celery-task-id"
    with patch("app.api.models.train_model_task.delay", return_value=mock_result):
        res = await auth_client.post("/api/v1/models/train", json={
            "model_type": "random_forest",
            "task": task,
        })
        return res.json()["model_id"]


def _mock_httpx_post(return_json: dict):
    """Create a mock for httpx.AsyncClient that returns the given JSON."""
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = return_json
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ────────────────────────────────────────────────────────────────
# Existing tests (preserved)
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_no_model_available(auth_client: AsyncClient):
    """Classify should return 404 when no trained model exists."""
    experiment_id = await _load_experiment(auth_client)

    res = await auth_client.post("/api/v1/predictions/classify", json={
        "experiment_id": experiment_id,
    })
    assert res.status_code == 404
    assert "model" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_disruption_no_model_available(auth_client: AsyncClient):
    """Disruption prediction should return 404 when no trained model exists."""
    experiment_id = await _load_experiment(auth_client)

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


# ────────────────────────────────────────────────────────────────
# New tests — classify with mocked ML service
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_success(auth_client: AsyncClient):
    """Classify should return a valid ClassifyResponse when model + experiment exist."""
    experiment_id = await _load_experiment(auth_client)
    model_id = await _create_model(auth_client, task="classification")

    mock_client = _mock_httpx_post(MOCK_CLASSIFY_RESULT)

    with patch("app.api.predictions.httpx.AsyncClient", return_value=mock_client):
        res = await auth_client.post("/api/v1/predictions/classify", json={
            "experiment_id": experiment_id,
        })

    assert res.status_code == 200
    data = res.json()
    assert data["label"] == "stable"
    assert data["confidence"] == 0.92
    assert data["experiment_id"] == experiment_id
    assert "inference_time_ms" in data
    assert data["model_id"] == model_id


@pytest.mark.asyncio
async def test_classify_with_explicit_model_id(auth_client: AsyncClient):
    """Classify with an explicit model_id should work."""
    experiment_id = await _load_experiment(auth_client)
    model_id = await _create_model(auth_client, task="classification")

    mock_client = _mock_httpx_post(MOCK_CLASSIFY_RESULT)

    with patch("app.api.predictions.httpx.AsyncClient", return_value=mock_client):
        res = await auth_client.post("/api/v1/predictions/classify", json={
            "experiment_id": experiment_id,
            "model_id": model_id,
        })

    assert res.status_code == 200
    assert res.json()["label"] == "stable"


# ────────────────────────────────────────────────────────────────
# New tests — disruption prediction with mocked ML service
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_disruption_success(auth_client: AsyncClient):
    """Disruption prediction should return timestamped probabilities and recommendations."""
    experiment_id = await _load_experiment(auth_client)
    await _create_model(auth_client, task="disruption_prediction")

    mock_client = _mock_httpx_post(MOCK_DISRUPTION_RESULT)

    with patch("app.api.predictions.httpx.AsyncClient", return_value=mock_client):
        res = await auth_client.post("/api/v1/predictions/disruption", json={
            "experiment_id": experiment_id,
        })

    assert res.status_code == 200
    data = res.json()
    assert data["warning_issued"] is True
    assert len(data["timestamps"]) == 3
    assert len(data["probabilities"]) == 3
    assert data["warning_time_ms"] == 150.0
    assert "inference_time_ms" in data
    # Should contain recommendations since max_prob > 0.9
    assert len(data["recommendations"]) > 0


@pytest.mark.asyncio
async def test_disruption_with_custom_threshold(auth_client: AsyncClient):
    """Disruption prediction with custom threshold."""
    experiment_id = await _load_experiment(auth_client)
    await _create_model(auth_client, task="disruption_prediction")

    mock_client = _mock_httpx_post(MOCK_DISRUPTION_RESULT)

    with patch("app.api.predictions.httpx.AsyncClient", return_value=mock_client):
        res = await auth_client.post("/api/v1/predictions/disruption", json={
            "experiment_id": experiment_id,
            "threshold": 0.3,
        })

    assert res.status_code == 200
    assert res.json()["warning_issued"] is True


# ────────────────────────────────────────────────────────────────
# New tests — batch classify
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch_classify_success(auth_client: AsyncClient):
    """Batch classify should return results for all valid experiments."""
    eid1 = await _load_experiment(auth_client)
    await _create_model(auth_client, task="classification")

    mock_client = _mock_httpx_post(MOCK_CLASSIFY_RESULT)

    with patch("app.api.predictions.httpx.AsyncClient", return_value=mock_client):
        res = await auth_client.post("/api/v1/predictions/batch-classify", json={
            "experiment_ids": [eid1],
        })

    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["label"] == "stable"
    assert data["failed"] == []


@pytest.mark.asyncio
async def test_batch_classify_with_invalid_experiment(auth_client: AsyncClient):
    """Batch classify with a non-existent experiment should put it in failed."""
    await _create_model(auth_client, task="classification")

    mock_client = _mock_httpx_post(MOCK_CLASSIFY_RESULT)

    with patch("app.api.predictions.httpx.AsyncClient", return_value=mock_client):
        res = await auth_client.post("/api/v1/predictions/batch-classify", json={
            "experiment_ids": [99999],
        })

    assert res.status_code == 200
    data = res.json()
    assert len(data["failed"]) == 1
    assert data["failed"][0]["experiment_id"] == 99999


@pytest.mark.asyncio
async def test_batch_classify_no_model(auth_client: AsyncClient):
    """Batch classify without a model should return 404."""
    eid = await _load_experiment(auth_client)
    res = await auth_client.post("/api/v1/predictions/batch-classify", json={
        "experiment_ids": [eid],
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_batch_classify_unauthenticated(client: AsyncClient):
    """Batch classify should reject unauthenticated requests."""
    res = await client.post("/api/v1/predictions/batch-classify", json={
        "experiment_ids": [1],
    })
    assert res.status_code in (401, 403)


# ────────────────────────────────────────────────────────────────
# New tests — batch disruption
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch_disruption_success(auth_client: AsyncClient):
    """Batch disruption should return results for valid experiments."""
    eid = await _load_experiment(auth_client)
    await _create_model(auth_client, task="disruption_prediction")

    mock_client = _mock_httpx_post(MOCK_DISRUPTION_RESULT)

    with patch("app.api.predictions.httpx.AsyncClient", return_value=mock_client):
        res = await auth_client.post("/api/v1/predictions/batch-disruption", json={
            "experiment_ids": [eid],
        })

    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["warning_issued"] is True
    assert data["failed"] == []


@pytest.mark.asyncio
async def test_batch_disruption_with_invalid_experiment(auth_client: AsyncClient):
    """Batch disruption with non-existent experiment should report failure."""
    await _create_model(auth_client, task="disruption_prediction")

    mock_client = _mock_httpx_post(MOCK_DISRUPTION_RESULT)

    with patch("app.api.predictions.httpx.AsyncClient", return_value=mock_client):
        res = await auth_client.post("/api/v1/predictions/batch-disruption", json={
            "experiment_ids": [99999],
        })

    assert res.status_code == 200
    data = res.json()
    assert len(data["failed"]) == 1


@pytest.mark.asyncio
async def test_batch_disruption_unauthenticated(client: AsyncClient):
    """Batch disruption should reject unauthenticated requests."""
    res = await client.post("/api/v1/predictions/batch-disruption", json={
        "experiment_ids": [1],
    })
    assert res.status_code in (401, 403)


# ────────────────────────────────────────────────────────────────
# New tests — threshold GET/PUT
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_threshold_default(auth_client: AsyncClient):
    """GET /threshold should return default threshold when no settings exist."""
    res = await auth_client.get("/api/v1/predictions/threshold")
    assert res.status_code == 200
    data = res.json()
    assert data["threshold"] == 0.7
    assert data["notification_enabled"] is True


@pytest.mark.asyncio
async def test_put_threshold(auth_client: AsyncClient):
    """PUT /threshold should update the user's threshold."""
    res = await auth_client.put("/api/v1/predictions/threshold", json={
        "threshold": 0.5,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["threshold"] == 0.5


@pytest.mark.asyncio
async def test_put_threshold_then_get(auth_client: AsyncClient):
    """After PUT, GET should reflect the updated threshold."""
    await auth_client.put("/api/v1/predictions/threshold", json={
        "threshold": 0.3,
    })
    res = await auth_client.get("/api/v1/predictions/threshold")
    assert res.status_code == 200
    assert res.json()["threshold"] == 0.3


@pytest.mark.asyncio
async def test_put_threshold_negative_rejected(auth_client: AsyncClient):
    """Negative threshold should be rejected."""
    res = await auth_client.put("/api/v1/predictions/threshold", json={"threshold": -0.1})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_put_threshold_invalid_range(auth_client: AsyncClient):
    """Threshold outside [0, 1] should be rejected."""
    res = await auth_client.put("/api/v1/predictions/threshold", json={"threshold": 2.0})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_threshold_unauthenticated(client: AsyncClient):
    """GET /threshold should reject unauthenticated requests."""
    res = await client.get("/api/v1/predictions/threshold")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_put_threshold_unauthenticated(client: AsyncClient):
    """PUT /threshold should reject unauthenticated requests."""
    res = await client.put("/api/v1/predictions/threshold", json={"threshold": 0.5})
    assert res.status_code in (401, 403)
