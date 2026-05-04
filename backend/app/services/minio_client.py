from __future__ import annotations

from minio import Minio

from app.config import settings


class MinIOService:
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_secure,
        )
        self._ensure_buckets()

    def _ensure_buckets(self) -> None:
        for bucket in [settings.minio_bucket_models, settings.minio_bucket_data]:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)

    def upload_model(self, local_path: str, model_name: str, version: str) -> str:
        object_name = f"{model_name}/{version}/{model_name}.artifact"
        self.client.fput_object(settings.minio_bucket_models, object_name, local_path)
        return object_name

    def download_model(self, object_name: str, local_path: str) -> str:
        self.client.fget_object(settings.minio_bucket_models, object_name, local_path)
        return local_path

    def list_model_versions(self, model_name: str) -> list[str]:
        objects = self.client.list_objects(
            settings.minio_bucket_models, prefix=f"{model_name}/", recursive=True
        )
        return [obj.object_name for obj in objects]

    def delete_model(self, object_name: str) -> None:
        self.client.remove_object(settings.minio_bucket_models, object_name)
