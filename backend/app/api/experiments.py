from __future__ import annotations

import csv
import io
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_action
from app.core.security import get_current_user
from app.database import get_db
from app.models.experiment import Experiment, ExperimentStatus, TimeSeriesData
from app.models.user import User
from app.schemas.experiment import (
    ExperimentListResponse,
    ExperimentLoadRequest,
    ExperimentResponse,
    ExportRequest,
    TimeSeriesResponse,
)
from app.services.fair_mast import FairMastClient
from app.services.preprocessing import preprocess_timeseries

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


@router.post("/load", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def load_experiment(
    data: ExperimentLoadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    experiment = Experiment(
        shot_id=data.shot_id,
        source=data.source,
        status=ExperimentStatus.LOADING,
        user_id=current_user.id,
    )
    db.add(experiment)
    await db.flush()

    try:
        client = FairMastClient()
        signals = await client.load_shot(data.shot_id)

        for signal_name, signal_data in signals.items():
            ts, vals = preprocess_timeseries(signal_data["timestamps"], signal_data["values"])
            ts_record = TimeSeriesData(
                experiment_id=experiment.id,
                parameter_name=signal_name,
                timestamps=ts,
                values=vals,
                units=signal_data.get("units"),
                description=signal_data.get("description"),
            )
            db.add(ts_record)

        experiment.status = ExperimentStatus.PREPROCESSED
        experiment.metadata_json = {"signal_count": len(signals), "shot_id": data.shot_id}

    except Exception as e:
        experiment.status = ExperimentStatus.ERROR
        experiment.metadata_json = {"error": str(e)}
        await db.flush()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to load shot: {e}")

    await log_action(
        db, "load_experiment", "experiment",
        user_id=current_user.id,
        details={"shot_id": data.shot_id},
        request=request,
    )

    await db.flush()

    result = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.timeseries))
        .where(Experiment.id == experiment.id)
    )
    return result.scalar_one()


@router.get("/", response_model=ExperimentListResponse)
async def list_experiments(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Experiment)
        .where(Experiment.user_id == current_user.id)
        .order_by(Experiment.loaded_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    experiments = result.scalars().all()

    count_result = await db.execute(
        select(Experiment.id).where(Experiment.user_id == current_user.id)
    )
    total = len(count_result.all())

    return ExperimentListResponse(experiments=experiments, total=total)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.timeseries))
        .where(Experiment.id == experiment_id, Experiment.user_id == current_user.id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return experiment


@router.get("/{experiment_id}/timeseries", response_model=list[TimeSeriesResponse])
async def get_timeseries(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id, Experiment.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    ts_result = await db.execute(
        select(TimeSeriesData).where(TimeSeriesData.experiment_id == experiment_id)
    )
    return ts_result.scalars().all()


@router.get("/{experiment_id}/export")
async def export_experiment(
    experiment_id: int,
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.timeseries))
        .where(Experiment.id == experiment_id, Experiment.user_id == current_user.id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    if format == "json":
        data = {
            "shot_id": experiment.shot_id,
            "source": experiment.source.value,
            "signals": {
                ts.parameter_name: {
                    "timestamps": ts.timestamps,
                    "values": ts.values,
                    "units": ts.units,
                }
                for ts in experiment.timeseries
            },
        }
        return StreamingResponse(
            io.BytesIO(json.dumps(data, ensure_ascii=False).encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=shot_{experiment.shot_id}.json"},
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["parameter", "timestamp", "value", "units"])
    for ts in experiment.timeseries:
        for t, v in zip(ts.timestamps, ts.values):
            writer.writerow([ts.parameter_name, t, v, ts.units or ""])

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=shot_{experiment.shot_id}.csv"},
    )
