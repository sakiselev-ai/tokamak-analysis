from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://tokamak:changeme_in_production@localhost:5432/tokamak_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin123"
    minio_bucket_models: str = "models"
    minio_bucket_data: str = "data"
    minio_secure: bool = False

    # JWT
    jwt_secret_key: str = "changeme_jwt_secret_key_in_production"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # ML Service
    ml_service_url: str = "http://ml-service:8001"

    # FAIR-MAST
    fair_mast_s3_endpoint: str = "https://s3.echo.stfc.ac.uk"
    fair_mast_bucket: str = "mast"

    # App
    app_env: str = "development"
    app_debug: bool = True
    backend_cors_origins: str = "http://localhost:3000,http://localhost:80"

    # Rate limiting
    rate_limit_per_minute: int = 100

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
