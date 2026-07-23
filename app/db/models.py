from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db.base import Base
from app.schemas.contact import EMAIL_MAX_LENGTH, NAME_MAX_LENGTH, PHONE_MAX_DIGITS
from app.schemas.contact_storage import AiStatus, EmailStatus, ProcessingStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        # SQLite хранит дату без timezone, поэтому сохраняем UTC и восстанавливаем tzinfo при чтении.
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ContactRequest(Base):
    __tablename__ = "contact_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    phone: Mapped[str] = mapped_column(String(PHONE_MAX_DIGITS + 1), nullable=False)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), nullable=False, index=True)
    # Максимальная длина комментария проверяется Pydantic-схемой; в БД нужен Text,
    # чтобы не терять переносы строк и абзацы.
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_status: Mapped[str] = mapped_column(String(32), default=AiStatus.PENDING.value, nullable=False)
    ai_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    owner_email_status: Mapped[str] = mapped_column(String(32), default=EmailStatus.PENDING.value, nullable=False)
    owner_email_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    processing_status: Mapped[str] = mapped_column(
        String(32),
        default=ProcessingStatus.RECEIVED.value,
        nullable=False,
        index=True,
    )
