import logging
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import ContactRequest
from app.schemas.contact import ContactRequestCreate
from app.schemas.contact_storage import (
    AiStatus,
    ContactAiUpdate,
    ContactEmailStatusUpdate,
    ContactMetrics,
    EmailStatus,
    ProcessingStatus,
)

logger = logging.getLogger(__name__)


class ContactRepositoryError(Exception):
    """Ошибка уровня репозитория обращений."""


class ContactNotFoundError(ContactRepositoryError):
    """Обращение не найдено для операции обновления."""


class ContactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, contact_data: ContactRequestCreate) -> ContactRequest:
        logger.info("event=contact_create_started operation=create")
        contact = ContactRequest(
            name=contact_data.name,
            phone=contact_data.phone,
            email=str(contact_data.email),
            comment=contact_data.comment,
            processing_status=ProcessingStatus.RECEIVED.value,
            ai_status=AiStatus.PENDING.value,
            owner_email_status=EmailStatus.PENDING.value,
            user_email_status=EmailStatus.PENDING.value,
        )

        try:
            # Обращение сохраняется до будущих OpenAI/email операций, чтобы внешние сбои
            # не приводили к потере исходного пользовательского запроса.
            self.session.add(contact)
            self.session.commit()
            self.session.refresh(contact)
        except SQLAlchemyError as exc:
            self._rollback_after_error("contact_create_failed", exc)
            raise ContactRepositoryError("Не удалось сохранить обращение в базе данных") from exc

        logger.info(
            "event=contact_create_completed operation=create contact_id=%s processing_status=%s",
            contact.id,
            contact.processing_status,
        )
        return contact

    def get_by_id(self, contact_id: int) -> ContactRequest | None:
        logger.info("event=contact_get_by_id_started operation=get_by_id contact_id=%s", contact_id)
        contact = self.session.get(ContactRequest, contact_id)
        logger.info(
            "event=contact_get_by_id_completed operation=get_by_id contact_id=%s found=%s",
            contact_id,
            contact is not None,
        )
        return contact

    def update_ai_result(self, contact_id: int, update: ContactAiUpdate) -> ContactRequest:
        logger.info(
            "event=contact_ai_update_started operation=update_ai_result contact_id=%s ai_status=%s",
            contact_id,
            update.ai_status.value,
        )
        contact = self._get_existing_contact(contact_id)
        contact.sentiment = update.sentiment
        contact.category = update.category
        contact.priority = update.priority
        contact.ai_summary = update.ai_summary
        contact.suggested_reply = update.suggested_reply
        contact.ai_status = update.ai_status.value
        contact.ai_error = update.ai_error
        return self._commit_updated_contact(contact, "contact_ai_update_completed", "contact_ai_update_failed")

    def update_email_statuses(self, contact_id: int, update: ContactEmailStatusUpdate) -> ContactRequest:
        logger.info("event=contact_email_update_started operation=update_email_statuses contact_id=%s", contact_id)
        contact = self._get_existing_contact(contact_id)

        # Email-статусы обновляются независимо: в будущем письма владельцу и пользователю
        # могут завершаться в разное время и не должны перезаписывать состояние друг друга.
        if update.owner_email_status is not None:
            contact.owner_email_status = update.owner_email_status.value
            contact.owner_email_error = update.owner_email_error
            logger.info(
                "event=contact_email_status_prepared contact_id=%s email_type=owner status=%s",
                contact_id,
                update.owner_email_status.value,
            )
        if update.user_email_status is not None:
            contact.user_email_status = update.user_email_status.value
            contact.user_email_error = update.user_email_error
            logger.info(
                "event=contact_email_status_prepared contact_id=%s email_type=user status=%s",
                contact_id,
                update.user_email_status.value,
            )

        return self._commit_updated_contact(contact, "contact_email_update_completed", "contact_email_update_failed")

    def update_owner_email_status(
        self,
        contact_id: int,
        status: EmailStatus,
        error: str | None = None,
    ) -> ContactRequest:
        return self.update_email_statuses(
            contact_id,
            ContactEmailStatusUpdate(owner_email_status=status, owner_email_error=error),
        )

    def update_user_email_status(
        self,
        contact_id: int,
        status: EmailStatus,
        error: str | None = None,
    ) -> ContactRequest:
        return self.update_email_statuses(
            contact_id,
            ContactEmailStatusUpdate(user_email_status=status, user_email_error=error),
        )

    def update_processing_status(self, contact_id: int, status: ProcessingStatus) -> ContactRequest:
        logger.info(
            "event=contact_processing_status_update_started operation=update_processing_status contact_id=%s status=%s",
            contact_id,
            status.value,
        )
        contact = self._get_existing_contact(contact_id)
        contact.processing_status = status.value
        return self._commit_updated_contact(
            contact,
            "contact_processing_status_update_completed",
            "contact_processing_status_update_failed",
        )

    def get_metrics(self) -> ContactMetrics:
        logger.info("event=contact_metrics_started operation=get_metrics")
        try:
            total_contacts = self.session.scalar(select(func.count(ContactRequest.id))) or 0
            metrics = ContactMetrics(
                total_contacts=total_contacts,
                by_processing_status=self._count_by_column(ContactRequest.processing_status),
                by_ai_status=self._count_by_column(ContactRequest.ai_status),
                owner_email=self._count_by_column(ContactRequest.owner_email_status),
                user_email=self._count_by_column(ContactRequest.user_email_status),
                # Метрики возвращают только агрегаты: персональные поля не выбираются и не попадают в результат.
                by_category=self._count_by_column(ContactRequest.category),
            )
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception("event=contact_metrics_failed operation=get_metrics error_type=%s", type(exc).__name__)
            raise ContactRepositoryError("Не удалось рассчитать метрики обращений") from exc

        logger.info("event=contact_metrics_completed operation=get_metrics total_contacts=%s", total_contacts)
        return metrics

    def _get_existing_contact(self, contact_id: int) -> ContactRequest:
        contact = self.get_by_id(contact_id)
        if contact is None:
            logger.info("event=contact_not_found contact_id=%s", contact_id)
            raise ContactNotFoundError(f"Обращение с id={contact_id} не найдено")
        return contact

    def _commit_updated_contact(
        self,
        contact: ContactRequest,
        success_event: str,
        failure_event: str,
    ) -> ContactRequest:
        try:
            self.session.commit()
            self.session.refresh(contact)
        except SQLAlchemyError as exc:
            self._rollback_after_error(failure_event, exc, contact_id=contact.id)
            raise ContactRepositoryError("Не удалось обновить обращение в базе данных") from exc

        logger.info("event=%s contact_id=%s", success_event, contact.id)
        return contact

    def _rollback_after_error(
        self,
        event: str,
        exc: SQLAlchemyError,
        contact_id: int | None = None,
    ) -> None:
        rollback_completed = False
        try:
            # Rollback возвращает сессию в пригодное состояние после неудачного commit.
            self.session.rollback()
            rollback_completed = True
        finally:
            logger.exception(
                "event=%s contact_id=%s error_type=%s rollback_completed=%s",
                event,
                contact_id,
                type(exc).__name__,
                rollback_completed,
            )

    def _count_by_column(self, column, ignore_empty: bool = False) -> dict[str, int]:
        query = select(column, func.count()).group_by(column)
        rows: Iterable[tuple[str | None, int]] = self.session.execute(query).all()
        result: dict[str, int] = {}
        for value, count in rows:
            if ignore_empty and not value:
                continue
            result[str(value)] = count
        return result
