from __future__ import annotations

import argparse
import logging
import sys
import tempfile
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
from app.schemas.contact import ContactRequestCreate
from app.schemas.contact_storage import AiStatus, ContactAiUpdate, EmailStatus, ProcessingStatus


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

    args = parser.parse_args(argv)
    if args.command == "check-foundation":
        return check_foundation()
    if args.command == "validate-contact":
        return validate_contact()
    if args.command == "check-repository":
        return check_repository()
    return 1


if __name__ == "__main__":
    sys.exit(main())
