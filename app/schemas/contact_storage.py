from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ProcessingStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class AiStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FALLBACK = "fallback"
    FAILED = "failed"


class EmailStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ContactPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class ContactCategory(StrEnum):
    JOB_OFFER = "job_offer"
    PROJECT_REQUEST = "project_request"
    CONSULTATION = "consultation"
    PARTNERSHIP = "partnership"
    OTHER = "other"


class ContactAiUpdate(BaseModel):
    sentiment: str | None = None
    category: str | None = None
    priority: str | None = None
    ai_summary: str | None = None
    suggested_reply: str | None = None
    ai_status: AiStatus
    ai_error: str | None = None


class ContactEmailStatusUpdate(BaseModel):
    owner_email_status: EmailStatus | None = None
    owner_email_error: str | None = None


class ContactMetrics(BaseModel):
    total_contacts: int
    by_processing_status: dict[str, int]
    by_ai_status: dict[str, int]
    owner_email: dict[str, int]
    by_category: dict[str, int]

    model_config = ConfigDict(frozen=True)
