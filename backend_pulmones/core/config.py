import tempfile
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    database_url: str = Field(validation_alias="DATABASE_URL")
    s3_endpoint_url: str = Field(validation_alias="S3_ENDPOINT_URL")
    s3_region: str = Field(validation_alias="S3_REGION")
    s3_bucket: str = Field(validation_alias="S3_BUCKET")
    s3_access_key_id: str = Field(validation_alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(validation_alias="S3_SECRET_ACCESS_KEY")
    runtime_dir: Path = Field(
        default=Path(tempfile.gettempdir()) / "pulmoscan",
        validation_alias="RUNTIME_DIR",
    )
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(
        default="gemini-2.0-flash", validation_alias="GEMINI_MODEL"
    )
    gemini_timeout: int = Field(default=30, validation_alias="GEMINI_TIMEOUT")
    gemini_max_retries: int = Field(default=2, validation_alias="GEMINI_MAX_RETRIES")
    gemini_max_reviews: int = Field(default=10, validation_alias="GEMINI_MAX_REVIEWS")
    gemini_max_workers: int = Field(default=5, validation_alias="GEMINI_MAX_WORKERS")
    public_api_url: str = Field(
        default="http://localhost:8001", validation_alias="PUBLIC_API_URL"
    )

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

RUNTIME_DIR = settings.runtime_dir
UPLOAD_DIR = RUNTIME_DIR / "uploads"
OUTPUT_DIR = RUNTIME_DIR / "outputs"
MODEL_PATH = BASE_DIR / "ai_model" / "modelo_entrenado.pth"
DATABASE_URL = settings.database_url.strip()
S3_ENDPOINT_URL = settings.s3_endpoint_url.strip().rstrip("/")
S3_REGION = settings.s3_region.strip()
S3_BUCKET = settings.s3_bucket.strip()
S3_ACCESS_KEY_ID = settings.s3_access_key_id.strip()
S3_SECRET_ACCESS_KEY = settings.s3_secret_access_key.strip()
GEMINI_API_KEY = settings.gemini_api_key.strip()
GEMINI_MODEL = settings.gemini_model
GEMINI_TIMEOUT = settings.gemini_timeout
GEMINI_MAX_RETRIES = settings.gemini_max_retries
GEMINI_MAX_REVIEWS = settings.gemini_max_reviews
GEMINI_MAX_WORKERS = settings.gemini_max_workers
PUBLIC_API_URL = settings.public_api_url
