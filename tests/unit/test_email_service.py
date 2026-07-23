from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from resend import exceptions as resend_exceptions

from app.core.config import Settings
from app.schemas.contact_storage import EmailStatus
from app.schemas.email import EmailMessage, EmailType
from app.services import email_service as email_service_module
from app.services.email_service import FakeEmailService, ResendEmailService
from tests.conftest import readable_test_id


class FakeResendEmails:
    response = {"id": "resend_msg_123"}
    exc: Exception | None = None
    payload = None

    @classmethod
    def send(cls, payload):
        cls.payload = payload
        if cls.exc is not None:
            raise cls.exc
        return cls.response


def fake_resend_module():
    FakeResendEmails.response = {"id": "resend_msg_123"}
    FakeResendEmails.exc = None
    FakeResendEmails.payload = None
    return SimpleNamespace(api_key=None, Emails=FakeResendEmails)


def make_settings(**overrides) -> Settings:
    data = {
        "APP_ENV": "test",
        "RESEND_API_KEY": "test-key",
        "EMAIL_FROM_ADDRESS": "hello@example.com",
        "EMAIL_FROM_NAME": "DevReach AI",
        "OWNER_EMAIL": "owner@example.com",
        "EMAIL_REPLY_TO": "reply@example.com",
        "EMAIL_LIVE_REQUESTS_ENABLED": True,
    }
    data.update(overrides)
    return Settings(**data)


def make_message(**overrides) -> EmailMessage:
    data = {
        "to": "user@example.com",
        "subject": "Тестовое письмо",
        "html": "<p>Привет</p>",
        "text": "Привет",
        "reply_to": "reply@example.com",
    }
    data.update(overrides)
    return EmailMessage(**data)


@readable_test_id("resend payload формируется корректно")
def test_resend_payload_is_built_correctly(_case_id) -> None:
    """EMAIL-SEND-PAYLOAD-001: payload содержит sender, to, subject, html, text и reply_to."""
    resend_module = fake_resend_module()
    service = ResendEmailService(settings=make_settings(), resend_module=resend_module)

    result = service.send(make_message(), EmailType.USER_CONFIRMATION, contact_id=15)

    assert result.status == EmailStatus.SENT
    assert resend_module.api_key == "test-key"
    assert FakeResendEmails.payload == {
        "from": "DevReach AI <hello@example.com>",
        "to": ["user@example.com"],
        "subject": "Тестовое письмо",
        "html": "<p>Привет</p>",
        "text": "Привет",
        "reply_to": "reply@example.com",
    }


@readable_test_id("письмо владельцу отправляется на owner email")
def test_owner_notification_uses_owner_email_and_user_reply_to(_case_id) -> None:
    """EMAIL-SEND-OWNER-001: уведомление владельцу уходит на OWNER_EMAIL с reply_to пользователя."""
    resend_module = fake_resend_module()
    service = ResendEmailService(settings=make_settings(), resend_module=resend_module)
    context = email_service_module.EmailTemplateContext(
        contact_id=15,
        name="Иван Иванов",
        phone="+79991234567",
        email="user@example.com",
        comment="Тестовый комментарий",
    )

    result = service.send_owner_notification(context)

    assert result.status == EmailStatus.SENT
    assert FakeResendEmails.payload["to"] == ["owner@example.com"]
    assert FakeResendEmails.payload["reply_to"] == "user@example.com"


@readable_test_id("письмо пользователю отправляется на его email")
def test_user_confirmation_uses_user_email(_case_id) -> None:
    """EMAIL-SEND-USER-001: подтверждение отправляется пользователю."""
    resend_module = fake_resend_module()
    service = ResendEmailService(settings=make_settings(), resend_module=resend_module)
    context = email_service_module.EmailTemplateContext(
        name="Иван Иванов",
        phone="+79991234567",
        email="user@example.com",
        comment="Тестовый комментарий",
    )

    result = service.send_user_confirmation(context)

    assert result.status == EmailStatus.SENT
    assert FakeResendEmails.payload["to"] == ["user@example.com"]
    assert FakeResendEmails.payload["reply_to"] == "reply@example.com"


@readable_test_id("успешный ответ сохраняет provider message id")
def test_successful_resend_response_returns_sent_status(_case_id) -> None:
    """EMAIL-SEND-RESULT-001: успешный Resend-ответ возвращает sent и message_id."""
    result = ResendEmailService(settings=make_settings(), resend_module=fake_resend_module()).send(
        make_message(),
        EmailType.TEST_MESSAGE,
    )

    assert result.status == EmailStatus.SENT
    assert result.message_id == "resend_msg_123"


@readable_test_id("live отключен возвращает skipped")
def test_disabled_live_requests_return_skipped(_case_id) -> None:
    """EMAIL-SKIPPED-DISABLED-001: при выключенном live письмо не отправляется."""
    resend_module = fake_resend_module()
    service = ResendEmailService(
        settings=make_settings(EMAIL_LIVE_REQUESTS_ENABLED=False),
        resend_module=resend_module,
    )

    result = service.send(make_message(), EmailType.TEST_MESSAGE)

    assert result.status == EmailStatus.SKIPPED
    assert result.error_code == "live_requests_disabled"
    assert FakeResendEmails.payload is None


@pytest.mark.parametrize(
    ("settings_overrides", "expected_code"),
    [
        ({"RESEND_API_KEY": ""}, "missing_api_key"),
        ({"EMAIL_FROM_ADDRESS": ""}, "missing_sender"),
        ({"EMAIL_FROM_ADDRESS": "Legal Client Tracker <onboarding@resend.dev>"}, "invalid_sender"),
        ({"OWNER_EMAIL": ""}, "missing_owner_email"),
    ],
    ids=[
        "отсутствующий resend api key обрабатывается",
        "отсутствующий sender обрабатывается",
        "sender с именем вместо чистого email отклоняется",
        "отсутствующий owner email обрабатывается",
    ],
)
def test_missing_email_settings_are_handled(settings_overrides: dict, expected_code: str) -> None:
    """EMAIL-FAILED-CONFIG-001: отсутствие обязательных настроек возвращает failed."""
    service = ResendEmailService(settings=make_settings(**settings_overrides), resend_module=fake_resend_module())

    if expected_code == "missing_owner_email":
        result = service.send_owner_notification(
            email_service_module.EmailTemplateContext(
                name="Иван Иванов",
                phone="+79991234567",
                email="user@example.com",
                comment="Тестовый комментарий",
            )
        )
    else:
        result = service.send(make_message(), EmailType.TEST_MESSAGE)

    assert result.status == EmailStatus.FAILED
    assert result.error_code == expected_code
    if expected_code == "invalid_sender":
        assert FakeResendEmails.payload is None


@pytest.mark.parametrize(
    ("exc", "expected_code"),
    [
        (
            resend_exceptions.InvalidApiKeyError("invalid", "invalid_api_key", 401),
            "provider_authentication_failed",
        ),
        (
            resend_exceptions.RateLimitError("too many", "rate_limit_exceeded", 429),
            "provider_rate_limited",
        ),
        (requests.exceptions.Timeout("timeout"), "provider_timeout"),
        (requests.exceptions.ConnectionError("connection"), "provider_connection_error"),
        (RuntimeError("unexpected"), "unexpected_error"),
    ],
    ids=[
        "ошибка авторизации resend возвращает failed",
        "rate limit resend возвращает failed",
        "timeout resend возвращает failed",
        "ошибка соединения resend возвращает failed",
        "неожиданная ошибка возвращает failed",
    ],
)
def test_provider_errors_return_failed(exc: Exception, expected_code: str) -> None:
    """EMAIL-FAILED-PROVIDER-001: ошибки Resend классифицируются в безопасные коды."""
    resend_module = fake_resend_module()
    FakeResendEmails.exc = exc
    service = ResendEmailService(settings=make_settings(), resend_module=resend_module)

    result = service.send(make_message(), EmailType.TEST_MESSAGE)

    assert result.status == EmailStatus.FAILED
    assert result.error_code == expected_code


@readable_test_id("ответ без message id считается ошибкой")
def test_invalid_provider_response_returns_failed(_case_id) -> None:
    """EMAIL-FAILED-INVALID-RESPONSE-001: ответ Resend без id не считается отправкой."""
    resend_module = fake_resend_module()
    FakeResendEmails.response = {}

    result = ResendEmailService(settings=make_settings(), resend_module=resend_module).send(
        make_message(),
        EmailType.TEST_MESSAGE,
    )

    assert result.status == EmailStatus.FAILED
    assert result.error_code == "invalid_provider_response"


@readable_test_id("тело письма и персональные данные не попадают в логи")
def test_email_body_and_personal_data_are_not_logged(monkeypatch, _case_id) -> None:
    """EMAIL-LOGGING-001: тело письма, email и комментарий не пишутся в логи."""
    logger_spy = Mock()
    monkeypatch.setattr(email_service_module, "logger", logger_spy)
    service = ResendEmailService(settings=make_settings(), resend_module=fake_resend_module())
    message = make_message(html="<p>secret body</p>", text="secret body", to="private@example.com")

    service.send(message, EmailType.TEST_MESSAGE, contact_id=15)

    log_text = " ".join(str(arg) for call in logger_spy.info.call_args_list for arg in call.args)
    assert "secret body" not in log_text
    assert "private@example.com" not in log_text
    assert "contact_id" in log_text


@pytest.mark.parametrize(
    "mode",
    ["success", "failed", "skipped"],
    ids=[
        "fake success возвращает sent",
        "fake failure возвращает failed",
        "fake skipped возвращает skipped",
    ],
)
def test_fake_email_service_modes(mode: str) -> None:
    """EMAIL-FAKE-001: fake-сервис поддерживает основные режимы результата."""
    service = FakeEmailService(mode=mode)

    result = service.send(make_message(), EmailType.TEST_MESSAGE, contact_id=15)

    assert len(service.sent_messages) == 1
    if mode == "success":
        assert result.status == EmailStatus.SENT
    if mode == "failed":
        assert result.status == EmailStatus.FAILED
    if mode == "skipped":
        assert result.status == EmailStatus.SKIPPED


@readable_test_id("fake exception имитирует ошибку")
def test_fake_email_service_can_raise_error(_case_id) -> None:
    """EMAIL-FAKE-002: fake-сервис умеет имитировать исключение."""
    with pytest.raises(RuntimeError):
        FakeEmailService(mode="error").send(make_message(), EmailType.TEST_MESSAGE)


@readable_test_id("fake сервис не вызывает resend sdk")
def test_fake_email_service_does_not_call_resend(monkeypatch, _case_id) -> None:
    """EMAIL-FAKE-003: fake-сервис не использует Resend и не требует API-ключ."""
    monkeypatch.setattr(email_service_module.resend.Emails, "send", Mock(side_effect=RuntimeError("no resend")))

    result = FakeEmailService().send(make_message(), EmailType.TEST_MESSAGE)

    assert result.status == EmailStatus.SENT
