from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(PROJECT_ROOT / "backend" / ".env", ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Veltar Classifier"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    database_url: str = f"sqlite+aiosqlite:///{(PROJECT_ROOT / 'data' / 'classifier.db').as_posix()}"
    storage_root: Path = PROJECT_ROOT / "data" / "storage"
    kb_root: Path = PROJECT_ROOT / "kb"
    prompts_root: Path = PROJECT_ROOT / "backend" / "app" / "prompts"

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "qwen/qwen3.6-plus"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 240
    llm_temperature: float = 0.0
    llm_seed: int = 42
    llm_max_tokens: int = 1800
    llm_context_window_tokens: int = 16384
    llm_verify_ssl: bool = True
    llm_image_transport: str = "base64"
    llm_file_url_root: Path = PROJECT_ROOT
    step2_visual_thinking: bool = False
    page_scan_concurrency: int = 8
    job_lease_seconds: int = 900
    worker_poll_timeout_seconds: int = 5
    worker_job_concurrency: int = 4
    recovery_poll_interval_seconds: int = 30
    redis_url: str | None = None
    redis_queue_name: str = "classification:jobs"
    worker_identity: str = "classification-worker"

    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen3.6-plus"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_max_tokens: int = 8000
    openrouter_timeout_seconds: int = 180
    openrouter_fallback_models: list[str] = []
    openrouter_provider_order: list[str] = []
    openrouter_require_parameters: bool = True
    openrouter_allow_provider_fallbacks: bool = True

    max_pages_per_document: int | None = None
    max_batch_documents: int = 25
    technical_score_threshold: int = 40
    review_confidence_threshold: float = 0.75
    insufficient_evidence_threshold: float = 0.35
    close_to_threshold_ratio: float = 0.10
    max_upload_size_mb: int = 50
    allowed_media_types: list[str] = ["application/pdf", "image/png", "image/jpeg", "image/tiff", "image/webp", "image/bmp", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "text/plain", "message/rfc822"]

    default_pipeline_version: str = "v2"
    gate_timeout_seconds: int = 300
    gate_sample_max_pages: int = 6
    gate_budget_minutes: int = 5

    @field_validator("storage_root", "kb_root", "prompts_root", "llm_file_url_root", mode="before")
    @classmethod
    def _coerce_path(cls, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    @field_validator("database_url", mode="before")
    @classmethod
    def _coerce_database_url(cls, value: str) -> str:
        prefix = "sqlite+aiosqlite:///"
        if not isinstance(value, str) or not value.startswith(prefix):
            return value
        database_path = Path(value.removeprefix(prefix))
        if database_path.is_absolute():
            return value
        return f"{prefix}{(PROJECT_ROOT / database_path).resolve().as_posix()}"

    @field_validator("max_pages_per_document", mode="before")
    @classmethod
    def _coerce_max_pages_per_document(cls, value: int | str | None) -> int | None:
        if value in (None, ""):
            return None
        parsed = int(value)
        return parsed if parsed > 0 else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    return settings
