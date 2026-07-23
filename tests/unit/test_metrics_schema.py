from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.metrics import ContactMetricsResponse, EmailMetrics
from app.schemas.contact_storage import AiStatus, ContactCategory, EmailStatus, ProcessingStatus
from app.schemas.contact_storage import ContactMetrics
from app.services.diagnostics import build_metrics_response
from tests.conftest import readable_test_id


def valid_metrics_payload(**overrides) -> dict:
    data = {
        "total_contacts": 0,
        "processing": {status.value: 0 for status in ProcessingStatus} | {"unknown": 0},
        "ai": {status.value: 0 for status in AiStatus} | {"unknown": 0},
        "emails": {
            "owner": {status.value: 0 for status in EmailStatus} | {"unknown": 0},
            "user": {status.value: 0 for status in EmailStatus} | {"unknown": 0},
        },
        "categories": {category.value: 0 for category in ContactCategory} | {"unknown": 0},
        "generated_at": datetime.now(timezone.utc),
        "request_id": "metrics-request",
    }
    data.update(overrides)
    return data


@readable_test_id("валидная схема метрик принимается")
def test_valid_metrics_response_is_accepted(_case_id) -> None:
    """METRICS-SCHEMA-001: валидный response метрик принимается схемой."""
    response = ContactMetricsResponse(**valid_metrics_payload(total_contacts=5))

    assert response.total_contacts == 5
    assert response.emails.owner[EmailStatus.PENDING.value] == 0


@pytest.mark.parametrize(
    "payload",
    [
        valid_metrics_payload(total_contacts=-1),
        valid_metrics_payload(processing={ProcessingStatus.RECEIVED.value: -1}),
        valid_metrics_payload(emails={"owner": {EmailStatus.SENT.value: -1}, "user": {EmailStatus.SENT.value: 0}}),
        valid_metrics_payload(categories={ContactCategory.OTHER.value: -1}),
    ],
    ids=[
        "отрицательный total отклоняется",
        "отрицательный processing count отклоняется",
        "отрицательный email count отклоняется",
        "отрицательный category count отклоняется",
    ],
)
def test_negative_metric_values_are_rejected(payload: dict) -> None:
    """METRICS-SCHEMA-002: отрицательные значения метрик отклоняются."""
    with pytest.raises(ValidationError):
        ContactMetricsResponse(**payload)


@readable_test_id("generated at обязан содержать timezone")
def test_generated_at_must_be_timezone_aware(_case_id) -> None:
    """METRICS-SCHEMA-003: generated_at должен быть timezone-aware."""
    with pytest.raises(ValidationError, match="timezone"):
        ContactMetricsResponse(**valid_metrics_payload(generated_at=datetime(2026, 7, 23, 12, 0)))


@readable_test_id("request id обязателен")
def test_request_id_is_required(_case_id) -> None:
    """METRICS-SCHEMA-004: request_id обязателен в response метрик."""
    payload = valid_metrics_payload()
    payload.pop("request_id")

    with pytest.raises(ValidationError):
        ContactMetricsResponse(**payload)


@readable_test_id("пустые метрики имеют стабильную структуру")
def test_empty_metrics_have_stable_structure(_case_id) -> None:
    """METRICS-SCHEMA-005: пустые метрики содержат все известные ключи с нулями."""
    response = build_metrics_response(
        ContactMetrics(
            total_contacts=0,
            by_processing_status={},
            by_ai_status={},
            owner_email={},
            user_email={},
            by_category={},
        ),
        request_id="empty-metrics",
    )

    assert response.total_contacts == 0
    assert set(response.processing) == {status.value for status in ProcessingStatus} | {"unknown"}
    assert set(response.ai) == {status.value for status in AiStatus} | {"unknown"}
    assert set(response.emails.owner) == {status.value for status in EmailStatus} | {"unknown"}
    assert set(response.categories) == {category.value for category in ContactCategory} | {"unknown"}
    assert all(value == 0 for section in [response.processing, response.ai, response.emails.owner, response.emails.user, response.categories] for value in section.values())


@readable_test_id("лишние персональные поля запрещены схемой")
def test_extra_personal_fields_are_forbidden(_case_id) -> None:
    """METRICS-SCHEMA-006: произвольные персональные поля не принимаются схемой."""
    with pytest.raises(ValidationError):
        ContactMetricsResponse(**valid_metrics_payload(email="user@example.com"))


@readable_test_id("email metrics запрещает лишние поля")
def test_email_metrics_forbids_extra_fields(_case_id) -> None:
    """METRICS-SCHEMA-007: вложенная email-схема запрещает лишние поля."""
    with pytest.raises(ValidationError):
        EmailMetrics(owner={EmailStatus.SENT.value: 1}, user={EmailStatus.SENT.value: 1}, email="user@example.com")
