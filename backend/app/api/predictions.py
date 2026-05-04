from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.experiment import Experiment, TimeSeriesData
from app.models.ml_model import MLModel, ModelTask
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.prediction import (
    ClassifyRequest,
    ClassifyResponse,
    DisruptionPredictRequest,
    DisruptionPredictResponse,
)

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


async def _get_experiment_data(experiment_id: int, user_id: int, db: AsyncSession) -> dict:
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id, Experiment.user_id == user_id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    ts_result = await db.execute(
        select(TimeSeriesData).where(TimeSeriesData.experiment_id == experiment_id)
    )
    timeseries = ts_result.scalars().all()

    return {
        "shot_id": experiment.shot_id,
        "signals": {
            ts.parameter_name: {"timestamps": ts.timestamps, "values": ts.values}
            for ts in timeseries
        },
    }


async def _get_model(model_id: int | None, task: ModelTask, db: AsyncSession) -> MLModel:
    if model_id:
        result = await db.execute(select(MLModel).where(MLModel.id == model_id, MLModel.is_active.is_(True)))
    else:
        result = await db.execute(
            select(MLModel)
            .where(MLModel.task == task, MLModel.is_active.is_(True))
            .order_by(MLModel.created_at.desc())
            .limit(1)
        )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No trained model available")
    return model


@router.post("/classify", response_model=ClassifyResponse)
async def classify(
    data: ClassifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    experiment_data = await _get_experiment_data(data.experiment_id, current_user.id, db)
    model = await _get_model(data.model_id, ModelTask.CLASSIFICATION, db)

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.ml_service_url}/api/v1/predict/classify",
            json={"data": experiment_data, "model_path": model.s3_path, "model_type": model.model_type.value},
        )
        response.raise_for_status()
        result = response.json()
    inference_time = (time.perf_counter() - start) * 1000

    prediction = Prediction(
        experiment_id=data.experiment_id,
        model_id=model.id,
        result_json=result,
        probability=result.get("confidence"),
    )
    db.add(prediction)
    await db.flush()

    return ClassifyResponse(
        experiment_id=data.experiment_id,
        label=result["label"],
        confidence=result["confidence"],
        inference_time_ms=inference_time,
        model_id=model.id,
    )


@router.post("/disruption", response_model=DisruptionPredictResponse)
async def predict_disruption(
    data: DisruptionPredictRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    experiment_data = await _get_experiment_data(data.experiment_id, current_user.id, db)
    model = await _get_model(data.model_id, ModelTask.DISRUPTION_PREDICTION, db)

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.ml_service_url}/api/v1/predict/disruption",
            json={
                "data": experiment_data,
                "model_path": model.s3_path,
                "model_type": model.model_type.value,
                "threshold": data.threshold,
            },
        )
        response.raise_for_status()
        result = response.json()
    inference_time = (time.perf_counter() - start) * 1000

    prediction = Prediction(
        experiment_id=data.experiment_id,
        model_id=model.id,
        result_json=result,
        probability=result.get("max_probability"),
    )
    db.add(prediction)
    await db.flush()

    return DisruptionPredictResponse(
        experiment_id=data.experiment_id,
        timestamps=result["timestamps"],
        probabilities=result["probabilities"],
        warning_issued=result["warning_issued"],
        warning_time_ms=result.get("warning_time_ms"),
        inference_time_ms=inference_time,
        model_id=model.id,
    )
