from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatabaseHealth(BaseModel):
    status: Literal["available", "unavailable"]
    latency_ms: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


class DependencyHealth(BaseModel):
    ai: Literal["configured", "not_configured", "disabled"]
    email: Literal["configured", "not_configured", "disabled"]

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    service: str
    version: str
    environment: str
    database: DatabaseHealth
    dependencies: DependencyHealth
    timestamp: datetime
    request_id: str
    message: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("timestamp должен содержать timezone")
        return value
