from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из окружения и `.env` при локальном запуске."""

    app_name: str = Field(default="devreach-ai", validation_alias="APP_NAME")
    app_env: Literal["local", "test", "staging", "production"] = Field(
        default="local", validation_alias="APP_ENV"
    )
    debug: bool = Field(default=False, validation_alias="DEBUG")
    host: str = Field(default="127.0.0.1", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")
    database_url: str = Field(
        default="sqlite:///./devreach_ai.sqlite3", validation_alias="DATABASE_URL"
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:8000"],
        validation_alias="CORS_ORIGINS",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_file_path: str = Field(default="logs/app.log", validation_alias="LOG_FILE_PATH")
    log_max_bytes: int = Field(default=1_048_576, validation_alias="LOG_MAX_BYTES")
    log_backup_count: int = Field(default=3, validation_alias="LOG_BACKUP_COUNT")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_MODEL")
    openai_timeout_seconds: float = Field(default=20.0, validation_alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_retries: int = Field(default=1, validation_alias="OPENAI_MAX_RETRIES")
    ai_live_requests_enabled: bool = Field(default=False, validation_alias="AI_LIVE_REQUESTS_ENABLED")
    resend_api_key: str | None = Field(default=None, validation_alias="RESEND_API_KEY")
    email_from_address: str | None = Field(default=None, validation_alias="EMAIL_FROM_ADDRESS")
    email_from_name: str = Field(default="DevReach AI", validation_alias="EMAIL_FROM_NAME")
    owner_email: str | None = Field(default=None, validation_alias="OWNER_EMAIL")
    email_live_requests_enabled: bool = Field(default=False, validation_alias="EMAIL_LIVE_REQUESTS_ENABLED")
    email_reply_to: str | None = Field(default=None, validation_alias="EMAIL_REPLY_TO")
    email_subject_prefix: str = Field(default="[DevReach AI]", validation_alias="EMAIL_SUBJECT_PREFIX")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value: bool | str) -> bool:
        if isinstance(value, bool):
            return value
        normalized_value = value.strip().lower()
        if normalized_value in {"1", "true", "yes", "on", "debug", "dev", "local"}:
            return True
        if normalized_value in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def normalize_openai_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped_value = value.strip()
        return stripped_value or None

    @field_validator("openai_base_url", mode="before")
    @classmethod
    def normalize_openai_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped_value = value.strip()
        return stripped_value or None

    @field_validator("resend_api_key", "email_from_address", "owner_email", "email_reply_to", mode="before")
    @classmethod
    def normalize_optional_email_setting(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped_value = value.strip()
        return stripped_value or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
