import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_contact_service
from app.core.config import Settings
from app.db.base import Base
from app.db.models import ContactRequest
from app.main import create_app
from app.repositories.contact_repository import ContactRepository, ContactRepositoryError
from app.schemas.contact_storage import AiStatus, EmailStatus, ProcessingStatus
from app.services.ai_service import FakeAIAnalysisService
from app.services.contact_service import ContactService
from app.services.email_service import FakeEmailService
from tests.conftest import readable_test_id


class CreateFailingRepository:
    def create(self, contact_data):
        raise ContactRepositoryError("create failed")


class TrackingContactService:
    def __init__(self) -> None:
        self.called = False

    def process_contact(self, contact_data, request_id, notification_recipient=None):
        self.called = True
        raise AssertionError("ContactService не должен вызываться")


@pytest.fixture
def contact_api_context(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'contact-api.sqlite3'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'unused.sqlite3'}",
        LOG_FILE_PATH=str(tmp_path / "api.log"),
        CORS_ORIGINS=["http://testserver"],
    )
    app = create_app(settings)

    try:
        yield app, session
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def valid_payload(**overrides) -> dict:
    data = {
        "name": "   Иван    Иванов   ",
        "phone": "8 (999) 123-45-67",
        "email": "  User@Example.COM  ",
        "comment": "Хотел бы обсудить разработку backend-сервиса.",
    }
    data.update(overrides)
    return data


def install_contact_service_override(app, session, ai_mode: str = "success", email_service=None) -> None:
    def override_contact_service() -> ContactService:
        return ContactService(
            repository=ContactRepository(session),
            ai_service=FakeAIAnalysisService(mode=ai_mode),
            email_service=email_service or FakeEmailService(),
        )

    app.dependency_overrides[get_contact_service] = override_contact_service


def get_only_contact(session) -> ContactRequest:
    return session.execute(select(ContactRequest)).scalar_one()


@readable_test_id("post contact success возвращает 201 и сохраняет запись")
def test_contact_api_success_creates_contact(contact_api_context, _case_id) -> None:
    """CONTACT-API-SUCCESS-001: успешный POST сохраняет обращение и возвращает безопасный ответ."""
    app, session = contact_api_context
    install_contact_service_override(app, session)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/contact", json=valid_payload(), headers={"X-Request-ID": "api-request-1"})

    payload = response.json()
    contact = get_only_contact(session)
    assert response.status_code == 201
    assert payload["id"] == contact.id
    assert payload["status"] == "completed"
    assert payload["message"] == "Обращение принято"
    assert payload["ai_processed"] is True
    assert payload["ai_status"] == "success"
    assert payload["owner_email_status"] == "sent"
    assert "emails" not in payload
    assert payload["request_id"] == response.headers["X-Request-ID"] == "api-request-1"
    assert contact.name == "Иван Иванов"
    assert contact.phone == "+79991234567"
    assert contact.email == "user@example.com"
    assert contact.ai_status == AiStatus.SUCCESS.value
    assert contact.owner_email_status == EmailStatus.SENT.value
    assert contact.processing_status == ProcessingStatus.COMPLETED.value


@readable_test_id("post contact demo success отправляет письмо demo получателю")
def test_contact_api_demo_success_sends_single_email_to_demo_recipient(contact_api_context, _case_id) -> None:
    """DEMO-ACCESS-GRANTED-001: корректный demo-запрос создаёт запись и отправляет одно письмо demo recipient."""
    app, session = contact_api_context
    app.state.settings.demo_access_token = "demo-secret"
    email_service = FakeEmailService()
    install_contact_service_override(app, session, email_service=email_service)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/contact",
            json=valid_payload(
                demo_recipient_email="  Reviewer@Example.COM  ",
                demo_access_token="demo-secret",
            ),
            headers={"X-Request-ID": "demo-success-request"},
        )

    payload = response.json()
    contact = get_only_contact(session)
    assert response.status_code == 201
    assert payload["message"] == "Обращение принято"
    assert payload["owner_email_status"] == "sent"
    assert len(email_service.sent_messages) == 1
    assert str(email_service.sent_messages[0]["message"].to) == "reviewer@example.com"
    assert str(email_service.sent_messages[0]["message"].reply_to) == "user@example.com"
    assert contact.email == "user@example.com"
    assert "demo_recipient_email" not in contact.__table__.columns
    assert "demo_access_token" not in contact.__table__.columns


@readable_test_id("post contact invalid demo token возвращает безопасный 403")
def test_contact_api_invalid_demo_token_returns_403_before_pipeline(contact_api_context, _case_id) -> None:
    """DEMO-ACCESS-DENIED-001: неверный demo token не создаёт запись и не запускает pipeline."""
    app, session = contact_api_context
    app.state.settings.demo_access_token = "demo-secret"
    tracking_service = TrackingContactService()
    app.dependency_overrides[get_contact_service] = lambda: tracking_service

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/contact",
            json=valid_payload(demo_recipient_email="reviewer@example.com", demo_access_token="wrong-secret"),
            headers={"X-Request-ID": "demo-denied-request"},
        )

    body = response.json()
    assert response.status_code == 403
    assert body["error"]["code"] == "demo_access_denied"
    assert body["error"]["message"] == "Режим демонстрационной проверки недоступен."
    assert body["error"]["details"] == []
    assert body["request_id"] == "demo-denied-request"
    assert "wrong-secret" not in str(body)
    assert "demo-secret" not in str(body)
    assert tracking_service.called is False
    assert session.execute(select(ContactRequest)).scalars().all() == []


@readable_test_id("post contact demo disabled возвращает тот же 403")
def test_contact_api_disabled_demo_mode_returns_403_before_pipeline(contact_api_context, _case_id) -> None:
    """DEMO-DISABLED-001: пустой DEMO_ACCESS_TOKEN отключает demo-доставку."""
    app, session = contact_api_context
    app.state.settings.demo_access_token = None
    tracking_service = TrackingContactService()
    app.dependency_overrides[get_contact_service] = lambda: tracking_service

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/contact",
            json=valid_payload(demo_recipient_email="reviewer@example.com", demo_access_token="demo-secret"),
            headers={"X-Request-ID": "demo-disabled-request"},
        )

    body = response.json()
    assert response.status_code == 403
    assert body["error"]["code"] == "demo_access_denied"
    assert body["request_id"] == "demo-disabled-request"
    assert tracking_service.called is False
    assert session.execute(select(ContactRequest)).scalars().all() == []


@readable_test_id("post contact demo email без token возвращает 403")
def test_contact_api_demo_email_without_token_returns_403(contact_api_context, _case_id) -> None:
    """DEMO-ACCESS-DENIED-002: demo email без token отклоняется безопасным 403."""
    app, session = contact_api_context
    app.state.settings.demo_access_token = "demo-secret"
    tracking_service = TrackingContactService()
    app.dependency_overrides[get_contact_service] = lambda: tracking_service

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/contact",
            json=valid_payload(demo_recipient_email="reviewer@example.com"),
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "demo_access_denied"
    assert tracking_service.called is False
    assert session.execute(select(ContactRequest)).scalars().all() == []


@readable_test_id("post contact demo token без email возвращает 422")
def test_contact_api_demo_token_without_email_returns_422(contact_api_context, _case_id) -> None:
    """DEMO-SCHEMA-008: demo token без recipient считается неполным payload."""
    app, session = contact_api_context
    tracking_service = TrackingContactService()
    app.dependency_overrides[get_contact_service] = lambda: tracking_service

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/contact",
            json=valid_payload(demo_access_token="demo-secret"),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert tracking_service.called is False
    assert session.execute(select(ContactRequest)).scalars().all() == []


@readable_test_id("post contact ai fallback возвращает 201")
def test_contact_api_ai_fallback_returns_created(contact_api_context, _case_id) -> None:
    """CONTACT-API-AI-FALLBACK-001: AI fallback не меняет HTTP 201 после сохранения обращения."""
    app, session = contact_api_context
    install_contact_service_override(app, session, ai_mode="fallback")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/contact", json=valid_payload())

    payload = response.json()
    contact = get_only_contact(session)
    assert response.status_code == 201
    assert payload["ai_processed"] is False
    assert payload["ai_status"] == "fallback"
    assert payload["status"] == "completed_with_errors"
    assert contact.processing_status == ProcessingStatus.COMPLETED_WITH_ERRORS.value
    assert contact.ai_status == AiStatus.FALLBACK.value


@readable_test_id("post contact email failure возвращает частичную ошибку в body")
def test_contact_api_email_failure_returns_completed_with_errors(contact_api_context, _case_id) -> None:
    """CONTACT-API-EMAIL-FAILED-001: email failed сохраняется, но API остаётся 201."""
    app, session = contact_api_context
    install_contact_service_override(app, session, email_service=FakeEmailService(owner_mode="failed"))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/contact", json=valid_payload())

    payload = response.json()
    contact = get_only_contact(session)
    assert response.status_code == 201
    assert payload["status"] == "completed_with_errors"
    assert payload["owner_email_status"] == "failed"
    assert "user" not in str(payload)
    assert "fake_failed" not in str(payload)
    assert contact.owner_email_status == EmailStatus.FAILED.value
    assert contact.processing_status == ProcessingStatus.COMPLETED_WITH_ERRORS.value


@pytest.mark.parametrize(
    "payload",
    [
        valid_payload(name="Иван123"),
        valid_payload(email="not-email"),
        valid_payload(phone="+7 phone"),
        valid_payload(comment="   "),
        valid_payload(website="bot"),
    ],
    ids=[
        "имя с цифрами возвращает 422",
        "невалидный email возвращает 422",
        "невалидный телефон возвращает 422",
        "пустой комментарий возвращает 422",
        "заполненный honeypot возвращает 422",
    ],
)
def test_contact_api_validation_errors_do_not_call_service(contact_api_context, payload: dict) -> None:
    """CONTACT-API-VALIDATION-001: невалидный запрос не создаёт запись и возвращает безопасный 422."""
    app, session = contact_api_context
    tracking_service = TrackingContactService()
    app.dependency_overrides[get_contact_service] = lambda: tracking_service

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/contact", json=payload, headers={"X-Request-ID": "validation-request"})

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "validation_error"
    assert body["request_id"] == "validation-request"
    assert tracking_service.called is False
    assert session.execute(select(ContactRequest)).scalars().all() == []


@readable_test_id("validation response не содержит value error prefix")
def test_contact_api_validation_messages_do_not_include_value_error_prefix(contact_api_context, _case_id) -> None:
    """CONTACT-API-VALIDATION-002: сообщения 422 не содержат технический префикс Pydantic."""
    app, session = contact_api_context
    tracking_service = TrackingContactService()
    app.dependency_overrides[get_contact_service] = lambda: tracking_service

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/contact",
            json=valid_payload(name="2134234", phone="", email="", comment=""),
        )

    body = response.json()
    messages = [detail["msg"] for detail in body["error"]["details"]]
    assert response.status_code == 422
    assert all(not message.startswith("Value error,") for message in messages)
    assert "Имя должно содержать хотя бы одну букву" in messages
    assert "Телефон обязателен" in messages
    assert "Email обязателен" in messages
    assert "Комментарий обязателен" in messages
    assert tracking_service.called is False
    assert session.execute(select(ContactRequest)).scalars().all() == []


@readable_test_id("ошибка базы при создании возвращает безопасный 500")
def test_contact_api_database_create_error_returns_safe_500(contact_api_context, _case_id) -> None:
    """CONTACT-API-DATABASE-FAILED-001: ошибка create возвращает безопасный HTTP 500 без внешних вызовов."""
    app, _session = contact_api_context
    ai_service = FakeAIAnalysisService()
    email_service = FakeEmailService()
    app.dependency_overrides[get_contact_service] = lambda: ContactService(
        repository=CreateFailingRepository(),
        ai_service=ai_service,
        email_service=email_service,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/contact", json=valid_payload(), headers={"X-Request-ID": "db-error-request"})

    body = response.json()
    assert response.status_code == 500
    assert body["error"]["code"] == "internal_server_error"
    assert body["request_id"] == "db-error-request"
    assert "traceback" not in str(body).lower()
    assert email_service.sent_messages == []


@readable_test_id("contact endpoint зарегистрирован в openapi")
def test_contact_api_openapi_contains_contact_endpoint(contact_api_context, _case_id) -> None:
    """CONTACT-API-OPENAPI-001: OpenAPI содержит POST /api/contact и 201 response."""
    app, _session = contact_api_context

    with TestClient(app, raise_server_exceptions=False) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/api/contact"]["post"]
    assert "201" in operation["responses"]
    assert operation["summary"] == "Принять обращение с сайта"
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("ContactRequestCreate")


@readable_test_id("openapi содержит demo поля входной схемы")
def test_contact_api_openapi_contains_demo_fields(contact_api_context, _case_id) -> None:
    """DEMO-API-OPENAPI-001: OpenAPI описывает необязательные demo-поля без реального token."""
    app, _session = contact_api_context

    with TestClient(app, raise_server_exceptions=False) as client:
        schema = client.get("/openapi.json").json()

    properties = schema["components"]["schemas"]["ContactRequestCreate"]["properties"]
    assert "demo_recipient_email" in properties
    assert "demo_access_token" in properties
    assert properties["demo_access_token"].get("maxLength") == 256
    assert "demo-secret" not in str(properties["demo_access_token"])
