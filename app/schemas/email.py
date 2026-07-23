from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.contact_storage import AiStatus, ContactCategory, ContactPriority, EmailStatus, Sentiment


EMAIL_BODY_MAX_LENGTH = 100_000
EMAIL_SUBJECT_MAX_LENGTH = 200


class EmailType(StrEnum):
    OWNER_NOTIFICATION = "owner_notification"
    USER_CONFIRMATION = "user_confirmation"
    TEST_MESSAGE = "test_message"


class EmailMessage(BaseModel):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=EMAIL_SUBJECT_MAX_LENGTH)
    html: str = Field(min_length=1, max_length=EMAIL_BODY_MAX_LENGTH)
    text: str = Field(min_length=1, max_length=EMAIL_BODY_MAX_LENGTH)
    reply_to: EmailStr | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("subject", "html", "text", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class EmailSendResult(BaseModel):
    status: EmailStatus
    provider: str
    message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    model_config = ConfigDict(extra="forbid")


class EmailTemplateContext(BaseModel):
    contact_id: int | None = None
    name: str
    phone: str
    email: EmailStr
    comment: str
    created_at: datetime | None = None
    sentiment: Sentiment | None = None
    category: ContactCategory | None = None
    priority: ContactPriority | None = None
    summary: str | None = None
    suggested_reply: str | None = None
    ai_status: AiStatus | None = None
    ai_error: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("summary", "suggested_reply", "ai_error", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped_value = value.strip()
        return stripped_value or None
