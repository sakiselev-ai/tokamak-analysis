from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExperimentSource(str, enum.Enum):
    MAST = "mast"
    JET = "jet"
    DIII_D = "diii_d"
    LOCAL = "local"


class ExperimentStatus(str, enum.Enum):
    LOADING = "loading"
    LOADED = "loaded"
    PREPROCESSED = "preprocessed"
    ERROR = "error"


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shot_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source: Mapped[ExperimentSource] = mapped_column(Enum(ExperimentSource), default=ExperimentSource.MAST)
    status: Mapped[ExperimentStatus] = mapped_column(Enum(ExperimentStatus), default=ExperimentStatus.LOADING)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="experiments")
    timeseries = relationship("TimeSeriesData", back_populates="experiment", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="experiment")


class TimeSeriesData(Base):
    __tablename__ = "timeseries_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    parameter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamps: Mapped[dict] = mapped_column(JSON, nullable=False)  # list of floats
    values: Mapped[dict] = mapped_column(JSON, nullable=False)  # list of floats
    units: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    experiment = relationship("Experiment", back_populates="timeseries")
