import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_contact_service
from app.core.config import Settings
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.db.base import Base
from app.db.models import ContactRequest
from app.main import create_app
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact_storage import AiStatus, ContactCategory, ContactPriority, EmailStatus, Sentiment
from app.schemas.email import EmailSendResult, EmailTemplateContext
from app.services.contact_service import ContactService
from tests.conftest import readable_test_id


class MutableClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class CountingAIService:
    def __init__(self) -> None:
        self.calls = 0

    def analyze_comment(self, comment: str):
        from app.schemas.ai import AIAnalysisResult, AIServiceResult

        self.calls += 1
        return AIServiceResult(
            status=AiStatus.SUCCESS,
            analysis=AIAnalysisResult(
                sentiment=Sentiment.NEUTRAL,
                category=ContactCategory.PROJECT_REQUEST,
                priority=ContactPriority.NORMAL,
                summary="Тестовое обращение.",
                suggested_reply="Спасибо за обращение.",
            ),
        )


class CountingEmailService:
    def __init__(self) -> None:
        self.owner_calls = 0

    def send_owner_notification(
        self,
        context: EmailTemplateContext,
        recipient_email: str | None = None,
    ) -> EmailSendResult:
        self.owner_calls += 1
        return EmailSendResult(status=EmailStatus.SENT, provider="fake", message_id=f"owner-{self.owner_calls}")


@pytest.fixture
def rate_limit_api_context(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'contact-rate-limit.sqlite3'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    clock = MutableClock()
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'unused.sqlite3'}",
        LOG_FILE_PATH=str(tmp_path / "rate-limit.log"),
        CORS_ORIGINS=["http://testserver"],
        CONTACT_RATE_LIMIT_REQUESTS=2,
        CONTACT_RATE_LIMIT_WINDOW_SECONDS=60,
        TRUST_PROXY_HEADERS=True,
    )
    app = create_app(settings)
    app.state.contact_rate_limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=clock)
    ai_service = CountingAIService()
    email_service = CountingEmailService()

    def override_contact_service() -> ContactService:
        return ContactService(
            repository=ContactRepository(session),
            ai_service=ai_service,
            email_service=email_service,
        )

    app.dependency_overrides[get_contact_service] = override_contact_service

    try:
        yield app, session, clock, ai_service, email_service
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def valid_payload(**overrides) -> dict:
    data = {
        "name": "Иван Иванов",
        "phone": "+7 999 123 45 67",
        "email": "user@example.com",
        "comment": "Хочу обсудить разработку backend-сервиса.",
    }
    data.update(overrides)
    return data


def contact_count(session) -> int:
    return session.execute(select(func.count()).select_from(ContactRequest)).scalar_one()


@readable_test_id("запросы в пределах лимита создают обращения")
def test_contact_requests_within_limit_are_created(rate_limit_api_context, _case_id) -> None:
    """RATE-LIMIT-API-ALLOWED-001: запросы в пределах лимита доходят до pipeline."""
    app, session, _clock, ai_service, email_service = rate_limit_api_context

    with TestClient(app, raise_server_exceptions=False) as client:
        first = client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.1"})
        second = client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.1"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert contact_count(session) == 2
    assert ai_service.calls == 2
    assert email_service.owner_calls == 2


@readable_test_id("превышение лимита возвращает 429 и не вызывает pipeline")
def test_contact_request_over_limit_returns_429_without_pipeline(rate_limit_api_context, caplog, _case_id) -> None:
    """RATE-LIMIT-API-EXCEEDED-001: превышение лимита возвращает безопасный 429."""
    app, session, _clock, ai_service, email_service = rate_limit_api_context
    caplog.set_level(logging.WARNING)

    with TestClient(app, raise_server_exceptions=False) as client:
        client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.2"})
        client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.2"})
        response = client.post(
            "/api/contact",
            json=valid_payload(),
            headers={"X-Forwarded-For": "198.51.100.2", "X-Request-ID": "rate-limit-request"},
        )

    body = response.json()
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert body == {
        "error": {
            "code": "rate_limit_exceeded",
            "message": "Слишком много обращений. Попробуйте повторить позже.",
            "details": [],
        },
        "request_id": "rate-limit-request",
    }
    assert contact_count(session) == 2
    assert ai_service.calls == 2
    assert email_service.owner_calls == 2
    log_text = caplog.text
    assert "event=contact_rate_limit_exceeded" in log_text
    assert "ip_sha256:" in log_text
    assert "198.51.100.2" not in log_text


@readable_test_id("лимит одного ip не блокирует другой ip")
def test_different_ips_have_independent_contact_limits(rate_limit_api_context, _case_id) -> None:
    """RATE-LIMIT-API-INDEPENDENT-IP-001: разные IP имеют независимые лимиты."""
    app, session, _clock, _ai_service, _email_service = rate_limit_api_context

    with TestClient(app, raise_server_exceptions=False) as client:
        client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.3"})
        client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.3"})
        blocked = client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.3"})
        allowed = client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.4"})

    assert blocked.status_code == 429
    assert allowed.status_code == 201
    assert contact_count(session) == 3


@readable_test_id("после истечения окна contact снова принимается")
def test_contact_request_is_allowed_after_rate_limit_window(rate_limit_api_context, _case_id) -> None:
    """RATE-LIMIT-API-WINDOW-001: после перемотки времени запрос снова разрешён."""
    app, session, clock, _ai_service, _email_service = rate_limit_api_context

    with TestClient(app, raise_server_exceptions=False) as client:
        client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.5"})
        client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.5"})
        blocked = client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.5"})
        clock.advance(61)
        allowed = client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.5"})

    assert blocked.status_code == 429
    assert allowed.status_code == 201
    assert contact_count(session) == 3


@readable_test_id("невалидный запрос учитывается rate limiter")
def test_invalid_contact_request_counts_toward_rate_limit(rate_limit_api_context, _case_id) -> None:
    """RATE-LIMIT-API-INVALID-001: невалидные попытки тоже расходуют лимит endpoint."""
    app, session, _clock, ai_service, email_service = rate_limit_api_context
    app.state.contact_rate_limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=MutableClock())

    with TestClient(app, raise_server_exceptions=False) as client:
        invalid = client.post("/api/contact", json=valid_payload(email="not-email"), headers={"X-Forwarded-For": "198.51.100.6"})
        valid = client.post("/api/contact", json=valid_payload(), headers={"X-Forwarded-For": "198.51.100.6"})

    assert invalid.status_code == 422
    assert valid.status_code == 429
    assert contact_count(session) == 0
    assert ai_service.calls == 0
    assert email_service.owner_calls == 0


@readable_test_id("demo запросы не обходят rate limiter")
def test_demo_contact_request_over_limit_returns_429_without_pipeline(rate_limit_api_context, _case_id) -> None:
    """DEMO-RATE-LIMIT-001: demo-поля не участвуют в client key и не обходят лимит endpoint."""
    app, session, _clock, ai_service, email_service = rate_limit_api_context
    app.state.settings.demo_access_token = "demo-secret"

    with TestClient(app, raise_server_exceptions=False) as client:
        client.post(
            "/api/contact",
            json=valid_payload(demo_recipient_email="first@example.com", demo_access_token="demo-secret"),
            headers={"X-Forwarded-For": "198.51.100.8"},
        )
        client.post(
            "/api/contact",
            json=valid_payload(demo_recipient_email="second@example.com", demo_access_token="demo-secret"),
            headers={"X-Forwarded-For": "198.51.100.8"},
        )
        blocked = client.post(
            "/api/contact",
            json=valid_payload(demo_recipient_email="third@example.com", demo_access_token="demo-secret"),
            headers={"X-Forwarded-For": "198.51.100.8"},
        )

    assert blocked.status_code == 429
    assert contact_count(session) == 2
    assert ai_service.calls == 2
    assert email_service.owner_calls == 2


@readable_test_id("honeypot запрос не создает запись и логируется")
def test_honeypot_request_does_not_create_contact_and_is_logged(rate_limit_api_context, caplog, _case_id) -> None:
    """HONEYPOT-API-001: заполненный honeypot останавливается до pipeline и логируется."""
    app, session, _clock, ai_service, email_service = rate_limit_api_context
    caplog.set_level(logging.WARNING)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/contact",
            json=valid_payload(website="bot"),
            headers={"X-Forwarded-For": "198.51.100.7", "X-Request-ID": "honeypot-request"},
        )

    body = response.json()
    assert response.status_code == 422
    assert body["request_id"] == "honeypot-request"
    assert contact_count(session) == 0
    assert ai_service.calls == 0
    assert email_service.owner_calls == 0
    assert "event=contact_honeypot_triggered" in caplog.text
