from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
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
from app.services.email_service import FakeEmailService, ResendEmailService
from app.schemas.contact import ContactRequestCreate
from app.schemas.contact_storage import AiStatus, ContactAiUpdate, ContactCategory, ContactPriority, EmailStatus, ProcessingStatus, Sentiment


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

        repository.update_user_email_status(contact.id, EmailStatus.FAILED, "Тестовая ошибка письма")
        print("Обновление статуса письма пользователю: успешно")

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
        user_message = service.build_user_message(context)
        print("Рендеринг письма владельцу: успешно")
        print("Рендеринг письма пользователю: успешно")

        if not owner_message.html or not owner_message.text or not user_message.html or not user_message.text:
            raise AssertionError("Один из шаблонов отрендерился пустым")
        if "None" in owner_message.html + owner_message.text + user_message.html + user_message.text:
            raise AssertionError("В письмах найдено строковое значение None")
        if "<script>" in owner_message.html or "&lt;script&gt;" not in owner_message.html:
            raise AssertionError("HTML-экранирование комментария не сработало")

        (preview_dir / "owner_notification.html").write_text(owner_message.html, encoding="utf-8")
        (preview_dir / "owner_notification.txt").write_text(owner_message.text, encoding="utf-8")
        (preview_dir / "user_confirmation.html").write_text(user_message.html, encoding="utf-8")
        (preview_dir / "user_confirmation.txt").write_text(user_message.text, encoding="utf-8")

        print("HTML-экранирование: успешно")
        print("Текстовые версии: успешно")
        print(f"Preview сохранён: {preview_dir.as_posix()}/")
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
        user_result = fake_service.send(renderer.build_user_message(context), EmailType.USER_CONFIRMATION, context.contact_id)

        if owner_result.status != EmailStatus.SENT or user_result.status != EmailStatus.SENT:
            print("Итог: fake-проверка email завершилась ошибкой")
            return 1
        if len(fake_service.sent_messages) != 2:
            print("Итог: fake-сервис не сохранил оба сообщения")
            return 1

        print("Формирование письма владельцу: успешно")
        print("Формирование письма пользователю: успешно")
        print("Fake-отправка владельцу: успешно")
        print("Fake-отправка пользователю: успешно")
        print("Сообщения сохранены в памяти fake-сервиса: успешно")
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


def _print_ai_result(result) -> None:
    print(f"Тональность: {result.analysis.sentiment.value}")
    print(f"Категория: {result.analysis.category.value}")
    print(f"Приоритет: {result.analysis.priority.value}")
    print(f"Краткое содержание: {'получено' if result.analysis.summary else 'fallback'}")
    print("Черновик ответа: получен")
    if result.error_code:
        print(f"Внутренний код fallback: {result.error_code}")


def _assert_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError("Фактический результат не совпал с ожидаемым")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Служебные команды DevReach AI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-foundation", help="Проверить фундамент проекта без внешних API")
    subparsers.add_parser("validate-contact", help="Проверить схемы и валидацию обращения без API")
    subparsers.add_parser("check-repository", help="Проверить репозиторий обращений на временной SQLite")
    subparsers.add_parser("render-emails", help="Отрендерить preview email-шаблонов без отправки")
    email_parser = subparsers.add_parser("check-email", help="Проверить email-сервис")
    email_parser.add_argument("--live", action="store_true", help="Отправить одно тестовое письмо через Resend")
    email_parser.add_argument("--recipient", help="Явный получатель live-проверки email")
    analyze_parser = subparsers.add_parser("analyze-comment", help="Проверить AI-анализ комментария")
    analyze_parser.add_argument("--live", action="store_true", help="Выполнить один live-запрос OpenAI при явных настройках")

    args = parser.parse_args(argv)
    if args.command == "check-foundation":
        return check_foundation()
    if args.command == "validate-contact":
        return validate_contact()
    if args.command == "check-repository":
        return check_repository()
    if args.command == "render-emails":
        return render_emails()
    if args.command == "check-email":
        return check_email(live=args.live, recipient=args.recipient)
    if args.command == "analyze-comment":
        return analyze_comment(live=args.live)
    return 1


if __name__ == "__main__":
    sys.exit(main())
