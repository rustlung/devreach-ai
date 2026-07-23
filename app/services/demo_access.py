from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from enum import StrEnum

from app.core.config import Settings
from app.schemas.contact import ContactRequestCreate


logger = logging.getLogger(__name__)


class DeliveryMode(StrEnum):
    OWNER = "owner"
    DEMO = "demo"


@dataclass(frozen=True)
class NotificationRecipient:
    delivery_mode: DeliveryMode
    recipient_email: str | None = None


class DemoAccessDeniedError(Exception):
    """Безопасный отказ в защищённом demo-режиме без раскрытия причины клиенту."""


def resolve_notification_recipient(
    contact_data: ContactRequestCreate,
    settings: Settings,
    request_id: str,
    client_key: str | None = None,
) -> NotificationRecipient:
    has_demo_email = contact_data.demo_recipient_email is not None
    has_demo_token = contact_data.demo_access_token is not None

    if not has_demo_email and not has_demo_token:
        logger.info(
            "event=notification_recipient_resolved request_id=%s delivery_mode=%s",
            request_id,
            DeliveryMode.OWNER.value,
        )
        return NotificationRecipient(delivery_mode=DeliveryMode.OWNER)

    if not has_demo_email or not has_demo_token or not settings.demo_access_token:
        _log_demo_access_denied(request_id, client_key)
        raise DemoAccessDeniedError

    # compare_digest нужен, чтобы проверка секрета не зависела от совпавшего префикса.
    if not secrets.compare_digest(str(settings.demo_access_token), str(contact_data.demo_access_token)):
        _log_demo_access_denied(request_id, client_key)
        raise DemoAccessDeniedError

    logger.info("event=demo_access_granted request_id=%s client_key=%s", request_id, client_key)
    logger.info(
        "event=notification_recipient_resolved request_id=%s delivery_mode=%s",
        request_id,
        DeliveryMode.DEMO.value,
    )
    return NotificationRecipient(
        delivery_mode=DeliveryMode.DEMO,
        recipient_email=str(contact_data.demo_recipient_email),
    )


def _log_demo_access_denied(request_id: str, client_key: str | None) -> None:
    logger.warning(
        "event=demo_access_denied request_id=%s client_key=%s reason=invalid_or_disabled "
        "contact_pipeline_called=false",
        request_id,
        client_key,
    )
