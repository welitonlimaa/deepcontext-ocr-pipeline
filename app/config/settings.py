import os
from dataclasses import dataclass


@dataclass
class Settings:
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_job_ttl: int = 86400  # 24h

    # MinIO
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "ocr-pipeline")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # Pipeline
    chunk_size_pages: int = int(os.getenv("CHUNK_SIZE_PAGES", "10"))
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "200"))

    # Celery
    celery_broker: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_backend: str = os.getenv("REDIS_URL", "redis://localhost:6379/1")


settings = Settings()
