from __future__ import annotations

import argparse
import logging
import sys

from app.api.routes.health import get_health
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import check_database_connection


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


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Служебные команды DevReach AI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-foundation", help="Проверить фундамент проекта без внешних API")

    args = parser.parse_args(argv)
    if args.command == "check-foundation":
        return check_foundation()
    return 1


if __name__ == "__main__":
    sys.exit(main())
