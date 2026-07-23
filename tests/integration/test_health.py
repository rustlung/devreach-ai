from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import readable_test_id


def make_settings(tmp_path, **overrides) -> Settings:
    data = {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'health.sqlite3'}",
        "LOG_FILE_PATH": str(tmp_path / "health.log"),
        "CORS_ORIGINS": ["http://testserver"],
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


@readable_test_id("health возвращает ok при доступной базе")
def test_health_check_returns_ok_when_database_is_available(tmp_path, _case_id) -> None:
    """HEALTH-EXTENDED-001: успешный health check возвращает расширенный status=ok."""
    app = create_app(make_settings(tmp_path))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health", headers={"X-Request-ID": "health-ok"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["service"] == "devreach-ai"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "test"
    assert payload["database"]["status"] == "available"
    assert payload["database"]["latency_ms"] >= 0
    assert payload["dependencies"] == {"ai": "configured", "email": "configured"}
    assert payload["request_id"] == response.headers["X-Request-ID"] == "health-ok"


@readable_test_id("health возвращает degraded при отключенном ai")
def test_health_check_returns_degraded_when_ai_is_disabled(tmp_path, _case_id) -> None:
    """HEALTH-DEGRADED-AI-001: отключённый AI даёт degraded и HTTP 200."""
    app = create_app(make_settings(tmp_path, AI_LIVE_REQUESTS_ENABLED=False))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["ai"] == "disabled"
    assert payload["database"]["status"] == "available"


@readable_test_id("health возвращает degraded при ненастроенном email")
def test_health_check_returns_degraded_when_email_is_not_configured(tmp_path, _case_id) -> None:
    """HEALTH-DEGRADED-EMAIL-001: ненастроенный email даёт degraded и HTTP 200."""
    app = create_app(make_settings(tmp_path, RESEND_API_KEY=""))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["email"] == "not_configured"


@readable_test_id("health возвращает unavailable при недоступной базе")
def test_health_check_returns_safe_error_when_database_is_unavailable(tmp_path, _case_id) -> None:
    """HEALTH-DATABASE-UNAVAILABLE-001: недоступная БД даёт HTTP 503 без traceback."""
    blocked_path = tmp_path / "missing" / "db.sqlite3"
    app = create_app(make_settings(tmp_path, DATABASE_URL=f"sqlite:///{blocked_path}"))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health", headers={"X-Request-ID": "health-db-error"})

    payload = response.json()
    assert response.status_code == 503
    assert payload["status"] == "unavailable"
    assert payload["database"] == {"status": "unavailable", "latency_ms": None}
    assert payload["message"] == "База данных временно недоступна"
    assert payload["request_id"] == "health-db-error"
    assert "traceback" not in str(payload).lower()


@readable_test_id("health не раскрывает секреты и не вызывает внешние сервисы")
def test_health_check_does_not_expose_secrets_or_call_external_services(tmp_path, monkeypatch, _case_id) -> None:
    """HEALTH-NO-EXTERNAL-CALLS-001: health не вызывает ProxyAPI/Resend и не раскрывает ключи."""
    import app.services.ai_service as ai_service_module
    import app.services.email_service as email_service_module

    monkeypatch.setattr(ai_service_module, "OpenAI", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no ai")))
    monkeypatch.setattr(email_service_module.resend.Emails, "send", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no email")))
    app = create_app(make_settings(tmp_path))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health")

    response_text = response.text
    assert response.status_code == 200
    assert "sk-test-secret" not in response_text
    assert "re_test_secret" not in response_text


@readable_test_id("health endpoint зарегистрирован в openapi")
def test_health_openapi_schema_contains_extended_contract(tmp_path, _case_id) -> None:
    """HEALTH-OPENAPI-001: OpenAPI содержит расширенный health contract."""
    app = create_app(make_settings(tmp_path))

    with TestClient(app, raise_server_exceptions=False) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/api/health"]["get"]
    assert "200" in operation["responses"]
    assert "503" in operation["responses"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("HealthResponse")
