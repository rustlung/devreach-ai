from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import ContactRequestCreate
from tests.conftest import readable_test_id


def alembic_config_for(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def migrated_database_url(tmp_path, monkeypatch):
    database_path = tmp_path / "migration.sqlite3"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    try:
        yield database_url, database_path
    finally:
        get_settings.cache_clear()


@readable_test_id("alembic upgrade создает таблицу обращений")
def test_alembic_upgrade_creates_contact_requests_table(migrated_database_url, _case_id) -> None:
    """DATABASE-MIGRATION-001: Alembic upgrade создаёт таблицу обращений."""
    database_url, _database_path = migrated_database_url

    command.upgrade(alembic_config_for(database_url), "head")

    engine = create_engine(database_url, future=True)
    try:
        inspector = inspect(engine)
        assert "contact_requests" in inspector.get_table_names()
        column_names = {column["name"] for column in inspector.get_columns("contact_requests")}
        assert {"id", "name", "phone", "email", "comment", "processing_status"}.issubset(column_names)
        assert "owner_email_status" in column_names
        assert "owner_email_error" in column_names
        assert "user_email_status" not in column_names
        assert "user_email_error" not in column_names
    finally:
        engine.dispose()


@readable_test_id("модель совместима с актуальной миграцией")
def test_repository_works_with_migrated_database(migrated_database_url, _case_id) -> None:
    """DATABASE-MODEL-002: модель и репозиторий работают с БД, созданной миграцией."""
    database_url, _database_path = migrated_database_url
    command.upgrade(alembic_config_for(database_url), "head")

    engine = create_engine(database_url, connect_args={"check_same_thread": False}, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    try:
        repository = ContactRepository(session)
        contact = repository.create(
            ContactRequestCreate(
                name="Иван Иванов",
                phone="+7 999 123 45 67",
                email="user@example.com",
                comment="Здравствуйте, хочу обсудить тестовый проект.",
            )
        )
        assert repository.get_by_id(contact.id) is not None
    finally:
        session.close()
        engine.dispose()


@readable_test_id("alembic downgrade возвращает legacy user email поля")
def test_alembic_downgrade_restores_user_email_fields(migrated_database_url, _case_id) -> None:
    """DATABASE-MIGRATION-002: downgrade -1 возвращает старые user email поля."""
    database_url, database_path = migrated_database_url
    command.upgrade(alembic_config_for(database_url), "head")
    command.downgrade(alembic_config_for(database_url), "-1")

    assert Path(database_path).exists()
    engine = create_engine(database_url, future=True)
    try:
        inspector = inspect(engine)
        assert "contact_requests" in inspector.get_table_names()
        column_names = {column["name"] for column in inspector.get_columns("contact_requests")}
        assert "user_email_status" in column_names
        assert "user_email_error" in column_names
    finally:
        engine.dispose()


@readable_test_id("повторный upgrade снова удаляет legacy поля")
def test_alembic_downgrade_then_upgrade_removes_user_email_fields_again(migrated_database_url, _case_id) -> None:
    """DATABASE-REMOVE-USER-EMAIL-FIELDS-001: downgrade/upgrade корректно меняет структуру таблицы."""
    database_url, _database_path = migrated_database_url
    config = alembic_config_for(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, "-1")
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    try:
        column_names = {column["name"] for column in inspect(engine).get_columns("contact_requests")}
        assert "owner_email_status" in column_names
        assert "user_email_status" not in column_names
        assert "user_email_error" not in column_names
    finally:
        engine.dispose()
