from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Protocol

import requests
import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import EmailStr, TypeAdapter, ValidationError
from resend import exceptions as resend_exceptions

from app.core.config import Settings, get_settings
from app.schemas.contact_storage import AiStatus, EmailStatus
from app.schemas.email import EmailMessage, EmailSendResult, EmailTemplateContext, EmailType


logger = logging.getLogger(__name__)
_EMAIL_ADDRESS_ADAPTER = TypeAdapter(EmailStr)

class EmailDeliveryService(Protocol):
    def send(self, message: EmailMessage, email_type: EmailType, contact_id: int | None = None) -> EmailSendResult:
        ...


def create_email_template_environment(template_dir: Path | None = None) -> Environment:
    templates_path = template_dir or Path(__file__).resolve().parents[1] / "templates" / "emails"
    # Autoescape включён для HTML, потому что в шаблоны попадают пользовательские
    # данные. Эти данные нельзя помечать safe: комментарий может содержать HTML/JS.
    return Environment(
        loader=FileSystemLoader(templates_path),
        autoescape=select_autoescape(enabled_extensions=("html",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


class ResendEmailService:
    def __init__(
        self,
        settings: Settings | None = None,
        template_environment: Environment | None = None,
        resend_module=resend,
    ) -> None:
        self.settings = settings or get_settings()
        self.template_environment = template_environment or create_email_template_environment()
        self._resend = resend_module

    def build_owner_message(self, context: EmailTemplateContext, recipient_email: str | None = None) -> EmailMessage:
        rendered = self._render_templates(EmailType.OWNER_NOTIFICATION, context)
        subject = self._build_owner_subject(context)
        return EmailMessage(
            to=recipient_email or self.settings.owner_email or "owner@example.com",
            subject=subject,
            html=rendered["html"],
            text=rendered["text"],
            reply_to=context.email,
        )

    def send_owner_notification(
        self,
        context: EmailTemplateContext,
        recipient_email: str | None = None,
    ) -> EmailSendResult:
        recipient = recipient_email or self.settings.owner_email
        if not recipient:
            return self._failed(
                EmailType.OWNER_NOTIFICATION,
                context.contact_id,
                "missing_owner_email",
                "OWNER_EMAIL не задан",
            )
        return self.send(
            self.build_owner_message(context, recipient_email=recipient),
            EmailType.OWNER_NOTIFICATION,
            context.contact_id,
        )

    def send(self, message: EmailMessage, email_type: EmailType, contact_id: int | None = None) -> EmailSendResult:
        start_time = time.perf_counter()
        logger.info(
            "event=email_send_started provider=resend email_type=%s contact_id=%s",
            email_type.value,
            contact_id,
        )

        if not self.settings.email_live_requests_enabled:
            logger.info(
                "event=email_send_skipped reason=live_requests_disabled email_type=%s contact_id=%s",
                email_type.value,
                contact_id,
            )
            return EmailSendResult(
                status=EmailStatus.SKIPPED,
                provider="resend",
                error_code="live_requests_disabled",
                error_message="Live-отправка email отключена настройкой",
            )

        if not self.settings.resend_api_key:
            return self._failed(email_type, contact_id, "missing_api_key", "RESEND_API_KEY не задан")
        if not self.settings.email_from_address:
            return self._failed(email_type, contact_id, "missing_sender", "EMAIL_FROM_ADDRESS не задан")
        if not self._is_valid_sender_address(self.settings.email_from_address):
            return self._failed(
                email_type,
                contact_id,
                "invalid_sender",
                "EMAIL_FROM_ADDRESS должен содержать только email без имени отправителя",
            )

        payload = self._build_payload(message)
        try:
            # API-ключ задаётся только в live-ветке непосредственно перед отправкой.
            self._resend.api_key = self.settings.resend_api_key
            response = self._resend.Emails.send(payload)
            message_id = self._extract_message_id(response)
            if not message_id:
                return self._failed(
                    email_type,
                    contact_id,
                    "invalid_provider_response",
                    "Resend вернул ответ без message id",
                )
        except Exception as exc:
            error_code = self._classify_provider_error(exc)
            return self._failed(email_type, contact_id, error_code, self._safe_provider_error_message(error_code), exc)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "event=email_send_completed provider=resend email_type=%s contact_id=%s message_id=%s duration_ms=%s",
            email_type.value,
            contact_id,
            message_id,
            duration_ms,
        )
        return EmailSendResult(status=EmailStatus.SENT, provider="resend", message_id=message_id)

    def _render_templates(self, email_type: EmailType, context: EmailTemplateContext) -> dict[str, str]:
        logger.info(
            "event=email_render_started email_type=%s contact_id=%s",
            email_type.value,
            context.contact_id,
        )
        template_context = self._build_template_context(context, email_type)
        html = self.template_environment.get_template(f"{email_type.value}.html").render(template_context)
        # Текстовая версия нужна для совместимости почтовых клиентов и доступности.
        text = self.template_environment.get_template(f"{email_type.value}.txt").render(template_context)
        logger.info(
            "event=email_render_completed email_type=%s contact_id=%s",
            email_type.value,
            context.contact_id,
        )
        return {"html": html, "text": text}

    def _build_template_context(self, context: EmailTemplateContext, email_type: EmailType) -> dict[str, Any]:
        subject = self._build_owner_subject(context)
        return {
            "subject": subject,
            "contact_id": context.contact_id,
            "name": context.name,
            "phone": context.phone,
            "email": str(context.email),
            "comment": context.comment,
            "created_at": self._format_created_at(context),
            "sentiment": self._enum_value(context.sentiment),
            "category": self._enum_value(context.category),
            "priority": self._enum_value(context.priority),
            "summary": context.summary,
            "suggested_reply": context.suggested_reply,
            "ai_status_label": self._build_ai_status_label(context),
            "ai_fallback_used": context.ai_status == AiStatus.FALLBACK,
        }

    def _build_owner_subject(self, context: EmailTemplateContext) -> str:
        if context.category:
            return f"{self.settings.email_subject_prefix} Новое обращение: {context.category.value}"
        return f"{self.settings.email_subject_prefix} Новое обращение с сайта"

    def _build_payload(self, message: EmailMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "from": self._format_sender(),
            "to": [str(message.to)],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        if message.reply_to:
            payload["reply_to"] = str(message.reply_to)
        return payload

    def _format_sender(self) -> str:
        if self.settings.email_from_name:
            return f"{self.settings.email_from_name} <{self.settings.email_from_address}>"
        return self.settings.email_from_address or ""

    def _is_valid_sender_address(self, value: str) -> bool:
        if "<" in value or ">" in value:
            return False
        try:
            # Resend принимает friendly sender в поле `from`, но в настройках мы
            # храним имя и адрес отдельно, чтобы не получить вложенный формат.
            _EMAIL_ADDRESS_ADAPTER.validate_python(value)
        except ValidationError:
            return False
        return True

    def _format_created_at(self, context: EmailTemplateContext) -> str | None:
        if context.created_at is None:
            return None
        return context.created_at.strftime("%Y-%m-%d %H:%M:%S %Z").strip()

    def _build_ai_status_label(self, context: EmailTemplateContext) -> str:
        if context.ai_status is None:
            return "AI-анализ ещё не выполнялся"
        if context.ai_status == AiStatus.FALLBACK:
            return "Применён AI fallback"
        return context.ai_status.value

    def _enum_value(self, value) -> str | None:
        return value.value if value is not None else None

    def _extract_message_id(self, response: Any) -> str | None:
        if isinstance(response, dict):
            return response.get("id")
        return getattr(response, "id", None)

    def _classify_provider_error(self, exc: Exception) -> str:
        if isinstance(exc, (resend_exceptions.MissingApiKeyError, resend_exceptions.InvalidApiKeyError)):
            return "provider_authentication_failed"
        if isinstance(exc, resend_exceptions.RateLimitError):
            return "provider_rate_limited"
        if isinstance(exc, requests.exceptions.Timeout):
            return "provider_timeout"
        if isinstance(exc, requests.exceptions.ConnectionError):
            return "provider_connection_error"
        if isinstance(exc, resend_exceptions.ResendError):
            return "provider_error"
        return "unexpected_error"

    def _safe_provider_error_message(self, error_code: str) -> str:
        messages = {
            "provider_authentication_failed": "Resend отклонил авторизацию",
            "provider_rate_limited": "Resend ограничил частоту запросов",
            "provider_timeout": "Resend не ответил за ожидаемое время",
            "provider_connection_error": "Ошибка соединения с Resend",
            "provider_error": "Resend вернул ошибку API",
            "invalid_sender": "EMAIL_FROM_ADDRESS должен содержать только email без имени отправителя",
            "unexpected_error": "Неожиданная ошибка email-сервиса",
        }
        return messages.get(error_code, "Ошибка email-сервиса")

    def _failed(
        self,
        email_type: EmailType,
        contact_id: int | None,
        error_code: str,
        error_message: str,
        exc: Exception | None = None,
    ) -> EmailSendResult:
        logger.warning(
            "event=email_send_failed provider=resend email_type=%s contact_id=%s error_code=%s error_type=%s",
            email_type.value,
            contact_id,
            error_code,
            type(exc).__name__ if exc else None,
        )
        return EmailSendResult(
            status=EmailStatus.FAILED,
            provider="resend",
            error_code=error_code,
            error_message=error_message,
        )


class FakeEmailService:
    def __init__(self, mode: str = "success", owner_mode: str | None = None) -> None:
        self.mode = mode
        self.owner_mode = owner_mode
        self.sent_messages: list[dict[str, Any]] = []

    def send(self, message: EmailMessage, email_type: EmailType, contact_id: int | None = None) -> EmailSendResult:
        return self._send_with_mode(self.mode, message, email_type, contact_id)

    def _send_with_mode(
        self,
        mode: str,
        message: EmailMessage,
        email_type: EmailType,
        contact_id: int | None,
    ) -> EmailSendResult:
        if mode in {"error", "exception"}:
            raise RuntimeError("Тестовая ошибка fake email")

        self.sent_messages.append(
            {
                "message": message,
                "email_type": email_type,
                "contact_id": contact_id,
            }
        )

        if mode == "failed":
            return EmailSendResult(
                status=EmailStatus.FAILED,
                provider="fake",
                error_code="fake_failed",
                error_message="Fake email failure",
            )
        if mode == "skipped":
            return EmailSendResult(
                status=EmailStatus.SKIPPED,
                provider="fake",
                error_code="fake_skipped",
                error_message="Fake email skipped",
            )
        return EmailSendResult(status=EmailStatus.SENT, provider="fake", message_id=f"fake-{len(self.sent_messages)}")

    def send_owner_notification(
        self,
        context: EmailTemplateContext,
        recipient_email: str | None = None,
    ) -> EmailSendResult:
        message = EmailMessage(
            to=recipient_email or "owner@example.com",
            subject="Fake owner notification",
            html="<p>Fake owner notification</p>",
            text="Fake owner notification",
            reply_to=context.email,
        )
        return self._send_with_mode(self.owner_mode or self.mode, message, EmailType.OWNER_NOTIFICATION, context.contact_id)
