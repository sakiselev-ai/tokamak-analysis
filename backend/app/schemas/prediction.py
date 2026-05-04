from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    experiment_id: int
    model_id: int | None = None


class DisruptionPredictRequest(BaseModel):
    experiment_id: int
    model_id: int | None = None
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class ClassifyResponse(BaseModel):
    experiment_id: int
    label: str  # "stable" | "unstable"
    confidence: float
    inference_time_ms: float
    model_id: int


class DisruptionPredictResponse(BaseModel):
    experiment_id: int
    timestamps: list[float]
    probabilities: list[float]
    warning_issued: bool
    warning_time_ms: float | None = None
    inference_time_ms: float
    model_id: int
    recommendations: list[dict] = []


class TrainRequest(BaseModel):
    model_type: str = Field(pattern="^(random_forest|lstm_attention|transformer)$")
    task: str = Field(default="classification", pattern="^(classification|disruption_prediction)$")
    hyperparameters: dict | None = None
    dataset_shot_ids: list[int] | None = None


class TrainResponse(BaseModel):
    run_id: int
    model_id: int
    status: str
    celery_task_id: str | None = None


class BatchClassifyRequest(BaseModel):
    experiment_ids: list[int] = Field(min_length=1, max_length=50)
    model_id: int | None = None


class BatchClassifyResponse(BaseModel):
    results: list[ClassifyResponse]
    failed: list[dict]


class BatchDisruptionRequest(BaseModel):
    experiment_ids: list[int] = Field(min_length=1, max_length=50)
    model_id: int | None = None
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class BatchDisruptionResponse(BaseModel):
    results: list[DisruptionPredictResponse]
    failed: list[dict]


class ThresholdUpdateRequest(BaseModel):
    threshold: float = Field(ge=0.0, le=1.0)


class ThresholdResponse(BaseModel):
    threshold: float
    notification_enabled: bool
    updated_at: str | None = None


class ModelRunResponse(BaseModel):
    id: int
    model_id: int
    status: str
    hyperparams_json: dict | None
    metrics_json: dict | None
    progress: float | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
