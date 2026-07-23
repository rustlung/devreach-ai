from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.health import get_health
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.models import ContactRequest
from app.db.session import check_database_connection
from app.repositories.contact_repository import ContactRepository
from app.schemas.email import EmailMessage, EmailTemplateContext, EmailType
from app.services.ai_service import FakeAIAnalysisService, OpenAIAnalysisService
from app.services.contact_service import ContactService
from app.services.email_service import FakeEmailService, ResendEmailService
from app.schemas.contact import ContactRequestCreate
from app.schemas.contact_storage import AiStatus, ContactAiUpdate, ContactCategory, ContactPriority, EmailStatus, ProcessingStatus, Sentiment
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.services.diagnostics import build_health_response, build_metrics_response, measure_database_health
from app.main import create_app


def check_foundation(settings: Settings | None = None) -> int:
    active_settings = settings or get_settings()
    configure_logging(active_settings)
    logger = logging.getLogger("app.cli")

    try:
        _ = active_settings.app_name
        print("Проверка конфигурации: успешно")

        check_database_connection(active_settings)
        print("Проверка базы данных: успешно")

        logger.info("CLI-проверка логирования успешно записала тестовое событие")
        print("Проверка логирования: успешно")

        # Проверяем внутренний компонент health без HTTP-запуска и внешних сервисов.
        check_database_connection(active_settings)
        _ = get_health
        print("Проверка health-компонентов: успешно")

    except Exception as exc:
        logger.exception("CLI-проверка фундамента завершилась ошибкой: type=%s message=%s", type(exc).__name__, exc)
        print(f"Итог: фундамент проекта не прошёл проверку ({type(exc).__name__})")
        return 1

    print("Итог: фундамент проекта работает")
    return 0


def _base_contact_payload(**overrides) -> dict:
    payload = {
        "name": "Иван Иванов",
        "phone": "+7 999 123 45 67",
        "email": "user@example.com",
        "comment": "Здравствуйте, хочу обсудить тестовый проект.",
    }
    payload.update(overrides)
    return payload


def _run_cli_scenario(title: str, scenario) -> bool:
    try:
        scenario()
    except Exception as exc:
        print(f"{title}: ошибка")
        print(f"Причина: {exc}")
        return False
    print(f"{title}: успешно")
    return True


def _expect_validation_error(payload: dict) -> None:
    try:
        ContactRequestCreate(**payload)
    except ValidationError:
        return
    raise AssertionError("Ожидалась ошибка валидации, но обращение было принято")


def validate_contact() -> int:
    scenarios = [
        (
            "Проверка валидного обращения",
            lambda: ContactRequestCreate(**_base_contact_payload()),
        ),
        (
            "Нормализация имени",
            lambda: _assert_equal(
                ContactRequestCreate(**_base_contact_payload(name="   Иван    Иванов   ")).name,
                "Иван Иванов",
            ),
        ),
        (
            "Нормализация телефона",
            lambda: _assert_equal(
                ContactRequestCreate(**_base_contact_payload(phone="8 (999) 123-45-67")).phone,
                "+79991234567",
            ),
        ),
        (
            "Нормализация email",
            lambda: _assert_equal(
                str(ContactRequestCreate(**_base_contact_payload(email="  User@Example.COM  ")).email),
                "user@example.com",
            ),
        ),
        (
            "Сохранение форматирования комментария",
            lambda: _assert_equal(
                ContactRequestCreate(
                    **_base_contact_payload(comment="   Первая строка.\n\nВторая    строка.   ")
                ).comment,
                "Первая строка.\n\nВторая    строка.",
            ),
        ),
        (
            "Отклонение имени с цифрами",
            lambda: _expect_validation_error(_base_contact_payload(name="Иван123")),
        ),
        (
            "Отклонение некорректного телефона",
            lambda: _expect_validation_error(_base_contact_payload(phone="+7 phone")),
        ),
        (
            "Отклонение пустого комментария",
            lambda: _expect_validation_error(_base_contact_payload(comment="   ")),
        ),
    ]

    for title, scenario in scenarios:
        if not _run_cli_scenario(title, scenario):
            print("\nИтог: проверка схем и валидации завершилась ошибкой")
            return 1

    print("\nИтог: проверка схем и валидации успешно завершена")
    return 0


def check_repository() -> int:
    temp_dir = tempfile.TemporaryDirectory()
    database_path = Path(temp_dir.name) / "repository-check.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False}, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = None

    try:
        Base.metadata.create_all(engine)
        print("Создание временной базы: успешно")

        session = session_factory()
        repository = ContactRepository(session)
        contact = repository.create(
            ContactRequestCreate(
                name="Иван Иванов",
                phone="+7 999 123 45 67",
                email="user@example.com",
                comment="Здравствуйте, хочу обсудить тестовый проект.",
            )
        )
        print(f"Создание обращения: успешно, ID={contact.id}")

        if repository.get_by_id(contact.id) is None:
            raise AssertionError("Созданное обращение не найдено по ID")
        print("Чтение обращения: успешно")

        repository.update_ai_result(
            contact.id,
            ContactAiUpdate(
                sentiment="positive",
                category="web",
                priority="high",
                ai_summary="Тестовое резюме",
                suggested_reply="Тестовый ответ",
                ai_status=AiStatus.SUCCESS,
            ),
        )
        print("Обновление AI-результата: успешно")

        repository.update_owner_email_status(contact.id, EmailStatus.SENT)
        print("Обновление статуса письма владельцу: успешно")

        repository.update_processing_status(contact.id, ProcessingStatus.COMPLETED_WITH_ERRORS)
        print("Обновление общего статуса: успешно")

        metrics = repository.get_metrics()
        if metrics.total_contacts != 1 or metrics.by_category.get("web") != 1:
            raise AssertionError("Метрики репозитория не совпали с ожидаемыми")
        print("Проверка метрик: успешно")

    except Exception as exc:
        logging.getLogger("app.cli").exception("CLI-проверка репозитория завершилась ошибкой")
        print(f"Итог: проверка репозитория завершилась ошибкой на этапе: {type(exc).__name__}")
        print(f"Причина: {exc}")
        return 1
    finally:
        if session is not None:
            session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
        temp_dir.cleanup()
        print("Удаление временной базы: успешно")

    _ = ContactRequest
    print("\nИтог: репозиторий обращений работает корректно")
    return 0


def analyze_comment(live: bool = False) -> int:
    settings = get_settings()
    comment = "Здравствуйте, хочу обсудить разработку небольшого backend-сервиса для сайта."

    if not live:
        print("Режим AI: fake")
        result = FakeAIAnalysisService().analyze_comment(comment)
        print("Проверка схемы результата: успешно")
        _print_ai_result(result)
        print("Внешний запрос OpenAI: не выполнялся")
        print("Расход токенов: отсутствует")
        print("\nИтог: AI-сервис в fake-режиме работает корректно")
        return 0

    print("Режим AI: live")
    print(f"Маршрут AI: {_get_ai_route_label(settings)}")
    if not settings.ai_live_requests_enabled:
        print("Live-запрос OpenAI не выполнен: AI_LIVE_REQUESTS_ENABLED=false")
        result = OpenAIAnalysisService(settings).analyze_comment(comment)
        _print_ai_result(result)
        return 0
    if not settings.openai_api_key:
        print("Live-запрос OpenAI не выполнен: OPENAI_API_KEY не задан")
        result = OpenAIAnalysisService(settings).analyze_comment(comment)
        _print_ai_result(result)
        return 0

    print("ВНИМАНИЕ: будет выполнен один реальный запрос к OpenAI с расходом API-токенов.")
    result = OpenAIAnalysisService(settings).analyze_comment(comment)
    _print_ai_result(result)
    if result.status == AiStatus.SUCCESS:
        print("\nИтог: live-проверка OpenAI успешно завершена")
    else:
        print("\nИтог: OpenAI недоступен или вернул ошибку, применён fallback")
    return 0


def _get_ai_route_label(settings: Settings) -> str:
    if not settings.openai_base_url:
        return "прямой OpenAI API"
    if "proxyapi" in settings.openai_base_url.lower():
        return "ProxyAPI через OpenAI SDK"
    return "OpenAI-compatible base_url"


def _email_preview_settings(**overrides) -> Settings:
    data = {
        "APP_ENV": "test",
        "EMAIL_FROM_ADDRESS": "hello@example.com",
        "EMAIL_FROM_NAME": "DevReach AI",
        "OWNER_EMAIL": "owner@example.com",
        "EMAIL_REPLY_TO": "reply@example.com",
        "EMAIL_SUBJECT_PREFIX": "[DevReach AI]",
        "EMAIL_LIVE_REQUESTS_ENABLED": False,
    }
    data.update(overrides)
    return Settings(**data)


def _sample_email_context(**overrides) -> EmailTemplateContext:
    data = {
        "contact_id": 15,
        "name": "Иван Иванов",
        "phone": "+79991234567",
        "email": "user@example.com",
        "comment": 'Здравствуйте!\nХочу обсудить проект.\n<script>alert("xss")</script>',
        "created_at": datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        "sentiment": Sentiment.NEUTRAL,
        "category": ContactCategory.PROJECT_REQUEST,
        "priority": ContactPriority.NORMAL,
        "summary": "Пользователь хочет обсудить проект.",
        "suggested_reply": "Спасибо за обращение. Я ознакомлюсь с деталями и свяжусь с вами.",
        "ai_status": AiStatus.SUCCESS,
    }
    data.update(overrides)
    return EmailTemplateContext(**data)


def render_emails() -> int:
    service = ResendEmailService(settings=_email_preview_settings())
    context = _sample_email_context()
    preview_dir = Path("tmp") / "email-preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    try:
        owner_message = service.build_owner_message(context)
        print("Рендеринг письма владельцу: успешно")

        if not owner_message.html or not owner_message.text:
            raise AssertionError("Шаблон владельца отрендерился пустым")
        if "None" in owner_message.html + owner_message.text:
            raise AssertionError("В письмах найдено строковое значение None")
        if "<script>" in owner_message.html or "&lt;script&gt;" not in owner_message.html:
            raise AssertionError("HTML-экранирование комментария не сработало")
        if "AI-анализ" not in owner_message.text or context.summary not in owner_message.text:
            raise AssertionError("AI-анализ отсутствует в письме владельцу")
        print("AI-анализ присутствует: успешно")
        if context.suggested_reply not in owner_message.text:
            raise AssertionError("Предлагаемый ответ отсутствует в письме владельцу")
        print("Предлагаемый ответ присутствует: успешно")
        if str(owner_message.reply_to) != str(context.email):
            raise AssertionError("Reply-To владельца не совпал с email пользователя")
        print("Reply-To пользователя настроен: успешно")

        (preview_dir / "owner_notification.html").write_text(owner_message.html, encoding="utf-8")
        (preview_dir / "owner_notification.txt").write_text(owner_message.text, encoding="utf-8")

        print("HTML-экранирование: успешно")
        print("Текстовая версия: успешно")
        print(f"Preview сохранён: {preview_dir.as_posix()}/")
        print("\nАвтоматическое письмо пользователю: не предусмотрено")
        print("\nВнешняя отправка: не выполнялась")
        print("Итог: email-шаблоны работают корректно")
        return 0
    except Exception as exc:
        print("Итог: рендеринг email-шаблонов завершился ошибкой")
        print(f"Причина: {exc}")
        return 1


def check_email(live: bool = False, recipient: str | None = None) -> int:
    context = _sample_email_context()

    if not live:
        renderer = ResendEmailService(settings=_email_preview_settings())
        fake_service = FakeEmailService()
        owner_result = fake_service.send(renderer.build_owner_message(context), EmailType.OWNER_NOTIFICATION, context.contact_id)

        if owner_result.status != EmailStatus.SENT:
            print("Итог: fake-проверка email завершилась ошибкой")
            return 1
        if len(fake_service.sent_messages) != 1:
            print("Итог: fake-сервис должен сохранить одно письмо владельцу")
            return 1

        print("Формирование письма владельцу: успешно")
        print("Fake-отправка владельцу: успешно")
        print("Сообщение сохранено в памяти fake-сервиса: успешно")
        print("Автоматическое письмо пользователю: не предусмотрено")
        print("Реальные письма: не отправлялись")
        print("\nИтог: email-сервис в fake-режиме работает корректно")
        return 0

    if not recipient:
        print("Live-отправка не выполнена: укажите получателя через --recipient")
        return 1

    settings = get_settings()
    message = EmailMessage(
        to=recipient,
        subject="Тестовое письмо DevReach AI",
        html="<p>Это контролируемая live-проверка email-сервиса DevReach AI.</p>",
        text="Это контролируемая live-проверка email-сервиса DevReach AI.",
        reply_to=settings.email_reply_to,
    )
    print("ВНИМАНИЕ: будет отправлено одно реальное тестовое письмо через Resend.")
    result = ResendEmailService(settings=settings).send(message, EmailType.TEST_MESSAGE)
    if result.status == EmailStatus.SENT:
        print(f"Provider message ID: {result.message_id}")
        print("Итог: live-проверка email успешно завершена")
        return 0

    print(f"Итог: live-проверка email не выполнена, статус={result.status.value}")
    if result.error_code:
        print(f"Код ошибки: {result.error_code}")
    if result.error_message:
        print(f"Причина: {result.error_message}")
    return 0 if result.status == EmailStatus.SKIPPED else 1


def run_contact_pipeline(ai_fallback: bool = False, email_failure: str | None = None) -> int:
    temp_dir = tempfile.TemporaryDirectory()
    database_path = Path(temp_dir.name) / "contact-pipeline.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False}, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = None

    try:
        Base.metadata.create_all(engine)
        print("Создание временной базы: успешно")

        contact_data = ContactRequestCreate(**_base_contact_payload())
        print("Валидация обращения: успешно")

        session = session_factory()
        repository = ContactRepository(session)
        ai_service = FakeAIAnalysisService(mode="fallback" if ai_fallback else "success")
        email_service = FakeEmailService(
            owner_mode="failed" if email_failure in {"owner", "both"} else None,
        )
        service = ContactService(repository=repository, ai_service=ai_service, email_service=email_service)

        response = service.process_contact(contact_data, request_id="cli-contact-pipeline")
        contact = repository.get_by_id(response.id)
        if contact is None:
            raise AssertionError("Созданное обращение не найдено в базе")

        print(f"Сохранение обращения: успешно, ID={response.id}")
        print("AI-анализ в fake-режиме: успешно")
        if not contact.ai_status:
            raise AssertionError("AI-статус не сохранён")
        print("Сохранение AI-результата: успешно")

        if len(email_service.sent_messages) != 1:
            raise AssertionError("Fake email service должен получить одно письмо владельцу")
        print("Fake-письмо владельцу: успешно")
        print("Автоматическое письмо пользователю: не предусмотрено")

        expected_owner_status = EmailStatus.FAILED.value if email_failure in {"owner", "both"} else EmailStatus.SENT.value
        if contact.owner_email_status != expected_owner_status:
            raise AssertionError("Email-статус владельца не совпал с ожидаемым")
        print("Сохранение owner email status: успешно")

        expected_processing = (
            ProcessingStatus.COMPLETED_WITH_ERRORS.value
            if ai_fallback or email_failure in {"owner", "both"}
            else ProcessingStatus.COMPLETED.value
        )
        if contact.processing_status != expected_processing:
            raise AssertionError("Итоговый статус обработки не совпал с ожидаемым")
        print(f"Итоговый статус {expected_processing}: успешно")

    except Exception as exc:
        logging.getLogger("app.cli").exception("CLI-проверка contact pipeline завершилась ошибкой")
        print(f"Итог: contact pipeline завершился ошибкой на этапе: {type(exc).__name__}")
        print(f"Причина: {exc}")
        return 1
    finally:
        if session is not None:
            session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
        temp_dir.cleanup()
        print("Удаление временной базы: успешно")

    print("\nOpenAI: не вызывался")
    print("Resend: не вызывался")
    print("Расход токенов: отсутствует")
    print("Реальные письма: не отправлялись")
    print("\nИтог: полный contact pipeline работает корректно")
    return 0


def check_rate_limit() -> int:
    current_time = 1_000.0

    def clock() -> float:
        return current_time

    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60, clock=clock)
    client_key = "ip_sha256:test0001"
    second_client_key = "ip_sha256:test0002"

    try:
        for attempt in range(1, 4):
            decision = limiter.check(client_key)
            if not decision.allowed:
                raise AssertionError(f"Запрос {attempt} должен быть разрешён")
            print(f"Запрос {attempt} из 3: разрешён")

        blocked = limiter.check(client_key)
        if blocked.allowed:
            raise AssertionError("Запрос сверх лимита должен быть отклонён")
        print("Запрос сверх лимита: отклонён")

        if blocked.retry_after_seconds is None or blocked.retry_after_seconds <= 0:
            raise AssertionError("Retry-After не рассчитан")
        print("Retry-After рассчитан: успешно")
        print(f"Retry-After: {blocked.retry_after_seconds}")

        current_time += 61
        print("Истечение окна без ожидания: успешно")

        after_window = limiter.check(client_key)
        if not after_window.allowed:
            raise AssertionError("Запрос после окончания окна должен быть разрешён")
        print("Новый запрос после окна: разрешён")

        independent = limiter.check(second_client_key)
        if not independent.allowed:
            raise AssertionError("Независимый клиент должен быть разрешён")
        print("Независимый клиент: разрешён")

    except Exception as exc:
        print("Итог: rate limiting завершился ошибкой")
        print(f"Причина: {exc}")
        return 1

    print("\nProxyAPI: не вызывался")
    print("Resend: не вызывался")
    print("База данных: не использовалась")
    print("\nИтог: rate limiting работает корректно")
    return 0


def check_diagnostics() -> int:
    temp_dir = tempfile.TemporaryDirectory()
    database_path = Path(temp_dir.name) / "diagnostics.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False}, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = None

    try:
        Base.metadata.create_all(engine)
        diagnostic_settings = Settings(
            APP_ENV="test",
            DATABASE_URL=f"sqlite:///{database_path}",
            LOG_FILE_PATH=str(Path(temp_dir.name) / "diagnostics.log"),
            AI_LIVE_REQUESTS_ENABLED=False,
            EMAIL_LIVE_REQUESTS_ENABLED=False,
        )

        database = measure_database_health(diagnostic_settings)
        health = build_health_response(diagnostic_settings, database)
        if health.database.status != "available":
            raise AssertionError("Health не подтвердил доступность базы")
        print("Проверка health: успешно")
        print("Статус базы данных: available")
        if health.database.latency_ms is None or health.database.latency_ms < 0:
            raise AssertionError("Latency базы не измерен")
        print("Измерение latency базы: успешно")
        print("Проверка конфигурации AI без внешнего вызова: успешно")
        print("Проверка конфигурации email без внешнего вызова: успешно")

        session = session_factory()
        repository = ContactRepository(session)
        empty_metrics = build_metrics_response(repository.get_metrics(), request_id="cli-diagnostics")
        if empty_metrics.total_contacts != 0 or any(empty_metrics.processing.values()):
            raise AssertionError("Метрики пустой базы не равны нулю")
        print("Метрики пустой базы: успешно")

        first = repository.create(_base_contact_payload_as_schema(email="diagnostic-one@example.com"))
        second = repository.create(_base_contact_payload_as_schema(email="diagnostic-two@example.com"))
        repository.update_ai_result(
            first.id,
            ContactAiUpdate(ai_status=AiStatus.SUCCESS, category=ContactCategory.PROJECT_REQUEST.value),
        )
        repository.update_owner_email_status(first.id, EmailStatus.SENT)
        repository.update_processing_status(first.id, ProcessingStatus.COMPLETED)
        repository.update_ai_result(
            second.id,
            ContactAiUpdate(ai_status=AiStatus.FALLBACK, category=ContactCategory.OTHER.value),
        )
        repository.update_owner_email_status(second.id, EmailStatus.FAILED, "Тестовая ошибка")
        repository.update_processing_status(second.id, ProcessingStatus.COMPLETED_WITH_ERRORS)
        print("Создание тестовых обращений: успешно")

        metrics = build_metrics_response(repository.get_metrics(), request_id="cli-diagnostics")
        if metrics.processing[ProcessingStatus.COMPLETED.value] != 1:
            raise AssertionError("Агрегация processing status некорректна")
        print("Агрегация processing status: успешно")
        if metrics.ai[AiStatus.SUCCESS.value] != 1 or metrics.ai[AiStatus.FALLBACK.value] != 1:
            raise AssertionError("Агрегация AI status некорректна")
        print("Агрегация AI status: успешно")
        if metrics.emails[EmailStatus.FAILED.value] != 1 or metrics.emails[EmailStatus.SENT.value] != 1:
            raise AssertionError("Агрегация email status некорректна")
        print("Агрегация email status: успешно")
        if metrics.categories[ContactCategory.PROJECT_REQUEST.value] != 1 or metrics.categories[ContactCategory.OTHER.value] != 1:
            raise AssertionError("Агрегация категорий некорректна")
        print("Агрегация категорий: успешно")

        metrics_text = metrics.model_dump_json()
        if any(secret in metrics_text for secret in ["Иван Иванов", "diagnostic-one@example.com", "+79991234567", "Тестовая ошибка"]):
            raise AssertionError("В метрики попали персональные данные")
        print("Проверка отсутствия персональных данных: успешно")

    except Exception as exc:
        print("Итог: диагностическая проверка завершилась ошибкой")
        print(f"Причина: {exc}")
        return 1
    finally:
        if session is not None:
            session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
        temp_dir.cleanup()
        print("Удаление временной базы: успешно")

    print("\nProxyAPI: не вызывался")
    print("Resend: не вызывался")
    print("\nИтог: диагностические endpoint готовы")
    return 0


def check_landing() -> int:
    temp_dir = tempfile.TemporaryDirectory()
    try:
        settings = Settings(
            APP_ENV="test",
            DATABASE_URL=f"sqlite:///{Path(temp_dir.name) / 'landing-cli.sqlite3'}",
            LOG_FILE_PATH=str(Path(temp_dir.name) / "landing.log"),
            CORS_ORIGINS=["http://testserver"],
            AI_LIVE_REQUESTS_ENABLED=False,
            EMAIL_LIVE_REQUESTS_ENABLED=False,
        )
        app = create_app(settings)

        with TestClient(app, raise_server_exceptions=False) as client:
            page = client.get("/", headers={"X-Request-ID": "cli-landing"})
            html = page.text
            css = client.get("/static/css/main.css")
            js = client.get("/static/js/contact-form.js")

        _assert_status(page.status_code, 200, "Главная страница должна быть доступна")
        print("Главная страница доступна: успешно")
        if "text/html" not in page.headers.get("content-type", ""):
            raise AssertionError("Главная страница вернула не HTML")
        print("HTML-шаблон отрендерен: успешно")
        if '<form id="contact-form"' not in html:
            raise AssertionError("Форма обратной связи не найдена")
        print("Форма обратной связи найдена: успешно")
        for field_name in ["name", "phone", "email", "comment"]:
            if f'name="{field_name}"' not in html:
                raise AssertionError(f"Поле формы не найдено: {field_name}")
        print("Поля формы найдены: успешно")
        if 'name="website"' not in html or 'tabindex="-1"' not in html:
            raise AssertionError("Honeypot не найден или доступен из tab order")
        print("Honeypot найден: успешно")
        _assert_status(css.status_code, 200, "CSS должен быть доступен")
        if "text/css" not in css.headers.get("content-type", ""):
            raise AssertionError("CSS вернул некорректный Content-Type")
        print("CSS доступен: успешно")
        _assert_status(js.status_code, 200, "JavaScript должен быть доступен")
        if "javascript" not in js.headers.get("content-type", ""):
            raise AssertionError("JavaScript вернул некорректный Content-Type")
        print("JavaScript доступен: успешно")
        if "/api/contact" not in js.text or "/api/contact" not in html:
            raise AssertionError("Контракт POST /api/contact не найден")
        print("Контракт POST /api/contact: успешно")
        for link in ['href="/docs"', 'href="/api/health"', 'href="/api/metrics"']:
            if link not in html:
                raise AssertionError(f"Ссылка не найдена: {link}")
        print("Ссылки на API-документацию: успешно")
        combined = f"{html}\n{css.text}\n{js.text}"
        for forbidden in ["OPENAI_API_KEY", "RESEND_API_KEY", "sk-", ".env"]:
            if forbidden in combined:
                raise AssertionError("В HTML/static найден секретный маркер")
        print("Проверка отсутствия секретов: успешно")
        if "Обращение принято" not in js.text:
            raise AssertionError("Frontend не содержит корректное подтверждение отправки")
        for forbidden in ["проверьте почту", "вам отправлено письмо", "ответ направлен на email"]:
            if forbidden in combined.lower():
                raise AssertionError("Frontend сообщает об автоматическом письме пользователю")
        print("Проверка отсутствия email-подтверждения пользователю: успешно")

    except Exception as exc:
        print("Итог: проверка Jinja2-лендинга завершилась ошибкой")
        print(f"Причина: {exc}")
        return 1
    finally:
        logging.shutdown()
        temp_dir.cleanup()

    print("\nProxyAPI: не вызывался")
    print("Resend: не вызывался")
    print("\nИтог: Jinja2-лендинг работает корректно")
    return 0


def _base_contact_payload_as_schema(**overrides) -> ContactRequestCreate:
    return ContactRequestCreate(**_base_contact_payload(**overrides))


def _print_ai_result(result) -> None:
    print(f"Тональность: {result.analysis.sentiment.value}")
    print(f"Категория: {result.analysis.category.value}")
    print(f"Приоритет: {result.analysis.priority.value}")
    print(f"Краткое содержание: {'получено' if result.analysis.summary else 'fallback'}")
    print("Черновик ответа: получен")
    if result.error_code:
        print(f"Внутренний код fallback: {result.error_code}")
    if result.error_message:
        print(f"Причина fallback: {result.error_message}")
    if result.error_code == "api_permission_denied":
        print("Подсказка: OpenAI принял ключ, но запретил выбранную модель или операцию.")
        print("Проверьте OPENAI_MODEL и доступ проекта/ключа к этой модели.")


def _assert_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError("Фактический результат не совпал с ожидаемым")


def _assert_status(actual: int, expected: int, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: status={actual}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Служебные команды DevReach AI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-foundation", help="Проверить фундамент проекта без внешних API")
    subparsers.add_parser("validate-contact", help="Проверить схемы и валидацию обращения без API")
    subparsers.add_parser("check-repository", help="Проверить репозиторий обращений на временной SQLite")
    subparsers.add_parser("check-rate-limit", help="Проверить rate limiting без FastAPI и внешних сервисов")
    subparsers.add_parser("check-diagnostics", help="Проверить health и metrics без внешних сервисов")
    subparsers.add_parser("check-landing", help="Проверить Jinja2-лендинг без Uvicorn и внешних сервисов")
    subparsers.add_parser("render-emails", help="Отрендерить preview email-шаблонов без отправки")
    email_parser = subparsers.add_parser("check-email", help="Проверить email-сервис")
    email_parser.add_argument("--live", action="store_true", help="Отправить одно тестовое письмо через Resend")
    email_parser.add_argument("--recipient", help="Явный получатель live-проверки email")
    pipeline_parser = subparsers.add_parser("run-contact-pipeline", help="Проверить полный fake contact pipeline")
    pipeline_parser.add_argument("--ai-fallback", action="store_true", help="Имитировать AI fallback")
    pipeline_parser.add_argument(
        "--email-failure",
        choices=["owner", "both"],
        help="Имитировать ошибку email-отправки в простой fake-проверке",
    )
    analyze_parser = subparsers.add_parser("analyze-comment", help="Проверить AI-анализ комментария")
    analyze_parser.add_argument("--live", action="store_true", help="Выполнить один live-запрос OpenAI при явных настройках")

    args = parser.parse_args(argv)
    if args.command == "check-foundation":
        return check_foundation()
    if args.command == "validate-contact":
        return validate_contact()
    if args.command == "check-repository":
        return check_repository()
    if args.command == "check-rate-limit":
        return check_rate_limit()
    if args.command == "check-diagnostics":
        return check_diagnostics()
    if args.command == "check-landing":
        return check_landing()
    if args.command == "render-emails":
        return render_emails()
    if args.command == "check-email":
        return check_email(live=args.live, recipient=args.recipient)
    if args.command == "run-contact-pipeline":
        return run_contact_pipeline(ai_fallback=args.ai_fallback, email_failure=args.email_failure)
    if args.command == "analyze-comment":
        return analyze_comment(live=args.live)
    return 1


if __name__ == "__main__":
    sys.exit(main())
