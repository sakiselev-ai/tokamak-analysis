from __future__ import annotations

"""Initial schema – all tables.

Revision ID: 001
Revises: None
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

# Enum names used in the schema
userrole = sa.Enum("researcher", "engineer", "admin", name="userrole")
experimentsource = sa.Enum("mast", "jet", "diii_d", "local", name="experimentsource")
experimentstatus = sa.Enum("loading", "loaded", "preprocessed", "error", name="experimentstatus")
modeltype = sa.Enum("random_forest", "lstm_attention", "transformer", name="modeltype")
modeltask = sa.Enum("classification", "disruption_prediction", name="modeltask")
runstatus = sa.Enum("queued", "running", "completed", "failed", "cancelled", name="runstatus")


def upgrade() -> None:
    # Create enum types explicitly
    userrole.create(op.get_bind(), checkfirst=True)
    experimentsource.create(op.get_bind(), checkfirst=True)
    experimentstatus.create(op.get_bind(), checkfirst=True)
    modeltype.create(op.get_bind(), checkfirst=True)
    modeltask.create(op.get_bind(), checkfirst=True)
    runstatus.create(op.get_bind(), checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", userrole, nullable=False, server_default="researcher"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- experiments ---
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shot_id", sa.Integer, nullable=False, index=True),
        sa.Column("source", experimentsource, nullable=False, server_default="mast"),
        sa.Column("status", experimentstatus, nullable=False, server_default="loading"),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_experiments_user_id", "experiments", ["user_id"])

    # --- timeseries_data ---
    op.create_table(
        "timeseries_data",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "experiment_id",
            sa.Integer,
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parameter_name", sa.String(100), nullable=False),
        sa.Column("timestamps", sa.JSON, nullable=False),
        sa.Column("values", sa.JSON, nullable=False),
        sa.Column("units", sa.String(50), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
    )
    op.create_index("ix_timeseries_data_experiment_id", "timeseries_data", ["experiment_id"])

    # --- ml_models ---
    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("model_type", modeltype, nullable=False),
        sa.Column("task", modeltask, nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0.0"),
        sa.Column("s3_path", sa.String(500), nullable=True),
        sa.Column("metrics_json", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- model_runs ---
    op.create_table(
        "model_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("model_id", sa.Integer, sa.ForeignKey("ml_models.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", runstatus, nullable=False, server_default="queued"),
        sa.Column("hyperparams_json", sa.JSON, nullable=True),
        sa.Column("metrics_json", sa.JSON, nullable=True),
        sa.Column("progress", sa.Float, nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_model_runs_model_id", "model_runs", ["model_id"])
    op.create_index("ix_model_runs_user_id", "model_runs", ["user_id"])

    # --- predictions ---
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.Integer, sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("model_id", sa.Integer, sa.ForeignKey("ml_models.id"), nullable=False),
        sa.Column("result_json", sa.JSON, nullable=False),
        sa.Column("probability", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_predictions_experiment_id", "predictions", ["experiment_id"])
    op.create_index("ix_predictions_model_id", "predictions", ["model_id"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource", sa.String(255), nullable=False),
        sa.Column("details_json", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("predictions")
    op.drop_table("model_runs")
    op.drop_table("ml_models")
    op.drop_table("timeseries_data")
    op.drop_table("experiments")
    op.drop_table("users")

    runstatus.drop(op.get_bind(), checkfirst=True)
    modeltask.drop(op.get_bind(), checkfirst=True)
    modeltype.drop(op.get_bind(), checkfirst=True)
    experimentstatus.drop(op.get_bind(), checkfirst=True)
    experimentsource.drop(op.get_bind(), checkfirst=True)
    userrole.drop(op.get_bind(), checkfirst=True)
