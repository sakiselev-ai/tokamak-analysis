from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    model_id: Mapped[int] = mapped_column(ForeignKey("ml_models.id"), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experiment = relationship("Experiment", back_populates="predictions")
    model = relationship("MLModel", back_populates="predictions")
