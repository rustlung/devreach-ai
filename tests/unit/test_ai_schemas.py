import pytest
from pydantic import ValidationError

from app.schemas.ai import AIAnalysisResult
from app.schemas.contact_storage import AiStatus
from app.services.ai_service import build_fallback_analysis, build_fallback_result
from tests.conftest import readable_test_id


def valid_ai_payload(**overrides) -> dict:
    payload = {
        "sentiment": "neutral",
        "category": "project_request",
        "priority": "normal",
        "summary": "Пользователь хочет обсудить проект.",
        "suggested_reply": "Спасибо за обращение. Я ознакомлюсь с деталями и свяжусь с вами.",
    }
    payload.update(overrides)
    return payload


@readable_test_id("валидный ai результат принимается схемой")
def test_valid_ai_result_is_accepted(_case_id) -> None:
    """AI-SCHEMA-001: валидный AI-результат принимается Pydantic-схемой."""
    result = AIAnalysisResult(**valid_ai_payload())

    assert result.sentiment == "neutral"
    assert result.category == "project_request"
    assert result.priority == "normal"


@pytest.mark.parametrize(
    ("field_name", "raw_value"),
    [
        ("sentiment", "mixed"),
        ("category", "sales"),
        ("priority", "urgent"),
    ],
    ids=[
        "неизвестная тональность отклоняется",
        "неизвестная категория отклоняется",
        "неизвестный приоритет отклоняется",
    ],
)
def test_unknown_enum_values_are_rejected(field_name: str, raw_value: str) -> None:
    """AI-SCHEMA-002: неизвестные enum-значения AI-результата отклоняются."""
    with pytest.raises(ValidationError):
        AIAnalysisResult(**valid_ai_payload(**{field_name: raw_value}))


@readable_test_id("слишком длинный summary отклоняется")
def test_too_long_summary_is_rejected(_case_id) -> None:
    """AI-SCHEMA-003: слишком длинный summary считается невалидным structured output."""
    with pytest.raises(ValidationError):
        AIAnalysisResult(**valid_ai_payload(summary="A" * 501))


@readable_test_id("пустой suggested reply отклоняется")
def test_empty_suggested_reply_is_rejected(_case_id) -> None:
    """AI-SCHEMA-004: пустой suggested reply отклоняется."""
    with pytest.raises(ValidationError):
        AIAnalysisResult(**valid_ai_payload(suggested_reply="   "))


@readable_test_id("fallback analysis соответствует схеме")
def test_fallback_analysis_matches_schema(_case_id) -> None:
    """AI-SCHEMA-005: fallback-результат соответствует AI-схеме."""
    fallback = build_fallback_analysis()

    assert fallback.sentiment == "neutral"
    assert fallback.category == "other"
    assert fallback.priority == "normal"
    assert fallback.summary is None
    assert "OpenAI" not in fallback.suggested_reply


@readable_test_id("fallback service result содержит внутренний статус fallback")
def test_fallback_service_result_has_fallback_status(_case_id) -> None:
    """AI-SCHEMA-006: сервисный fallback содержит статус и внутренний код причины."""
    result = build_fallback_result("missing_api_key", "OPENAI_API_KEY не задан")

    assert result.status == AiStatus.FALLBACK
    assert result.error_code == "missing_api_key"
    assert result.analysis.sentiment == "neutral"
