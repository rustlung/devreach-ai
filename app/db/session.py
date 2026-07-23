from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def create_database_engine(settings: Settings | None = None) -> Engine:
    active_settings = settings or get_settings()
    connect_args = {"check_same_thread": False} if active_settings.database_url.startswith("sqlite") else {}
    return create_engine(active_settings.database_url, connect_args=connect_args, future=True)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        logger.exception("Ошибка SQLAlchemy во время работы с сессией базы данных")
        raise
    finally:
        db.close()


def check_database_connection(settings: Settings | None = None) -> None:
    """Отдельная проверка нужна для health и CLI без создания бизнес-моделей."""
    test_engine = create_database_engine(settings)
    try:
        with test_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Не удалось выполнить техническую проверку подключения к базе данных")
        raise
    finally:
        test_engine.dispose()
