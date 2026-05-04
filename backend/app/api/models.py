from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.ml_model import MLModel, ModelRun, ModelTask, ModelType, RunStatus
from app.models.user import User
from app.schemas.prediction import ModelRunResponse, TrainRequest, TrainResponse

router = APIRouter(prefix="/api/v1/models", tags=["models"])


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

    # TODO: dispatch Celery task
    # from app.tasks.training import train_model_task
    # task = train_model_task.delay(run.id, data.model_type, data.task, data.hyperparameters, data.dataset_shot_ids)
    # run.celery_task_id = task.id

    return TrainResponse(
        run_id=run.id,
        model_id=model.id,
        status=run.status.value,
        celery_task_id=run.celery_task_id,
    )


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
