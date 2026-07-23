from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import readable_test_id


@readable_test_id("health возвращает ok при доступной базе")
def test_health_check_returns_ok_when_database_is_available(
    client: TestClient, _case_id
) -> None:
    """HEALTH-001: успешный health check возвращает статус ok и доступность базы."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "devreach-ai",
        "version": "0.1.0",
        "database": "available",
        "message": None,
    }


@readable_test_id("health возвращает безопасную ошибку при недоступной базе")
def test_health_check_returns_safe_error_when_database_is_unavailable(tmp_path, _case_id) -> None:
    """HEALTH-002: при недоступной БД API возвращает безопасное сообщение без traceback."""
    blocked_path = tmp_path / "missing" / "db.sqlite3"
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{blocked_path}",
        LOG_FILE_PATH=str(tmp_path / "health-error.log"),
        CORS_ORIGINS=["http://testserver"],
    )
    app = create_app(settings)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/health")

    payload = response.json()
    assert response.status_code == 503
    assert payload["status"] == "error"
    assert payload["database"] == "unavailable"
    assert payload["message"] == "База данных временно недоступна"
    assert "traceback" not in str(payload).lower()
