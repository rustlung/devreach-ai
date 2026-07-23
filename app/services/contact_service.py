from __future__ import annotations

import logging
import time
from typing import Protocol

from app.db.models import ContactRequest
from app.repositories.contact_repository import ContactRepository, ContactRepositoryError
from app.schemas.ai import AIServiceResult
from app.schemas.contact import ContactRequestCreate, ContactResponse
from app.schemas.contact_storage import (
    AiStatus,
    ContactAiUpdate,
    ContactCreateData,
    ContactPriority,
    EmailStatus,
    ProcessingStatus,
)
from app.schemas.email import EmailSendResult, EmailTemplateContext
from app.services.ai_service import build_fallback_result
from app.services.demo_access import DeliveryMode, NotificationRecipient


logger = logging.getLogger(__name__)


class ContactProcessingError(Exception):
    """Безопасная ошибка orchestration-слоя для критических внутренних сбоев."""


class ContactServiceRepository(Protocol):
    def create(self, contact_data: ContactCreateData) -> ContactRequest:
        ...

    def update_processing_status(self, contact_id: int, status: ProcessingStatus) -> ContactRequest:
        ...

    def update_ai_result(self, contact_id: int, update: ContactAiUpdate) -> ContactRequest:
        ...

    def update_owner_email_status(
        self,
        contact_id: int,
        status: EmailStatus,
        error: str | None = None,
    ) -> ContactRequest:
        ...


class ContactServiceAI(Protocol):
    def analyze_comment(self, comment: str) -> AIServiceResult:
        ...


class ContactServiceEmail(Protocol):
    def send_owner_notification(
        self,
        context: EmailTemplateContext,
        recipient_email: str | None = None,
    ) -> EmailSendResult:
        ...


class ContactService:
    def __init__(
        self,
        repository: ContactServiceRepository | ContactRepository,
        ai_service: ContactServiceAI,
        email_service: ContactServiceEmail,
    ) -> None:
        self.repository = repository
        self.ai_service = ai_service
        self.email_service = email_service

    def process_contact(
        self,
        contact_data: ContactRequestCreate,
        request_id: str,
        notification_recipient: NotificationRecipient | None = None,
    ) -> ContactResponse:
        start_time = time.perf_counter()
        contact_id: int | None = None
        active_recipient = notification_recipient or NotificationRecipient(delivery_mode=DeliveryMode.OWNER)
        logger.info("event=contact_pipeline_started request_id=%s", request_id)

        try:
            # Сначала сохраняем обращение: внешние AI/email сбои не должны стирать
            # исходный пользовательский запрос.
            storage_data = ContactCreateData(
                name=contact_data.name,
                phone=contact_data.phone,
                email=str(contact_data.email),
                comment=contact_data.comment,
            )
            contact = self.repository.create(storage_data)
            contact_id = contact.id
            logger.info(
                "event=contact_persisted request_id=%s contact_id=%s processing_status=%s",
                request_id,
                contact_id,
                contact.processing_status,
            )

            contact = self._update_processing_status(
                contact_id,
                ProcessingStatus.PROCESSING,
                request_id,
                "start_processing",
            )

            ai_result = self._run_ai_stage(contact, request_id)
            contact = self._save_ai_result(contact_id, ai_result, request_id)

            email_context = self._build_email_context(contact, ai_result)
            owner_result = self._run_owner_email_stage(contact_id, email_context, request_id, active_recipient)
            contact = self._save_owner_email_result(contact_id, owner_result, request_id)

            final_status = self._determine_processing_status(ai_result, owner_result)
            contact = self._update_processing_status(contact_id, final_status, request_id, "save_final_status")
        except ContactProcessingError:
            raise
        except ContactRepositoryError as exc:
            self._log_critical_failure(request_id, contact_id, "repository", exc)
            raise ContactProcessingError("Критическая ошибка сохранения обращения") from exc

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "event=contact_pipeline_completed request_id=%s contact_id=%s processing_status=%s "
            "ai_status=%s owner_email_status=%s delivery_mode=%s duration_ms=%s",
            request_id,
            contact_id,
            contact.processing_status,
            contact.ai_status,
            contact.owner_email_status,
            active_recipient.delivery_mode.value,
            duration_ms,
        )

        # HTTP 201 сохраняется при частичных внешних ошибках, потому что обращение
        # уже принято и его состояние зафиксировано в БД.
        return ContactResponse(
            id=contact.id,
            status=ProcessingStatus(contact.processing_status),
            message="Обращение принято",
            ai_processed=ai_result.status == AiStatus.SUCCESS,
            ai_status=AiStatus(contact.ai_status),
            owner_email_status=EmailStatus(contact.owner_email_status),
            request_id=request_id,
        )

    def _run_ai_stage(self, contact: ContactRequest, request_id: str) -> AIServiceResult:
        logger.info("event=contact_ai_stage_started request_id=%s contact_id=%s", request_id, contact.id)
        try:
            ai_result = self.ai_service.analyze_comment(contact.comment)
        except Exception as exc:
            # AI fallback не останавливает pipeline: обращение уже сохранено,
            # а владелец всё равно должен получить письмо с безопасным черновиком.
            logger.exception(
                "event=contact_ai_stage_fallback request_id=%s contact_id=%s reason=unexpected_exception error_type=%s",
                request_id,
                contact.id,
                type(exc).__name__,
            )
            ai_result = build_fallback_result("ai_service_exception", "AI-сервис выбросил исключение")

        if ai_result.status == AiStatus.SUCCESS:
            logger.info(
                "event=contact_ai_stage_completed request_id=%s contact_id=%s ai_status=%s",
                request_id,
                contact.id,
                ai_result.status.value,
            )
        else:
            logger.warning(
                "event=contact_ai_stage_fallback request_id=%s contact_id=%s reason=%s",
                request_id,
                contact.id,
                ai_result.error_code,
            )
        return ai_result

    def _save_ai_result(self, contact_id: int, ai_result: AIServiceResult, request_id: str) -> ContactRequest:
        try:
            return self.repository.update_ai_result(
                contact_id,
                ContactAiUpdate(
                    sentiment=ai_result.analysis.sentiment.value,
                    category=ai_result.analysis.category.value,
                    priority=ai_result.analysis.priority.value,
                    ai_summary=ai_result.analysis.summary,
                    suggested_reply=ai_result.analysis.suggested_reply,
                    ai_status=ai_result.status,
                    ai_error=self._safe_error(ai_result.error_code),
                ),
            )
        except ContactRepositoryError as exc:
            # Ошибка БД критична: в отличие от OpenAI/Resend, мы не можем честно
            # продолжать, если не удалось зафиксировать состояние обращения.
            self._log_critical_failure(request_id, contact_id, "save_ai_result", exc)
            raise ContactProcessingError("Не удалось сохранить AI-результат обращения") from exc

    def _update_processing_status(
        self,
        contact_id: int,
        status: ProcessingStatus,
        request_id: str,
        stage: str,
    ) -> ContactRequest:
        try:
            return self.repository.update_processing_status(contact_id, status)
        except ContactRepositoryError as exc:
            self._log_critical_failure(request_id, contact_id, stage, exc)
            raise ContactProcessingError("Не удалось обновить статус обработки обращения") from exc

    def _build_email_context(self, contact: ContactRequest, ai_result: AIServiceResult) -> EmailTemplateContext:
        # В шаблоны передаём контролируемый Pydantic-контекст вместо ORM-модели,
        # чтобы случайно не раскрыть внутренние поля или служебные ошибки.
        return EmailTemplateContext(
            contact_id=contact.id,
            name=contact.name,
            phone=contact.phone,
            email=contact.email,
            comment=contact.comment,
            created_at=contact.created_at,
            sentiment=ai_result.analysis.sentiment,
            category=ai_result.analysis.category,
            priority=ai_result.analysis.priority,
            summary=ai_result.analysis.summary,
            suggested_reply=ai_result.analysis.suggested_reply,
            ai_status=ai_result.status,
            ai_error=self._safe_error(ai_result.error_code),
        )

    def _run_owner_email_stage(
        self,
        contact_id: int,
        context: EmailTemplateContext,
        request_id: str,
        notification_recipient: NotificationRecipient,
    ) -> EmailSendResult:
        logger.info(
            "event=contact_owner_email_stage_started request_id=%s contact_id=%s delivery_mode=%s",
            request_id,
            contact_id,
            notification_recipient.delivery_mode.value,
        )
        try:
            result = self.email_service.send_owner_notification(context, notification_recipient.recipient_email)
        except Exception as exc:
            logger.exception(
                "event=contact_owner_email_stage_failed request_id=%s contact_id=%s error_type=%s",
                request_id,
                contact_id,
                type(exc).__name__,
            )
            result = EmailSendResult(
                status=EmailStatus.FAILED,
                provider="email_service",
                error_code="email_service_exception",
                error_message="Email-сервис выбросил исключение",
            )

        logger.info(
            "event=contact_owner_email_stage_completed request_id=%s contact_id=%s delivery_mode=%s "
            "email_status=%s error_code=%s",
            request_id,
            contact_id,
            notification_recipient.delivery_mode.value,
            result.status.value,
            result.error_code,
        )
        return result

    def _save_owner_email_result(
        self,
        contact_id: int,
        result: EmailSendResult,
        request_id: str,
    ) -> ContactRequest:
        try:
            return self.repository.update_owner_email_status(
                contact_id,
                result.status,
                self._safe_error(result.error_code),
            )
        except ContactRepositoryError as exc:
            self._log_critical_failure(request_id, contact_id, "save_owner_email_status", exc)
            raise ContactProcessingError("Не удалось сохранить статус письма владельцу") from exc

    def _determine_processing_status(
        self,
        ai_result: AIServiceResult,
        owner_result: EmailSendResult,
    ) -> ProcessingStatus:
        if ai_result.status == AiStatus.SUCCESS and owner_result.status == EmailStatus.SENT:
            return ProcessingStatus.COMPLETED
        return ProcessingStatus.COMPLETED_WITH_ERRORS

    def _safe_error(self, error_code: str | None) -> str | None:
        if error_code is None:
            return None
        return error_code[:200]

    def _log_critical_failure(
        self,
        request_id: str,
        contact_id: int | None,
        stage: str,
        exc: Exception,
    ) -> None:
        logger.exception(
            "event=contact_pipeline_failed request_id=%s contact_id=%s stage=%s error_type=%s",
            request_id,
            contact_id,
            stage,
            type(exc).__name__,
        )
