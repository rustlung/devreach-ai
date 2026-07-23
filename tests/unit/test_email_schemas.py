import pytest
from pydantic import ValidationError

from app.schemas.contact_storage import EmailStatus
from app.schemas.email import EmailMessage, EmailSendResult
from tests.conftest import readable_test_id


def valid_message(**overrides) -> dict:
    data = {
        "to": "user@example.com",
        "subject": "Тестовое письмо",
        "html": "<p>Здравствуйте</p>",
        "text": "Здравствуйте",
        "reply_to": "reply@example.com",
    }
    data.update(overrides)
    return data


@readable_test_id("валидное email сообщение принимается")
def test_valid_email_message_is_accepted(_case_id) -> None:
    """EMAIL-SCHEMA-001: валидное email-сообщение соответствует схеме."""
    message = EmailMessage(**valid_message())

    assert str(message.to) == "user@example.com"
    assert str(message.reply_to) == "reply@example.com"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("to", ""),
        ("to", "not-email"),
        ("subject", ""),
        ("html", ""),
        ("text", ""),
    ],
    ids=[
        "пустой получатель отклоняется",
        "некорректный email отклоняется",
        "пустая тема отклоняется",
        "пустой html body отклоняется",
        "пустой text body отклоняется",
    ],
)
def test_invalid_email_message_fields_are_rejected(field: str, value: str) -> None:
    """EMAIL-SCHEMA-002: обязательные поля письма строго валидируются."""
    with pytest.raises(ValidationError):
        EmailMessage(**valid_message(**{field: value}))


@readable_test_id("валидный результат отправки принимается")
def test_valid_email_send_result_is_accepted(_case_id) -> None:
    """EMAIL-SCHEMA-003: результат отправки принимает существующий EmailStatus."""
    result = EmailSendResult(status=EmailStatus.SENT, provider="fake", message_id="msg_123")

    assert result.status == EmailStatus.SENT


@readable_test_id("неизвестный email статус отклоняется")
def test_unknown_email_status_is_rejected(_case_id) -> None:
    """EMAIL-SCHEMA-004: неизвестный статус отправки отклоняется."""
    with pytest.raises(ValidationError):
        EmailSendResult(status="unknown", provider="fake")
