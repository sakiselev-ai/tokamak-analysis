from __future__ import annotations

import httpx

from app.config import settings


class MLServiceClient:
    """HTTP client for ML service communication."""

    def __init__(self):
        self.base_url = settings.ml_service_url

    async def classify(self, data: dict, model_path: str, model_type: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/predict/classify",
                json={"data": data, "model_path": model_path, "model_type": model_type},
            )
            response.raise_for_status()
            return response.json()

    async def predict_disruption(
        self, data: dict, model_path: str, model_type: str, threshold: float = 0.7
    ) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/predict/disruption",
                json={
                    "data": data,
                    "model_path": model_path,
                    "model_type": model_type,
                    "threshold": threshold,
                },
            )
            response.raise_for_status()
            return response.json()

    async def train(self, model_type: str, task: str, hyperparameters: dict, shot_ids: list[int]) -> dict:
        async with httpx.AsyncClient(timeout=3600.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/train",
                json={
                    "model_type": model_type,
                    "task": task,
                    "hyperparameters": hyperparameters,
                    "shot_ids": shot_ids,
                },
            )
            response.raise_for_status()
            return response.json()

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
