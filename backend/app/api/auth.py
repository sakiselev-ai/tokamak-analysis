from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.audit import log_action
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.experiment import Experiment, TimeSeriesData
from app.models.ml_model import ModelRun
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.auth import (
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not data.consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо согласие на обработку персональных данных (152-ФЗ)",
        )

    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        consent_given_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    await log_action(db, "register", "user", user_id=user.id, request=request)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        await log_action(
            db, "login_failed", "auth",
            details={"email": data.email},
            request=request,
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    await log_action(db, "login", "auth", user_id=user.id, request=request)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.delete("/account", status_code=status.HTTP_200_OK)
async def delete_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete current user account and all associated data (152-ФЗ, ст. 21)."""
    user_id = current_user.id

    # Delete predictions linked to user's experiments
    user_experiment_ids = select(Experiment.id).where(Experiment.user_id == user_id)
    await db.execute(
        delete(Prediction).where(Prediction.experiment_id.in_(user_experiment_ids))
    )

    # Delete timeseries data linked to user's experiments
    await db.execute(
        delete(TimeSeriesData).where(TimeSeriesData.experiment_id.in_(user_experiment_ids))
    )

    # Delete user's experiments
    await db.execute(delete(Experiment).where(Experiment.user_id == user_id))

    # Delete user's model runs
    await db.execute(delete(ModelRun).where(ModelRun.user_id == user_id))

    # Delete user's audit logs
    await db.execute(delete(AuditLog).where(AuditLog.user_id == user_id))

    # Soft-delete the user account
    current_user.is_active = False
    current_user.deleted_at = datetime.now(timezone.utc)

    await log_action(
        db, "account_deleted", "user",
        user_id=user_id,
        details={"email": current_user.email},
        request=request,
    )
    await db.commit()

    return {"detail": "Аккаунт и все связанные данные удалены"}


@router.get("/export-data")
async def export_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all user personal data (152-ФЗ, ст. 14 / right to data portability)."""
    # Profile
    profile = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "consent_given_at": current_user.consent_given_at.isoformat() if current_user.consent_given_at else None,
    }

    # Experiments
    result = await db.execute(
        select(Experiment).where(Experiment.user_id == current_user.id)
    )
    experiments = result.scalars().all()
    experiments_data = [
        {
            "id": exp.id,
            "shot_id": exp.shot_id,
            "source": exp.source.value,
            "status": exp.status.value,
            "metadata": exp.metadata_json,
            "loaded_at": exp.loaded_at.isoformat() if exp.loaded_at else None,
        }
        for exp in experiments
    ]

    # Predictions linked to user's experiments
    experiment_ids = [exp.id for exp in experiments]
    predictions_data = []
    if experiment_ids:
        result = await db.execute(
            select(Prediction).where(Prediction.experiment_id.in_(experiment_ids))
        )
        predictions = result.scalars().all()
        predictions_data = [
            {
                "id": pred.id,
                "experiment_id": pred.experiment_id,
                "model_id": pred.model_id,
                "result": pred.result_json,
                "probability": pred.probability,
                "created_at": pred.created_at.isoformat() if pred.created_at else None,
            }
            for pred in predictions
        ]

    # Model runs
    result = await db.execute(
        select(ModelRun).where(ModelRun.user_id == current_user.id)
    )
    model_runs = result.scalars().all()
    model_runs_data = [
        {
            "id": run.id,
            "model_id": run.model_id,
            "status": run.status.value,
            "hyperparams": run.hyperparams_json,
            "metrics": run.metrics_json,
            "progress": run.progress,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
        for run in model_runs
    ]

    return {
        "profile": profile,
        "experiments": experiments_data,
        "predictions": predictions_data,
        "model_runs": model_runs_data,
    }
