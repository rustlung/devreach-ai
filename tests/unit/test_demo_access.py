from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.schemas.contact import ContactRequestCreate
from app.services import demo_access as demo_access_module
from app.services.demo_access import (
    DeliveryMode,
    DemoAccessDeniedError,
    resolve_notification_recipient,
)
from tests.conftest import readable_test_id


def make_settings(**overrides) -> Settings:
    data = {
        "APP_ENV": "test",
        "OWNER_EMAIL": "owner@example.com",
        "DEMO_ACCESS_TOKEN": "demo-secret",
    }
    data.update(overrides)
    return Settings(**data)


def make_contact(**overrides) -> ContactRequestCreate:
    data = {
        "name": "Иван Иванов",
        "phone": "+7 999 123 45 67",
        "email": "user@example.com",
        "comment": "Здравствуйте, хочу обсудить тестовый проект.",
    }
    data.update(overrides)
    return ContactRequestCreate(**data)


@readable_test_id("обычный режим выбирает owner delivery")
def test_resolve_notification_recipient_uses_owner_mode_without_demo_fields(_case_id) -> None:
    """DEMO-ACCESS-OWNER-001: без demo-полей выбирается обычный режим доставки владельцу."""
    result = resolve_notification_recipient(make_contact(), make_settings(), "request-1", "ip_sha256:test")

    assert result.delivery_mode == DeliveryMode.OWNER
    assert result.recipient_email is None


@readable_test_id("корректный demo token выбирает demo email")
def test_resolve_notification_recipient_uses_demo_email_with_valid_token(_case_id) -> None:
    """DEMO-ACCESS-GRANTED-001: корректный demo token разрешает доставку на demo email."""
    result = resolve_notification_recipient(
        make_contact(demo_recipient_email="reviewer@example.com", demo_access_token="demo-secret"),
        make_settings(),
        "request-2",
        "ip_sha256:test",
    )

    assert result.delivery_mode == DeliveryMode.DEMO
    assert result.recipient_email == "reviewer@example.com"


@readable_test_id("demo access использует compare digest")
def test_resolve_notification_recipient_uses_compare_digest(monkeypatch, _case_id) -> None:
    """DEMO-ACCESS-COMPARE-DIGEST-001: токены сравниваются через secrets.compare_digest."""
    compare_digest = Mock(return_value=True)
    monkeypatch.setattr(demo_access_module.secrets, "compare_digest", compare_digest)

    resolve_notification_recipient(
        make_contact(demo_recipient_email="reviewer@example.com", demo_access_token="demo-secret"),
        make_settings(),
        "request-3",
        "ip_sha256:test",
    )

    compare_digest.assert_called_once_with("demo-secret", "demo-secret")


@readable_test_id("неверный demo token отклоняется")
def test_resolve_notification_recipient_rejects_invalid_token(_case_id) -> None:
    """DEMO-ACCESS-DENIED-001: неверный demo token не переключается на OWNER_EMAIL."""
    with pytest.raises(DemoAccessDeniedError):
        resolve_notification_recipient(
            make_contact(demo_recipient_email="reviewer@example.com", demo_access_token="wrong-secret"),
            make_settings(),
            "request-4",
            "ip_sha256:test",
        )


@readable_test_id("пустой серверный demo token отключает режим")
def test_resolve_notification_recipient_rejects_disabled_demo_mode(_case_id) -> None:
    """DEMO-DISABLED-001: пустой DEMO_ACCESS_TOKEN отключает demo-доставку."""
    with pytest.raises(DemoAccessDeniedError):
        resolve_notification_recipient(
            make_contact(demo_recipient_email="reviewer@example.com", demo_access_token="demo-secret"),
            make_settings(DEMO_ACCESS_TOKEN=""),
            "request-5",
            "ip_sha256:test",
        )


@readable_test_id("demo email без token отклоняется")
def test_resolve_notification_recipient_rejects_demo_email_without_token(_case_id) -> None:
    """DEMO-ACCESS-DENIED-002: demo email без token возвращает безопасный отказ."""
    with pytest.raises(DemoAccessDeniedError):
        resolve_notification_recipient(
            make_contact(demo_recipient_email="reviewer@example.com"),
            make_settings(),
            "request-6",
            "ip_sha256:test",
        )


@readable_test_id("секреты не попадают в demo access логи")
def test_resolve_notification_recipient_does_not_log_secret_values(monkeypatch, _case_id) -> None:
    """DEMO-NO-SECRETS-LOGGING-001: token и email не пишутся в логи resolver."""
    logger_spy = Mock()
    monkeypatch.setattr(demo_access_module, "logger", logger_spy)

    with pytest.raises(DemoAccessDeniedError):
        resolve_notification_recipient(
            make_contact(demo_recipient_email="reviewer@example.com", demo_access_token="wrong-secret"),
            make_settings(),
            "request-7",
            "ip_sha256:test",
        )

    log_text = " ".join(str(arg) for call in logger_spy.warning.call_args_list for arg in call.args)
    assert "wrong-secret" not in log_text
    assert "demo-secret" not in log_text
    assert "reviewer@example.com" not in log_text
    assert "invalid_or_disabled" in log_text
    assert "contact_pipeline_called=false" in log_text


@readable_test_id("результат resolver не содержит секретный token")
def test_resolve_notification_recipient_result_does_not_contain_token(_case_id) -> None:
    """DEMO-NO-SECRETS-RESULT-001: результат resolver содержит режим и recipient, но не token."""
    result = resolve_notification_recipient(
        make_contact(demo_recipient_email="reviewer@example.com", demo_access_token="demo-secret"),
        make_settings(),
        "request-8",
        "ip_sha256:test",
    )

    assert "demo-secret" not in repr(result)
    assert result.recipient_email == "reviewer@example.com"
