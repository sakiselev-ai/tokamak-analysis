from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_minio():
    """Mock Minio client so no real connection is needed."""
    with patch("app.services.minio_client.Minio") as MockMinio:
        client = MockMinio.return_value
        client.bucket_exists.return_value = True  # buckets already exist
        yield client


def _create_service(mock_minio):
    """Create MinIOService with mocked Minio client."""
    from app.services.minio_client import MinIOService
    svc = MinIOService.__new__(MinIOService)
    svc.client = mock_minio
    return svc


def test_ensure_buckets_creates_missing(mock_minio):
    """_ensure_buckets should create buckets that don't exist."""
    mock_minio.bucket_exists.return_value = False
    from app.services.minio_client import MinIOService
    svc = MinIOService.__new__(MinIOService)
    svc.client = mock_minio
    svc._ensure_buckets()
    assert mock_minio.make_bucket.call_count == 2  # models + data


def test_ensure_buckets_skips_existing(mock_minio):
    """_ensure_buckets should not create buckets that already exist."""
    mock_minio.bucket_exists.return_value = True
    svc = _create_service(mock_minio)
    svc._ensure_buckets()
    mock_minio.make_bucket.assert_not_called()


def test_upload_model(mock_minio):
    """upload_model should call fput_object with the correct path."""
    svc = _create_service(mock_minio)
    result = svc.upload_model("/tmp/model.pt", "lstm_attention", "v1.0")
    assert "lstm_attention" in result
    assert "v1.0" in result
    mock_minio.fput_object.assert_called_once()


def test_download_model(mock_minio):
    """download_model should call fget_object."""
    svc = _create_service(mock_minio)
    result = svc.download_model("lstm_attention/v1.0/lstm_attention.artifact", "/tmp/model.pt")
    assert result == "/tmp/model.pt"
    mock_minio.fget_object.assert_called_once()


def test_list_model_versions(mock_minio):
    """list_model_versions should return object names."""
    mock_obj1 = MagicMock()
    mock_obj1.object_name = "rf/v1/rf.artifact"
    mock_obj2 = MagicMock()
    mock_obj2.object_name = "rf/v2/rf.artifact"
    mock_minio.list_objects.return_value = [mock_obj1, mock_obj2]

    svc = _create_service(mock_minio)
    versions = svc.list_model_versions("rf")
    assert len(versions) == 2
    assert "rf/v1/rf.artifact" in versions
    assert "rf/v2/rf.artifact" in versions


def test_delete_model(mock_minio):
    """delete_model should call remove_object."""
    svc = _create_service(mock_minio)
    svc.delete_model("rf/v1/rf.artifact")
    mock_minio.remove_object.assert_called_once()
