from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.experiment import ExperimentSource, ExperimentStatus


class ExperimentLoadRequest(BaseModel):
    shot_id: int = Field(gt=0, description="Shot identifier from FAIR-MAST")
    source: ExperimentSource = ExperimentSource.MAST


class TimeSeriesResponse(BaseModel):
    parameter_name: str
    timestamps: list[float]
    values: list[float]
    units: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class ExperimentResponse(BaseModel):
    id: int
    shot_id: int
    source: ExperimentSource
    status: ExperimentStatus
    metadata_json: dict | None = None
    loaded_at: datetime
    timeseries: list[TimeSeriesResponse] = []

    model_config = {"from_attributes": True}


class ExperimentListResponse(BaseModel):
    experiments: list[ExperimentResponse]
    total: int


class ExportRequest(BaseModel):
    format: str = Field(default="csv", pattern="^(csv|json)$")


class BatchLoadRequest(BaseModel):
    shot_ids: list[int] = Field(min_length=1, max_length=50)
    source: ExperimentSource = ExperimentSource.MAST


class BatchLoadResponse(BaseModel):
    experiments: list[ExperimentResponse]
    failed: list[dict]
    total_loaded: int
