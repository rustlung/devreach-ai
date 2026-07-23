from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.schemas.health import DatabaseHealth
from app.services.diagnostics import (
    build_dependency_health,
    build_health_response,
    build_unavailable_health_response,
    measure_database_health,
)
from tests.conftest import readable_test_id


def make_settings(tmp_path, **overrides) -> Settings:
    data = {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'health.sqlite3'}",
        "LOG_FILE_PATH": str(tmp_path / "health.log"),
        "AI_LIVE_REQUESTS_ENABLED": True,
        "OPENAI_API_KEY": "sk-test-secret",
        "OPENAI_BASE_URL": "https://api.proxyapi.ru/openai/v1",
        "OPENAI_MODEL": "gpt-4.1-mini",
        "EMAIL_LIVE_REQUESTS_ENABLED": True,
        "RESEND_API_KEY": "re_test_secret",
        "EMAIL_FROM_ADDRESS": "hello@example.com",
        "OWNER_EMAIL": "owner@example.com",
    }
    data.update(overrides)
    return Settings(**data)


@readable_test_id("health ok при доступной базе и настроенных интеграциях")
def test_health_is_ok_when_database_and_integrations_are_configured(tmp_path, _case_id) -> None:
    """HEALTH-EXTENDED-001: доступная БД и настроенные integrations дают status=ok."""
    settings = make_settings(tmp_path)

    response = build_health_response(settings, measure_database_health(settings))

    assert response.status == "ok"
    assert response.database.status == "available"
    assert response.database.latency_ms is not None
    assert response.database.latency_ms >= 0
    assert response.dependencies.ai == "configured"
    assert response.dependencies.email == "configured"


@readable_test_id("health degraded при отключенном ai")
def test_health_is_degraded_when_ai_is_disabled(tmp_path, _case_id) -> None:
    """HEALTH-DEGRADED-AI-001: отключённый AI даёт degraded без внешнего вызова."""
    settings = make_settings(tmp_path, AI_LIVE_REQUESTS_ENABLED=False)

    response = build_health_response(settings, measure_database_health(settings))

    assert response.status == "degraded"
    assert response.dependencies.ai == "disabled"


@readable_test_id("health degraded при ненастроенном email")
def test_health_is_degraded_when_email_is_not_configured(tmp_path, _case_id) -> None:
    """HEALTH-DEGRADED-EMAIL-001: ненастроенный email даёт degraded."""
    settings = make_settings(tmp_path, RESEND_API_KEY="")

    response = build_health_response(settings, measure_database_health(settings))

    assert response.status == "degraded"
    assert response.dependencies.email == "not_configured"


@readable_test_id("health degraded при отключенных интеграциях")
def test_health_is_degraded_when_integrations_are_disabled(tmp_path, _case_id) -> None:
    """HEALTH-DEGRADED-BOTH-001: обе отключённые integrations дают degraded."""
    settings = make_settings(tmp_path, AI_LIVE_REQUESTS_ENABLED=False, EMAIL_LIVE_REQUESTS_ENABLED=False)

    dependencies = build_dependency_health(settings)
    response = build_health_response(settings, measure_database_health(settings))

    assert dependencies.ai == "disabled"
    assert dependencies.email == "disabled"
    assert response.status == "degraded"


@readable_test_id("health unavailable при недоступной базе")
def test_database_health_raises_when_database_is_unavailable(tmp_path, _case_id) -> None:
    """HEALTH-DATABASE-UNAVAILABLE-001: недоступная БД приводит к диагностической ошибке."""
    settings = make_settings(tmp_path, DATABASE_URL=f"sqlite:///{tmp_path / 'missing' / 'db.sqlite3'}")

    try:
        measure_database_health(settings)
    except SQLAlchemyError as exc:
        assert type(exc).__name__
    else:
        raise AssertionError("Ожидалась SQLAlchemyError для недоступной базы")

    response = build_unavailable_health_response(settings, DatabaseHealth(status="unavailable", latency_ms=None))
    assert response.status == "unavailable"
    assert response.message == "База данных временно недоступна"


@readable_test_id("health не создает ai или resend клиенты")
def test_health_does_not_create_ai_or_resend_clients(tmp_path, monkeypatch, _case_id) -> None:
    """HEALTH-NO-EXTERNAL-CALLS-001: health не создаёт клиентов внешних провайдеров."""
    import app.services.ai_service as ai_service_module
    import app.services.email_service as email_service_module

    monkeypatch.setattr(ai_service_module, "OpenAI", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no ai")))
    monkeypatch.setattr(email_service_module.resend.Emails, "send", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no email")))
    settings = make_settings(tmp_path)

    response = build_health_response(settings, measure_database_health(settings))

    assert response.status == "ok"


@readable_test_id("секреты не попадают в health response и логи")
def test_health_does_not_expose_secrets(tmp_path, caplog, _case_id) -> None:
    """HEALTH-SECRETS-001: API-ключи не попадают в response и логи health."""
    settings = make_settings(tmp_path)

    response = build_health_response(settings, measure_database_health(settings))

    text = response.model_dump_json() + caplog.text
    assert "sk-test-secret" not in text
    assert "re_test_secret" not in text
