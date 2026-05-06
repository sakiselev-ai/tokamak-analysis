from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ml_client import MLServiceClient


@pytest.fixture
def ml_client():
    return MLServiceClient()


def _mock_httpx_response(json_data: dict, status_code: int = 200):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


def _mock_async_client(response):
    """Create a mock httpx.AsyncClient context manager."""
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_classify(ml_client):
    """classify should POST to ML service and return result."""
    response = _mock_httpx_response({"label": "stable", "confidence": 0.9})
    mock_client = _mock_async_client(response)

    with patch("app.services.ml_client.httpx.AsyncClient", return_value=mock_client):
        result = await ml_client.classify(
            data={"signals": {}}, model_path="model.pt", model_type="random_forest"
        )

    assert result["label"] == "stable"
    assert result["confidence"] == 0.9


@pytest.mark.asyncio
async def test_predict_disruption(ml_client):
    """predict_disruption should POST to ML service and return result."""
    disruption_result = {
        "timestamps": [0.0, 0.1],
        "probabilities": [0.3, 0.8],
        "warning_issued": True,
    }
    response = _mock_httpx_response(disruption_result)
    mock_client = _mock_async_client(response)

    with patch("app.services.ml_client.httpx.AsyncClient", return_value=mock_client):
        result = await ml_client.predict_disruption(
            data={"signals": {}}, model_path="model.pt", model_type="random_forest", threshold=0.7
        )

    assert result["warning_issued"] is True
    assert len(result["probabilities"]) == 2


@pytest.mark.asyncio
async def test_train(ml_client):
    """train should POST to ML service and return result."""
    train_result = {"model_path": "/tmp/model.pt", "metrics": {"accuracy": 0.95}}
    response = _mock_httpx_response(train_result)
    mock_client = _mock_async_client(response)

    with patch("app.services.ml_client.httpx.AsyncClient", return_value=mock_client):
        result = await ml_client.train(
            model_type="random_forest",
            task="classification",
            hyperparameters={"n_estimators": 100},
            shot_ids=[30420],
        )

    assert result["metrics"]["accuracy"] == 0.95


@pytest.mark.asyncio
async def test_health_success(ml_client):
    """health should return True when ML service responds 200."""
    response = _mock_httpx_response({}, status_code=200)
    mock_client = _mock_async_client(response)

    with patch("app.services.ml_client.httpx.AsyncClient", return_value=mock_client):
        result = await ml_client.health()

    assert result is True


@pytest.mark.asyncio
async def test_health_failure(ml_client):
    """health should return False when ML service is unreachable."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ml_client.httpx.AsyncClient", return_value=mock_client):
        result = await ml_client.health()

    assert result is False
