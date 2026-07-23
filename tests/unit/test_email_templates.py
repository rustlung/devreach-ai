from datetime import datetime, timezone

from app.core.config import Settings
from app.schemas.contact_storage import AiStatus, ContactCategory, ContactPriority, Sentiment
from app.schemas.email import EmailTemplateContext
from app.services.email_service import ResendEmailService
from tests.conftest import readable_test_id


def make_settings(**overrides) -> Settings:
    data = {
        "APP_ENV": "test",
        "EMAIL_FROM_ADDRESS": "hello@example.com",
        "EMAIL_FROM_NAME": "DevReach AI",
        "OWNER_EMAIL": "owner@example.com",
        "EMAIL_REPLY_TO": "reply@example.com",
        "EMAIL_SUBJECT_PREFIX": "[DevReach AI]",
    }
    data.update(overrides)
    return Settings(**data)


def make_context(**overrides) -> EmailTemplateContext:
    data = {
        "contact_id": 15,
        "name": "Иван Иванов",
        "phone": "+79991234567",
        "email": "user@example.com",
        "comment": "Первая строка.\n\nВторая строка.",
        "created_at": datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        "sentiment": Sentiment.NEUTRAL,
        "category": ContactCategory.PROJECT_REQUEST,
        "priority": ContactPriority.NORMAL,
        "summary": "Пользователь хочет обсудить проект.",
        "suggested_reply": "Спасибо за обращение. Я ознакомлюсь с деталями.",
        "ai_status": AiStatus.SUCCESS,
    }
    data.update(overrides)
    return EmailTemplateContext(**data)


@readable_test_id("письмо владельцу рендерится с данными обращения")
def test_owner_notification_is_rendered(_case_id) -> None:
    """EMAIL-RENDER-OWNER-001: письмо владельцу содержит основные поля и AI summary."""
    message = ResendEmailService(settings=make_settings()).build_owner_message(make_context())

    assert message.html
    assert message.text
    assert "Иван Иванов" in message.html
    assert "Первая строка." in message.text
    assert "Пользователь хочет обсудить проект." in message.html


@readable_test_id("optional поля не выводят none")
def test_missing_optional_fields_do_not_render_none(_case_id) -> None:
    """EMAIL-RENDER-OPTIONAL-001: отсутствующие optional-поля не превращаются в строку None."""
    context = make_context(created_at=None, summary=None, category=None, sentiment=None, priority=None, ai_status=None)

    message = ResendEmailService(settings=make_settings()).build_owner_message(context)

    assert "None" not in message.html
    assert "None" not in message.text


@readable_test_id("html комментария экранируется")
def test_user_html_in_comment_is_escaped(_case_id) -> None:
    """EMAIL-HTML-ESCAPE-001: HTML/JS из комментария не становится тегом в письме."""
    context = make_context(comment='<script>alert("xss")</script>')

    message = ResendEmailService(settings=make_settings()).build_owner_message(context)

    assert "<script>" not in message.html
    assert "&lt;script&gt;" in message.html
    assert '<script>alert("xss")</script>' in message.text


@readable_test_id("переносы строк комментария сохраняются")
def test_comment_line_breaks_are_preserved(_case_id) -> None:
    """EMAIL-TEXT-001: переносы строк есть в text и визуально сохраняются в HTML."""
    message = ResendEmailService(settings=make_settings()).build_owner_message(make_context())

    assert "white-space:pre-wrap" in message.html
    assert "Первая строка.\n\nВторая строка." in message.text


@readable_test_id("suggested reply владельца экранируется")
def test_owner_suggested_reply_is_escaped(_case_id) -> None:
    """EMAIL-HTML-ESCAPE-002: AI suggested_reply не вставляется как безопасный HTML."""
    context = make_context(suggested_reply='<script>alert("reply")</script>')

    message = ResendEmailService(settings=make_settings()).build_owner_message(context)

    assert "<script>" not in message.html
    assert "&lt;script&gt;" in message.html


@readable_test_id("fallback отображается в письме владельцу")
def test_ai_fallback_is_rendered_safely(_case_id) -> None:
    """EMAIL-RENDER-FALLBACK-001: fallback виден владельцу без provider error."""
    context = make_context(ai_status=AiStatus.FALLBACK, suggested_reply=None, ai_error="OpenAI timeout")
    service = ResendEmailService(settings=make_settings())

    owner_message = service.build_owner_message(context)

    assert "AI fallback применён" in owner_message.text
    assert "OpenAI timeout" not in owner_message.html


@readable_test_id("письмо владельцу разделено на смысловые блоки")
def test_owner_notification_has_business_sections(_case_id) -> None:
    """EMAIL-OWNER-ONLY-001: письмо владельцу содержит блоки обращения, AI-анализа и черновика."""
    message = ResendEmailService(settings=make_settings()).build_owner_message(make_context())

    assert "Обращение" in message.text
    assert "AI-анализ" in message.text
    assert "Предлагаемый ответ" in message.text


@readable_test_id("шаблоны письма пользователю отсутствуют")
def test_user_confirmation_templates_are_removed(_case_id) -> None:
    """EMAIL-NO-USER-AUTOREPLY-001: шаблоны автоматического письма пользователю удалены."""
    service = ResendEmailService(settings=make_settings())

    assert not hasattr(service, "build_user_message")
