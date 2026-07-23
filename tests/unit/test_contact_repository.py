from datetime import timezone
from time import sleep

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import ContactRequest
from app.repositories.contact_repository import (
    ContactNotFoundError,
    ContactRepository,
    ContactRepositoryError,
)
from app.schemas.contact import ContactRequestCreate
from app.schemas.contact_storage import (
    AiStatus,
    ContactAiUpdate,
    ContactEmailStatusUpdate,
    EmailStatus,
    ProcessingStatus,
)
from tests.conftest import readable_test_id


@pytest.fixture
def repository_session(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'repository.sqlite3'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def repository(repository_session: Session) -> ContactRepository:
    return ContactRepository(repository_session)


def make_contact_request(**overrides) -> ContactRequestCreate:
    data = {
        "name": "   Иван    Иванов   ",
        "phone": "8 (999) 123-45-67",
        "email": "  User@Example.COM  ",
        "comment": "Здравствуйте, хочу обсудить тестовый проект.",
    }
    data.update(overrides)
    return ContactRequestCreate(**data)


def create_contact(repository: ContactRepository) -> ContactRequest:
    return repository.create(make_contact_request())


@readable_test_id("валидное обращение создается и получает id")
def test_create_contact_persists_valid_request(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-CREATE-001: валидное обращение сохраняется и получает ID."""
    contact = create_contact(repository)

    assert contact.id == 1
    assert contact.name == "Иван Иванов"
    assert contact.phone == "+79991234567"
    assert contact.email == "user@example.com"


@readable_test_id("при создании выставляются начальные статусы")
def test_create_contact_sets_initial_statuses(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-CREATE-002: при создании выставляются начальные статусы pipeline."""
    contact = create_contact(repository)

    assert contact.processing_status == ProcessingStatus.RECEIVED.value
    assert contact.ai_status == AiStatus.PENDING.value
    assert contact.owner_email_status == EmailStatus.PENDING.value
    assert contact.sentiment is None
    assert contact.ai_error is None


@readable_test_id("при создании устанавливаются utc временные метки")
def test_create_contact_sets_utc_timestamps(repository: ContactRepository, _case_id) -> None:
    """DATABASE-MODEL-001: created_at и updated_at устанавливаются в UTC."""
    contact = create_contact(repository)

    assert contact.created_at.tzinfo == timezone.utc
    assert contact.updated_at.tzinfo == timezone.utc
    assert contact.updated_at >= contact.created_at


@readable_test_id("updated at меняется при обновлении записи")
def test_updated_at_changes_after_update(repository: ContactRepository, _case_id) -> None:
    """DATABASE-MODEL-003: updated_at меняется после обновления обращения."""
    contact = create_contact(repository)
    original_updated_at = contact.updated_at

    sleep(0.001)
    updated_contact = repository.update_processing_status(contact.id, ProcessingStatus.PROCESSING)

    assert updated_contact.updated_at > original_updated_at


@readable_test_id("существующее обращение возвращается по id")
def test_get_by_id_returns_existing_contact(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-GET-001: существующее обращение возвращается по ID."""
    created_contact = create_contact(repository)

    found_contact = repository.get_by_id(created_contact.id)

    assert found_contact is not None
    assert found_contact.id == created_contact.id


@readable_test_id("несуществующее обращение возвращает none")
def test_get_by_id_returns_none_for_missing_contact(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-GET-002: отсутствие записи не считается системной ошибкой."""
    assert repository.get_by_id(999) is None


@readable_test_id("ai поля сохраняются при обновлении результата")
def test_update_ai_result_saves_all_ai_fields(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-AI-UPDATE-001: все AI-поля сохраняются при обновлении результата."""
    contact = create_contact(repository)

    updated_contact = repository.update_ai_result(
        contact.id,
        ContactAiUpdate(
            sentiment="positive",
            category="web_development",
            priority="high",
            ai_summary="Краткое тестовое резюме",
            suggested_reply="Тестовый ответ",
            ai_status=AiStatus.SUCCESS,
        ),
    )

    assert updated_contact.sentiment == "positive"
    assert updated_contact.category == "web_development"
    assert updated_contact.priority == "high"
    assert updated_contact.ai_summary == "Краткое тестовое резюме"
    assert updated_contact.suggested_reply == "Тестовый ответ"
    assert updated_contact.ai_status == AiStatus.SUCCESS.value


@readable_test_id("ai error можно сохранить отдельно")
def test_update_ai_result_can_save_error(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-AI-UPDATE-002: AI error сохраняется при ошибочном статусе."""
    contact = create_contact(repository)

    updated_contact = repository.update_ai_result(
        contact.id,
        ContactAiUpdate(ai_status=AiStatus.FAILED, ai_error="Тестовая ошибка AI"),
    )

    assert updated_contact.ai_status == AiStatus.FAILED.value
    assert updated_contact.ai_error == "Тестовая ошибка AI"


@readable_test_id("ai обновление не меняет исходные поля обращения")
def test_update_ai_result_does_not_change_original_fields(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-AI-UPDATE-003: AI-обновление не изменяет исходные данные обращения."""
    contact = create_contact(repository)

    updated_contact = repository.update_ai_result(
        contact.id,
        ContactAiUpdate(ai_status=AiStatus.SUCCESS, category="consulting"),
    )

    assert updated_contact.name == contact.name
    assert updated_contact.phone == contact.phone
    assert updated_contact.email == contact.email
    assert updated_contact.comment == contact.comment


@readable_test_id("ai обновление несуществующего id предсказуемо отклоняется")
def test_update_ai_result_rejects_missing_contact(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-AI-UPDATE-004: обновление AI для отсутствующей записи вызывает ContactNotFoundError."""
    with pytest.raises(ContactNotFoundError):
        repository.update_ai_result(999, ContactAiUpdate(ai_status=AiStatus.SUCCESS))


@readable_test_id("статус письма владельцу обновляется отдельно")
def test_update_owner_email_status_updates_only_owner(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-EMAIL-UPDATE-001: статус единственного письма владельцу обновляется отдельно."""
    contact = create_contact(repository)

    updated_contact = repository.update_owner_email_status(contact.id, EmailStatus.FAILED, "Тестовая ошибка письма")

    assert updated_contact.owner_email_status == EmailStatus.FAILED.value
    assert updated_contact.owner_email_error == "Тестовая ошибка письма"
    assert not hasattr(updated_contact, "user_email_status")
    assert not hasattr(updated_contact, "user_email_error")


@readable_test_id("общий update email статуса обновляет только owner")
def test_update_email_statuses_updates_owner_only(repository: ContactRepository, _case_id) -> None:
    """EMAIL-OWNER-ONLY-001: общий метод email-статуса больше не содержит user autoreply."""
    contact = create_contact(repository)

    updated_contact = repository.update_email_statuses(
        contact.id,
        ContactEmailStatusUpdate(
            owner_email_status=EmailStatus.SENT,
        ),
    )

    assert updated_contact.owner_email_status == EmailStatus.SENT.value
    assert not hasattr(updated_contact, "user_email_status")


@readable_test_id("общий статус обработки обновляется отдельно")
def test_update_processing_status_changes_only_processing_status(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-STATUS-001: общий статус обновляется без изменения остальных данных."""
    contact = create_contact(repository)

    updated_contact = repository.update_processing_status(contact.id, ProcessingStatus.COMPLETED)

    assert updated_contact.processing_status == ProcessingStatus.COMPLETED.value
    assert updated_contact.name == contact.name
    assert updated_contact.ai_status == AiStatus.PENDING.value


@readable_test_id("пустая база возвращает нулевые метрики")
def test_get_metrics_returns_zero_values_for_empty_database(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-METRICS-001: пустая база возвращает нулевые агрегаты."""
    metrics = repository.get_metrics()

    assert metrics.total_contacts == 0
    assert metrics.by_processing_status == {}
    assert metrics.by_ai_status == {}
    assert metrics.owner_email == {}
    assert metrics.by_category == {}


@readable_test_id("несколько записей корректно агрегируются в метриках")
def test_get_metrics_aggregates_multiple_contacts(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-METRICS-002: несколько записей корректно агрегируются."""
    first = create_contact(repository)
    second = repository.create(make_contact_request(email="second@example.com"))
    repository.update_ai_result(
        first.id,
        ContactAiUpdate(ai_status=AiStatus.SUCCESS, category="web"),
    )
    repository.update_ai_result(
        second.id,
        ContactAiUpdate(ai_status=AiStatus.FAILED, category="consulting"),
    )
    repository.update_owner_email_status(first.id, EmailStatus.SENT)
    repository.update_owner_email_status(second.id, EmailStatus.FAILED, "Тестовая ошибка письма")
    repository.update_processing_status(second.id, ProcessingStatus.COMPLETED_WITH_ERRORS)

    metrics = repository.get_metrics()

    assert metrics.total_contacts == 2
    assert metrics.by_processing_status[ProcessingStatus.RECEIVED.value] == 1
    assert metrics.by_processing_status[ProcessingStatus.COMPLETED_WITH_ERRORS.value] == 1
    assert metrics.by_ai_status[AiStatus.SUCCESS.value] == 1
    assert metrics.by_ai_status[AiStatus.FAILED.value] == 1
    assert metrics.owner_email[EmailStatus.SENT.value] == 1
    assert metrics.owner_email[EmailStatus.FAILED.value] == 1
    assert metrics.by_category == {"consulting": 1, "web": 1}


@readable_test_id("метрики не содержат персональные данные")
def test_get_metrics_does_not_return_personal_data(repository: ContactRepository, _case_id) -> None:
    """REPOSITORY-METRICS-003: метрики не возвращают персональные данные обращения."""
    create_contact(repository)

    metrics_text = str(repository.get_metrics().model_dump())

    assert "Иван" not in metrics_text
    assert "user@example.com" not in metrics_text
    assert "+79991234567" not in metrics_text
    assert "Здравствуйте" not in metrics_text


@readable_test_id("ошибка сохранения выполняет rollback и сессия остается рабочей")
def test_create_rolls_back_after_database_error(repository_session: Session, monkeypatch, _case_id) -> None:
    """REPOSITORY-ROLLBACK-001: при ошибке commit выполняется rollback, сессия остаётся пригодной."""
    repository = ContactRepository(repository_session)
    rollback_called = False

    def broken_commit() -> None:
        raise SQLAlchemyError("controlled test error")

    original_rollback = repository_session.rollback

    def tracked_rollback() -> None:
        nonlocal rollback_called
        rollback_called = True
        original_rollback()

    monkeypatch.setattr(repository_session, "commit", broken_commit)
    monkeypatch.setattr(repository_session, "rollback", tracked_rollback)

    with pytest.raises(ContactRepositoryError):
        repository.create(make_contact_request())

    assert rollback_called is True

    monkeypatch.undo()
    recovered_contact = repository.create(make_contact_request())
    assert recovered_contact.id == 1
