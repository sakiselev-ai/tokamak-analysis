from __future__ import annotations

import asyncio
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
from app.models.user_settings import UserSettings
from app.schemas.prediction import (
    BatchClassifyRequest,
    BatchClassifyResponse,
    BatchDisruptionRequest,
    BatchDisruptionResponse,
    ClassifyRequest,
    ClassifyResponse,
    DisruptionPredictRequest,
    DisruptionPredictResponse,
    ThresholdResponse,
    ThresholdUpdateRequest,
)
from app.services.recommendations import generate_recommendations

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

    recommendations = generate_recommendations(result, threshold=data.threshold)

    return DisruptionPredictResponse(
        experiment_id=data.experiment_id,
        timestamps=result["timestamps"],
        probabilities=result["probabilities"],
        warning_issued=result["warning_issued"],
        warning_time_ms=result.get("warning_time_ms"),
        inference_time_ms=inference_time,
        model_id=model.id,
        recommendations=recommendations,
    )


@router.post("/batch-classify", response_model=BatchClassifyResponse)
async def batch_classify(
    data: BatchClassifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await _get_model(data.model_id, ModelTask.CLASSIFICATION, db)
    results: list[ClassifyResponse] = []
    failed: list[dict] = []

    async def _classify_single(experiment_id: int) -> None:
        try:
            experiment_data = await _get_experiment_data(experiment_id, current_user.id, db)
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.ml_service_url}/api/v1/predict/classify",
                    json={
                        "data": experiment_data,
                        "model_path": model.s3_path,
                        "model_type": model.model_type.value,
                    },
                )
                response.raise_for_status()
                result = response.json()
            inference_time = (time.perf_counter() - start) * 1000

            prediction = Prediction(
                experiment_id=experiment_id,
                model_id=model.id,
                result_json=result,
                probability=result.get("confidence"),
            )
            db.add(prediction)
            await db.flush()

            results.append(ClassifyResponse(
                experiment_id=experiment_id,
                label=result["label"],
                confidence=result["confidence"],
                inference_time_ms=inference_time,
                model_id=model.id,
            ))
        except Exception as e:
            failed.append({"experiment_id": experiment_id, "error": str(e)})

    tasks = [_classify_single(eid) for eid in data.experiment_ids]
    await asyncio.gather(*tasks, return_exceptions=False)

    return BatchClassifyResponse(results=results, failed=failed)


@router.post("/batch-disruption", response_model=BatchDisruptionResponse)
async def batch_predict_disruption(
    data: BatchDisruptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await _get_model(data.model_id, ModelTask.DISRUPTION_PREDICTION, db)
    results: list[DisruptionPredictResponse] = []
    failed: list[dict] = []

    async def _predict_single(experiment_id: int) -> None:
        try:
            experiment_data = await _get_experiment_data(experiment_id, current_user.id, db)
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
                experiment_id=experiment_id,
                model_id=model.id,
                result_json=result,
                probability=result.get("max_probability"),
            )
            db.add(prediction)
            await db.flush()

            recommendations = generate_recommendations(result, threshold=data.threshold)

            results.append(DisruptionPredictResponse(
                experiment_id=experiment_id,
                timestamps=result["timestamps"],
                probabilities=result["probabilities"],
                warning_issued=result["warning_issued"],
                warning_time_ms=result.get("warning_time_ms"),
                inference_time_ms=inference_time,
                model_id=model.id,
                recommendations=recommendations,
            ))
        except Exception as e:
            failed.append({"experiment_id": experiment_id, "error": str(e)})

    tasks = [_predict_single(eid) for eid in data.experiment_ids]
    await asyncio.gather(*tasks, return_exceptions=False)

    return BatchDisruptionResponse(results=results, failed=failed)


@router.put("/threshold", response_model=ThresholdResponse)
async def update_threshold(
    data: ThresholdUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = result.scalar_one_or_none()

    if user_settings is None:
        user_settings = UserSettings(
            user_id=current_user.id,
            disruption_threshold=data.threshold,
        )
        db.add(user_settings)
    else:
        user_settings.disruption_threshold = data.threshold

    await db.flush()

    return ThresholdResponse(
        threshold=user_settings.disruption_threshold,
        notification_enabled=user_settings.notification_enabled,
        updated_at=user_settings.updated_at.isoformat() if user_settings.updated_at else None,
    )


@router.get("/threshold", response_model=ThresholdResponse)
async def get_threshold(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = result.scalar_one_or_none()

    if user_settings is None:
        return ThresholdResponse(threshold=0.7, notification_enabled=True)

    return ThresholdResponse(
        threshold=user_settings.disruption_threshold,
        notification_enabled=user_settings.notification_enabled,
        updated_at=user_settings.updated_at.isoformat() if user_settings.updated_at else None,
    )
