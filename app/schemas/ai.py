from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.contact_storage import AiStatus, ContactCategory, ContactPriority, Sentiment

AI_SUMMARY_MAX_LENGTH = 500
AI_SUGGESTED_REPLY_MAX_LENGTH = 1000


class AIAnalysisResult(BaseModel):
    sentiment: Sentiment
    category: ContactCategory
    priority: ContactPriority
    summary: str | None = Field(max_length=AI_SUMMARY_MAX_LENGTH)
    suggested_reply: str = Field(min_length=1, max_length=AI_SUGGESTED_REPLY_MAX_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped_value = value.strip()
        return stripped_value or None

    @field_validator("suggested_reply")
    @classmethod
    def validate_suggested_reply(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Черновик ответа не должен быть пустым")
        return stripped_value


class AIServiceResult(BaseModel):
    analysis: AIAnalysisResult
    status: AiStatus
    error_code: str | None = None
    error_message: str | None = None

    model_config = ConfigDict(extra="forbid")
