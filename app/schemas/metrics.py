from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContactMetricsResponse(BaseModel):
    total_contacts: int = Field(ge=0)
    processing: dict[str, int]
    ai: dict[str, int]
    emails: dict[str, int]
    categories: dict[str, int]
    generated_at: datetime
    request_id: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("processing", "ai", "emails", "categories")
    @classmethod
    def validate_non_negative_metric_values(cls, value: dict[str, int]) -> dict[str, int]:
        negative_keys = [key for key, count in value.items() if count < 0]
        if negative_keys:
            raise ValueError("Значения метрик не могут быть отрицательными")
        return value

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("generated_at должен содержать timezone")
        return value
