from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.models.ml_model import MLModel, ModelRun, RunStatus


class TestUpdateRunStatus:
    """Test _update_run_status helper function."""

    def _mock_session(self, run: ModelRun | None, model: MLModel | None = None):
        """Create a mock SyncSession context manager."""
        session = MagicMock()

        def _get(model_class, id_):
            if model_class is ModelRun:
                return run
            if model_class is MLModel:
                return model
            return None

        session.get = MagicMock(side_effect=_get)
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    def test_update_status_basic(self):
        """Should update run status."""
        run = MagicMock(spec=ModelRun)
        run.model_id = 1
        session = self._mock_session(run)

        with patch("app.tasks.training.SyncSession", return_value=session):
            from app.tasks.training import _update_run_status
            _update_run_status(1, RunStatus.RUNNING)

        assert run.status == RunStatus.RUNNING
        session.commit.assert_called_once()

    def test_update_with_metrics_and_s3_path(self):
        """Should update metrics and propagate s3_path to parent model."""
        run = MagicMock(spec=ModelRun)
        run.model_id = 1
        model = MagicMock(spec=MLModel)
        session = self._mock_session(run, model)

        with patch("app.tasks.training.SyncSession", return_value=session):
            from app.tasks.training import _update_run_status
            _update_run_status(
                1, RunStatus.COMPLETED,
                metrics={"accuracy": 0.95},
                s3_path="models/rf/v1",
                progress=100.0,
                finished_at=datetime.now(timezone.utc),
            )

        assert run.status == RunStatus.COMPLETED
        assert run.metrics_json == {"accuracy": 0.95}
        assert run.progress == 100.0
        assert model.s3_path == "models/rf/v1"
        assert model.metrics_json == {"accuracy": 0.95}

    def test_update_run_not_found(self):
        """Should log error when run is not found."""
        session = self._mock_session(None)

        with patch("app.tasks.training.SyncSession", return_value=session):
            from app.tasks.training import _update_run_status
            # Should not raise
            _update_run_status(999, RunStatus.RUNNING)

        session.commit.assert_not_called()

    def test_update_with_started_at(self):
        """Should update started_at timestamp."""
        run = MagicMock(spec=ModelRun)
        run.model_id = 1
        session = self._mock_session(run)
        now = datetime.now(timezone.utc)

        with patch("app.tasks.training.SyncSession", return_value=session):
            from app.tasks.training import _update_run_status
            _update_run_status(1, RunStatus.RUNNING, started_at=now)

        assert run.started_at == now


def _mock_http_client(response_json: dict):
    """Create a mock httpx.Client context manager."""
    mock_response = MagicMock()
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()

    client = MagicMock()
    client.post.return_value = mock_response
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


class TestTrainModelTask:
    """Test the Celery train_model_task."""

    def test_train_success(self):
        """Successful training should update run status to COMPLETED."""
        mock_http = _mock_http_client({
            "model_path": "/tmp/model.pt",
            "metrics": {"accuracy": 0.95},
        })

        mock_minio = MagicMock()
        mock_minio.upload_model.return_value = "models/rf/v1/rf.artifact"

        with patch("app.tasks.training._update_run_status") as mock_update, \
             patch("app.tasks.training.httpx.Client", return_value=mock_http), \
             patch("app.tasks.training.MinIOService", return_value=mock_minio):
            from app.tasks.training import train_model_task
            # Use .run() which is the bound method for celery tasks with bind=True
            # But we need to mock self (the task instance)
            task = train_model_task
            task.update_state = MagicMock()
            task.retry = MagicMock()
            result = task(1, "random_forest", "classification", None, None)

        assert result["status"] == "completed"
        assert result["metrics"] == {"accuracy": 0.95}
        assert result["s3_path"] == "models/rf/v1/rf.artifact"
        assert mock_update.call_count >= 2

    def test_train_success_no_model_path(self):
        """When ML service doesn't return model_path, s3_path should be None."""
        mock_http = _mock_http_client({"metrics": {"accuracy": 0.90}})

        with patch("app.tasks.training._update_run_status"), \
             patch("app.tasks.training.httpx.Client", return_value=mock_http):
            from app.tasks.training import train_model_task
            task = train_model_task
            task.update_state = MagicMock()
            task.retry = MagicMock()
            result = task(1, "random_forest", "classification", None, None)

        assert result["s3_path"] is None

    def test_train_failure(self):
        """Failed training should update run status to FAILED and retry."""
        mock_http = MagicMock()
        mock_http.post.side_effect = Exception("ML service down")
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)

        with patch("app.tasks.training._update_run_status") as mock_update, \
             patch("app.tasks.training.httpx.Client", return_value=mock_http):
            from app.tasks.training import train_model_task
            task = train_model_task
            task.update_state = MagicMock()
            task.retry = MagicMock(side_effect=Exception("Retry"))

            with pytest.raises(Exception, match="Retry"):
                task(1, "random_forest", "classification", None, None)

        calls = mock_update.call_args_list
        assert any(c.args[1] == RunStatus.FAILED for c in calls)

    def test_train_minio_upload_failure_continues(self):
        """MinIO upload failure should not fail the entire task."""
        mock_http = _mock_http_client({
            "model_path": "/tmp/model.pt",
            "metrics": {"accuracy": 0.95},
        })

        mock_minio = MagicMock()
        mock_minio.upload_model.side_effect = Exception("MinIO unreachable")

        with patch("app.tasks.training._update_run_status"), \
             patch("app.tasks.training.httpx.Client", return_value=mock_http), \
             patch("app.tasks.training.MinIOService", return_value=mock_minio):
            from app.tasks.training import train_model_task
            task = train_model_task
            task.update_state = MagicMock()
            task.retry = MagicMock()
            result = task(1, "random_forest", "classification", None, None)

        assert result["status"] == "completed"
        assert result["s3_path"] is None
