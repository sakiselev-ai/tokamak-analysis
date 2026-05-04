from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery("tokamak", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, name="train_model")
def train_model_task(self, run_id: int, model_type: str, task: str, hyperparameters: dict, shot_ids: list[int]):
    """Background task for model training.

    This task communicates with the ML service to train the model,
    and updates the ModelRun status in the database.
    """
    import asyncio
    import httpx

    async def _train():
        self.update_state(state="PROGRESS", meta={"progress": 0, "run_id": run_id})

        async with httpx.AsyncClient(timeout=3600.0) as client:
            response = await client.post(
                f"{settings.ml_service_url}/api/v1/train",
                json={
                    "model_type": model_type,
                    "task": task,
                    "hyperparameters": hyperparameters or {},
                    "shot_ids": shot_ids or [],
                    "run_id": run_id,
                },
            )
            response.raise_for_status()
            return response.json()

    result = asyncio.run(_train())
    return {"run_id": run_id, "result": result}
