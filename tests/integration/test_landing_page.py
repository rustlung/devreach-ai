import re

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_contact_service
from app.core.config import Settings
from app.db.base import Base
from app.repositories.contact_repository import ContactRepository
from app.main import create_app
from app.services.ai_service import FakeAIAnalysisService
from app.services.contact_service import ContactService
from app.services.email_service import FakeEmailService
from tests.conftest import readable_test_id


SECRET_MARKERS = [
    "OPENAI_API_KEY",
    "RESEND_API_KEY",
    "sk-",
    "re_",
    ".env",
    "v.i.sigaev",
]


@readable_test_id("главная страница возвращает html и request id")
def test_landing_page_returns_html_with_request_id(client: TestClient, _case_id) -> None:
    """LANDING-PAGE-001: GET / отдаёт HTML-страницу и сохраняет request ID."""
    response = client.get("/", headers={"X-Request-ID": "landing-request"})
    html = response.text

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["X-Request-ID"] == "landing-request"
    assert '<form id="contact-form"' in html
    assert 'action="http' not in html
    assert 'href="/docs"' in html
    assert 'href="/api/health"' in html
    assert 'href="/api/metrics"' in html
    assert 'href="/static/css/main.css"' in html
    assert 'src="/static/js/contact-form.js"' in html


@readable_test_id("landing содержит поля формы и honeypot")
def test_landing_page_contains_contact_fields_and_honeypot(client: TestClient, _case_id) -> None:
    """LANDING-FORM-FIELDS-001: HTML содержит ожидаемые поля формы обращения."""
    html = client.get("/").text

    assert 'name="name"' in html
    assert 'name="phone"' in html
    assert 'name="email"' in html
    assert 'name="comment"' in html
    assert 'name="website"' in html
    assert 'class="visually-hidden-trap"' in html
    assert 'tabindex="-1"' in html
    assert 'autocomplete="off"' in html
    assert 'name="demo_recipient_email"' in html
    assert 'name="demo_access_token"' in html


@readable_test_id("landing содержит label ограничения и aria live")
def test_landing_page_form_has_accessible_markup(client: TestClient, _case_id) -> None:
    """LANDING-ACCESSIBILITY-001: форма имеет labels, ограничения, submit button и aria-live."""
    html = client.get("/").text

    for field_id in [
        "contact-name",
        "contact-phone",
        "contact-email",
        "contact-comment",
        "contact-website",
        "contact-demo-enabled",
        "contact-demo-recipient-email",
        "contact-demo-access-token",
    ]:
        assert f'for="{field_id}"' in html
        assert f'id="{field_id}"' in html

    assert 'type="submit"' in html
    assert 'aria-live="polite"' in html
    assert "required" in html
    assert 'minlength="2"' in html
    assert 'maxlength="80"' in html
    assert 'maxlength="254"' in html
    assert 'maxlength="5000"' in html
    assert 'autocomplete="name"' in html
    assert 'autocomplete="tel"' in html
    assert 'autocomplete="email"' in html
    assert not re.search(r"\son[a-z]+\s*=", html)


@readable_test_id("landing и static не раскрывают секреты")
def test_landing_assets_do_not_expose_secrets(client: TestClient, _case_id) -> None:
    """LANDING-NO-SECRETS-001: HTML/CSS/JS не содержат ключи и значения .env."""
    html = client.get("/").text
    css = client.get("/static/css/main.css").text
    js = client.get("/static/js/contact-form.js").text
    combined = f"{html}\n{css}\n{js}"

    for marker in SECRET_MARKERS:
        assert marker not in combined


@readable_test_id("css файл доступен с корректным content type")
def test_landing_static_css_is_available(client: TestClient, _case_id) -> None:
    """LANDING-STATIC-CSS-001: CSS доступен через StaticFiles."""
    response = client.get("/static/css/main.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert ":root" in response.text


@readable_test_id("js файл доступен и использует api contact")
def test_landing_static_js_is_available_and_targets_contact_api(client: TestClient, _case_id) -> None:
    """LANDING-STATIC-JS-001: JS доступен и отправляет форму на /api/contact."""
    response = client.get("/static/js/contact-form.js")
    js = response.text

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert 'const API_ENDPOINT = "/api/contact";' in js
    assert 'method: "POST"' in js
    assert '"Content-Type": "application/json"' in js


@readable_test_id("js contract обрабатывает ошибки без innerHTML")
def test_landing_frontend_contract_handles_errors_safely(client: TestClient, _case_id) -> None:
    """LANDING-FRONTEND-CONTRACT-001: JS покрывает 422, 429, server/network и не использует innerHTML."""
    js = client.get("/static/js/contact-form.js").text

    assert "response.status === 422" in js
    assert "response.status === 403" in js
    assert "response.status === 429" in js
    assert "Режим демонстрационной проверки недоступен" in js
    assert "Не удалось отправить обращение" in js
    assert "Не удалось связаться с сервером" in js
    assert "content-type" in js
    assert "application/json" in js
    assert "textContent" in js
    assert "innerHTML" not in js


@readable_test_id("frontend не обещает email пользователю")
def test_landing_frontend_does_not_claim_user_email_confirmation(client: TestClient, _case_id) -> None:
    """UI-NO-EMAIL-CONFIRMATION-001: frontend не сообщает об автоматическом письме пользователю."""
    html = client.get("/").text
    js = client.get("/static/js/contact-form.js").text
    combined = f"{html}\n{js}".lower()

    assert "обращение принято" in js.lower()
    assert "обращение принято." in js.lower()
    for forbidden in ["проверьте почту", "вам отправлено письмо", "ответ направлен на email"]:
        assert forbidden not in combined


@readable_test_id("landing demo блок скрыт и доступен")
def test_landing_demo_block_is_present_hidden_and_accessible(client: TestClient, _case_id) -> None:
    """DEMO-LANDING-001: landing содержит скрытый demo-блок с доступными полями."""
    html = client.get("/").text

    assert "Демонстрационная проверка email" in html
    assert "Получить результат обработки на свой email" in html
    assert "Email для получения результата" in html
    assert "Код демонстрационной проверки" in html
    assert 'id="contact-demo-fields"' in html
    assert 'hidden' in html
    assert 'aria-controls="contact-demo-fields"' in html
    assert 'aria-expanded="false"' in html
    assert 'type="password"' in html
    assert 'autocomplete="email"' in html
    assert 'autocomplete="off"' in html
    assert "DEMO_ACCESS_TOKEN" not in html
    assert "OWNER_EMAIL" not in html


@readable_test_id("landing js отправляет demo поля только в demo режиме")
def test_landing_js_sends_demo_fields_only_when_enabled(client: TestClient, _case_id) -> None:
    """DEMO-LANDING-JS-001: JS добавляет demo-поля только при включенном checkbox."""
    js = client.get("/static/js/contact-form.js").text

    assert "isDemoModeEnabled()" in js
    assert "payload.demo_recipient_email" in js
    assert "payload.demo_access_token" in js
    assert "setDemoFieldsEnabled(false)" in js
    assert "Результат обработки отправлен на указанный email" in js
    assert "innerHTML" not in js


@readable_test_id("landing не подключает внешние scripts и inline handlers")
def test_landing_security_has_no_external_scripts_or_inline_handlers(client: TestClient, _case_id) -> None:
    """LANDING-SECURITY-001: страница не содержит внешние scripts и inline event handlers."""
    html = client.get("/").text

    assert not re.search(r'<script[^>]+src="https?://', html)
    assert not re.search(r"\son[a-z]+\s*=", html)
    assert "<iframe" not in html.lower()
    assert "innerHTML" not in html


@readable_test_id("landing response совместим с api contact 201")
def test_landing_api_compatibility_accepts_contact_payload(tmp_path, _case_id) -> None:
    """LANDING-API-COMPATIBILITY-001: сценарий frontend совместим с фактическим 201 API."""
    app, session, engine = build_landing_contact_app(tmp_path)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            page = client.get("/")
            response = client.post(
                "/api/contact",
                json={
                    "name": "Иван Иванов",
                    "phone": "+7 999 123 45 67",
                    "email": "user@example.com",
                    "comment": "Хочу обсудить backend-сервис.",
                    "website": "",
                },
                headers={"X-Request-ID": "landing-contact"},
            )
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()

    payload = response.json()
    assert page.status_code == 200
    assert response.status_code == 201
    assert payload["message"] == "Обращение принято"
    assert payload["request_id"] == "landing-contact"


def build_landing_contact_app(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'landing-contact.sqlite3'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'unused.sqlite3'}",
        LOG_FILE_PATH=str(tmp_path / "landing.log"),
        CORS_ORIGINS=["http://testserver"],
    )
    app = create_app(settings)

    def override_contact_service() -> ContactService:
        return ContactService(
            repository=ContactRepository(session),
            ai_service=FakeAIAnalysisService(mode="success"),
            email_service=FakeEmailService(),
        )

    app.dependency_overrides[get_contact_service] = override_contact_service
    return app, session, engine
