from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_contact_repository
from app.core.config import Settings
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.db.base import Base
from app.repositories.contact_repository import ContactRepository, ContactRepositoryError
from app.main import create_app
from app.schemas.contact import ContactRequestCreate
from app.schemas.contact_storage import AiStatus, ContactAiUpdate, EmailStatus, ProcessingStatus
from tests.conftest import readable_test_id


PERSONAL_KEYS = {
    "id",
    "name",
    "email",
    "phone",
    "comment",
    "summary",
    "suggested_reply",
    "owner_email_error",
    "ai_error",
}
PERSONAL_VALUES = {
    "Иван Иванов",
    "Мария Петрова",
    "ivan@example.com",
    "maria@example.com",
    "+79991234567",
    "Секретный пользовательский комментарий",
    "Персональное резюме AI",
    "Персональный черновик ответа",
}


class BrokenMetricsRepository:
    def get_metrics(self):
        raise ContactRepositoryError("controlled metrics failure")


@readable_test_id("metrics пустой базы возвращает стабильные нули")
def test_metrics_empty_database_returns_zero_values(tmp_path, _case_id) -> None:
    """METRICS-EMPTY-001: пустая БД возвращает стабильные нулевые агрегаты."""
    app, session, engine = build_metrics_app(tmp_path)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/metrics", headers={"X-Request-ID": "metrics-empty"})
    finally:
        cleanup_database(session, engine)

    payload = response.json()
    assert response.status_code == 200
    assert payload["total_contacts"] == 0
    assert payload["request_id"] == response.headers["X-Request-ID"] == "metrics-empty"
    assert all(value == 0 for value in payload["processing"].values())
    assert all(value == 0 for value in payload["ai"].values())
    assert all(value == 0 for value in payload["emails"].values())
    assert "user" not in payload["emails"]
    assert all(value == 0 for value in payload["categories"].values())


@readable_test_id("metrics заполненной базы возвращает точные агрегаты")
def test_metrics_populated_database_returns_exact_aggregates(tmp_path, _case_id) -> None:
    """METRICS-AGGREGATION-001: заполненная БД агрегируется по статусам и категориям."""
    app, session, engine = build_metrics_app(tmp_path)
    seed_metrics_contacts(session)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/metrics")
    finally:
        cleanup_database(session, engine)

    payload = response.json()
    assert response.status_code == 200
    assert payload["total_contacts"] == 3
    assert payload["processing"][ProcessingStatus.COMPLETED.value] == 1
    assert payload["processing"][ProcessingStatus.COMPLETED_WITH_ERRORS.value] == 1
    assert payload["processing"][ProcessingStatus.FAILED.value] == 1
    assert payload["ai"][AiStatus.SUCCESS.value] == 1
    assert payload["ai"][AiStatus.FALLBACK.value] == 1
    assert payload["ai"][AiStatus.FAILED.value] == 1
    assert payload["emails"][EmailStatus.SENT.value] == 1
    assert payload["emails"][EmailStatus.SKIPPED.value] == 1
    assert payload["emails"][EmailStatus.FAILED.value] == 1
    assert "user" not in payload["emails"]
    assert payload["categories"]["project_request"] == 1
    assert payload["categories"]["consultation"] == 1
    assert payload["categories"]["unknown"] == 1


@readable_test_id("metrics response не содержит персональные данные")
def test_metrics_response_does_not_contain_personal_data(tmp_path, _case_id) -> None:
    """METRICS-NO-PII-001: metrics response не содержит PII и персональные поля."""
    app, session, engine = build_metrics_app(tmp_path)
    seed_metrics_contacts(session)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            payload = client.get("/api/metrics").json()
    finally:
        cleanup_database(session, engine)

    assert_no_personal_data(payload)


@readable_test_id("metrics возвращает безопасный 503 при ошибке базы")
def test_metrics_database_error_returns_safe_503(tmp_path, _case_id) -> None:
    """METRICS-DATABASE-FAILED-001: ошибка агрегации даёт безопасный 503."""
    settings = Settings(APP_ENV="test", LOG_FILE_PATH=str(tmp_path / "metrics-error.log"))
    app = create_app(settings)
    app.dependency_overrides[get_contact_repository] = lambda: BrokenMetricsRepository()

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/metrics", headers={"X-Request-ID": "metrics-db-error"})

    payload = response.json()
    assert response.status_code == 503
    assert payload["error"]["code"] == "database_unavailable"
    assert payload["request_id"] == "metrics-db-error"
    assert "traceback" not in str(payload).lower()
    assert "select" not in str(payload).lower()


@readable_test_id("metrics и health не ограничиваются contact rate limiter")
def test_metrics_and_health_are_not_contact_rate_limited(tmp_path, _case_id) -> None:
    """METRICS-NO-RATE-LIMIT-001: diagnostics endpoints не получают contact 429."""
    app, session, engine = build_metrics_app(tmp_path)
    app.state.contact_rate_limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            metric_statuses = [client.get("/api/metrics").status_code for _ in range(4)]
            health_statuses = [client.get("/api/health").status_code for _ in range(4)]
    finally:
        cleanup_database(session, engine)

    assert metric_statuses == [200, 200, 200, 200]
    assert health_statuses == [200, 200, 200, 200]


@readable_test_id("metrics endpoint зарегистрирован в openapi")
def test_metrics_openapi_contains_endpoint_and_responses(tmp_path, _case_id) -> None:
    """METRICS-OPENAPI-001: OpenAPI содержит metrics endpoint и response schema."""
    app, session, engine = build_metrics_app(tmp_path)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            schema = client.get("/openapi.json").json()
    finally:
        cleanup_database(session, engine)

    operation = schema["paths"]["/api/metrics"]["get"]
    assert "200" in operation["responses"]
    assert "503" in operation["responses"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("ContactMetricsResponse")


def build_metrics_app(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'metrics.sqlite3'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'metrics.sqlite3'}",
        LOG_FILE_PATH=str(tmp_path / "metrics.log"),
        CORS_ORIGINS=["http://testserver"],
    )
    app = create_app(settings)
    app.dependency_overrides[get_contact_repository] = lambda: ContactRepository(session)
    return app, session, engine


def cleanup_database(session, engine) -> None:
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def seed_metrics_contacts(session) -> None:
    repository = ContactRepository(session)
    first = repository.create(make_contact("Иван Иванов", "ivan@example.com", "Секретный пользовательский комментарий"))
    second = repository.create(make_contact("Мария Петрова", "maria@example.com", "Второй секретный комментарий"))
    third = repository.create(make_contact("Павел Сергеев", "pavel@example.com", "Третий секретный комментарий"))

    repository.update_ai_result(
        first.id,
        ContactAiUpdate(
            ai_status=AiStatus.SUCCESS,
            category="project_request",
            ai_summary="Персональное резюме AI",
            suggested_reply="Персональный черновик ответа",
        ),
    )
    repository.update_owner_email_status(first.id, EmailStatus.SENT)
    repository.update_processing_status(first.id, ProcessingStatus.COMPLETED)

    repository.update_ai_result(second.id, ContactAiUpdate(ai_status=AiStatus.FALLBACK, category="consultation"))
    repository.update_owner_email_status(second.id, EmailStatus.SKIPPED)
    repository.update_processing_status(second.id, ProcessingStatus.COMPLETED_WITH_ERRORS)

    repository.update_ai_result(third.id, ContactAiUpdate(ai_status=AiStatus.FAILED, category="legacy_value", ai_error="provider failed"))
    repository.update_owner_email_status(third.id, EmailStatus.FAILED, "owner failed")
    repository.update_processing_status(third.id, ProcessingStatus.FAILED)


def make_contact(name: str, email: str, comment: str) -> ContactRequestCreate:
    return ContactRequestCreate(
        name=name,
        phone="+7 999 123 45 67",
        email=email,
        comment=comment,
    )


def assert_no_personal_data(value) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            assert key not in PERSONAL_KEYS
            assert_no_personal_data(nested_value)
    elif isinstance(value, list):
        for item in value:
            assert_no_personal_data(item)
    elif isinstance(value, str):
        assert value not in PERSONAL_VALUES
