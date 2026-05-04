from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.ml_model import MLModel, ModelRun, ModelTask, ModelType, RunStatus
from app.models.user import User
from app.schemas.prediction import ModelRunResponse, TrainRequest, TrainResponse
from app.tasks.training import celery_app, train_model_task

router = APIRouter(prefix="/api/v1/models", tags=["models"])


# ---------------------------------------------------------------------------
# Schemas for new endpoints
# ---------------------------------------------------------------------------

class ModelResponse(BaseModel):
    id: int
    name: str
    model_type: str
    task: str
    version: str
    s3_path: str | None = None
    metrics_json: dict | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class ModelVersionResponse(BaseModel):
    id: int
    name: str
    version: str
    s3_path: str | None = None
    metrics_json: dict | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class TrainingStatusResponse(BaseModel):
    run_id: int
    celery_task_id: str | None = None
    state: str
    progress: float | None = None
    status: str
    info: dict | None = None


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------

@router.post("/train", response_model=TrainResponse, status_code=status.HTTP_202_ACCEPTED)
async def train_model(
    data: TrainRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model_type = ModelType(data.model_type)
    task = ModelTask(data.task)

    result = await db.execute(
        select(MLModel)
        .where(MLModel.model_type == model_type, MLModel.task == task)
        .order_by(MLModel.created_at.desc())
        .limit(1)
    )
    model = result.scalar_one_or_none()

    if not model:
        model = MLModel(
            name=f"{data.model_type}_{data.task}",
            model_type=model_type,
            task=task,
        )
        db.add(model)
        await db.flush()

    run = ModelRun(
        model_id=model.id,
        user_id=current_user.id,
        status=RunStatus.QUEUED,
        hyperparams_json=data.hyperparameters,
    )
    db.add(run)
    await db.flush()

    # Dispatch Celery task
    celery_result = train_model_task.delay(
        run.id, data.model_type, data.task, data.hyperparameters, data.dataset_shot_ids
    )
    run.celery_task_id = celery_result.id

    return TrainResponse(
        run_id=run.id,
        model_id=model.id,
        status=run.status.value,
        celery_task_id=run.celery_task_id,
    )


# ---------------------------------------------------------------------------
# Model listing and versioning
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ModelResponse])
async def list_models(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all models with their latest version."""
    result = await db.execute(
        select(MLModel).order_by(MLModel.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{model_id}/versions", response_model=list[ModelVersionResponse])
async def list_model_versions(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all versions of a specific model."""
    result = await db.execute(
        select(MLModel).where(MLModel.id == model_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    # All models sharing the same type and task are treated as versions of one logical model
    result = await db.execute(
        select(MLModel)
        .where(MLModel.model_type == model.model_type, MLModel.task == model.task)
        .order_by(MLModel.created_at.desc())
    )
    return result.scalars().all()


@router.put("/{model_id}/activate", response_model=ModelResponse)
async def activate_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a model version as the active one (for rollback)."""
    result = await db.execute(select(MLModel).where(MLModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    # Deactivate all sibling versions (same type + task)
    siblings_result = await db.execute(
        select(MLModel).where(
            MLModel.model_type == model.model_type,
            MLModel.task == model.task,
        )
    )
    for sibling in siblings_result.scalars().all():
        sibling.is_active = False

    # Activate the requested one
    model.is_active = True

    return model


# ---------------------------------------------------------------------------
# Run endpoints
# ---------------------------------------------------------------------------

@router.get("/runs", response_model=list[ModelRunResponse])
async def list_runs(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ModelRun)
        .where(ModelRun.user_id == current_user.id)
        .order_by(ModelRun.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=ModelRunResponse)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ModelRun).where(ModelRun.id == run_id, ModelRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/runs/{run_id}/status", response_model=TrainingStatusResponse)
async def get_training_status(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get training progress by polling Celery task state."""
    result = await db.execute(
        select(ModelRun).where(ModelRun.id == run_id, ModelRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    response = TrainingStatusResponse(
        run_id=run.id,
        celery_task_id=run.celery_task_id,
        state="UNKNOWN",
        progress=run.progress,
        status=run.status.value,
    )

    if run.celery_task_id:
        async_result = celery_app.AsyncResult(run.celery_task_id)
        response.state = async_result.state or "UNKNOWN"

        if async_result.state == "PROGRESS":
            meta = async_result.info or {}
            response.progress = meta.get("progress")
            response.info = meta
        elif async_result.state == "SUCCESS":
            response.progress = 100.0
            response.info = async_result.result if isinstance(async_result.result, dict) else None
        elif async_result.state == "FAILURE":
            response.info = {"error": str(async_result.result)}

    return response
