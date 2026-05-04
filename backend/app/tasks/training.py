from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from celery import Celery

from app.config import settings
from app.models.ml_model import MLModel, ModelRun, RunStatus
from app.services.minio_client import MinIOService
from app.tasks.db_sync import SyncSession

logger = logging.getLogger(__name__)

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


def _update_run_status(
    run_id: int,
    status: RunStatus,
    *,
    metrics: dict | None = None,
    s3_path: str | None = None,
    progress: float | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> None:
    """Update a ModelRun record synchronously (for use inside Celery tasks)."""
    with SyncSession() as session:
        run = session.get(ModelRun, run_id)
        if run is None:
            logger.error("ModelRun %s not found", run_id)
            return
        run.status = status
        if metrics is not None:
            run.metrics_json = metrics
        if s3_path is not None:
            # Also update the parent MLModel's s3_path
            model = session.get(MLModel, run.model_id)
            if model:
                model.s3_path = s3_path
                model.metrics_json = metrics
        if progress is not None:
            run.progress = progress
        if started_at is not None:
            run.started_at = started_at
        if finished_at is not None:
            run.finished_at = finished_at
        session.commit()


@celery_app.task(bind=True, name="train_model")
def train_model_task(
    self,
    run_id: int,
    model_type: str,
    task: str,
    hyperparameters: dict | None,
    shot_ids: list[int] | None,
) -> dict:
    """Background task for model training.

    This task communicates with the ML service to train the model,
    and updates the ModelRun status in the database.
    """
    now = datetime.now(timezone.utc)

    # --- Mark RUNNING -------------------------------------------------------
    _update_run_status(run_id, RunStatus.RUNNING, progress=0.0, started_at=now)
    self.update_state(state="PROGRESS", meta={"progress": 0, "run_id": run_id})

    try:
        # --- Call ML service ------------------------------------------------
        with httpx.Client(timeout=3600.0) as client:
            response = client.post(
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
            result = response.json()

        self.update_state(state="PROGRESS", meta={"progress": 80, "run_id": run_id})

        # --- Upload model artifact to MinIO ---------------------------------
        s3_path: str | None = None
        model_file_path = result.get("model_path")

        if model_file_path:
            try:
                minio_svc = MinIOService()
                # Derive a version string from the run id + timestamp
                version = f"run-{run_id}-{now.strftime('%Y%m%dT%H%M%S')}"
                model_name = f"{model_type}_{task}"
                s3_path = minio_svc.upload_model(model_file_path, model_name, version)
                logger.info("Model uploaded to MinIO: %s", s3_path)
            except Exception:
                logger.exception("Failed to upload model to MinIO")

        # --- Mark COMPLETED -------------------------------------------------
        metrics = result.get("metrics")
        finished = datetime.now(timezone.utc)
        _update_run_status(
            run_id,
            RunStatus.COMPLETED,
            metrics=metrics,
            s3_path=s3_path,
            progress=100.0,
            finished_at=finished,
        )

        return {"run_id": run_id, "status": "completed", "metrics": metrics, "s3_path": s3_path}

    except Exception as exc:
        logger.exception("Training task failed for run %s", run_id)
        _update_run_status(
            run_id,
            RunStatus.FAILED,
            progress=None,
            finished_at=datetime.now(timezone.utc),
        )
        raise self.retry(exc=exc, max_retries=0)
