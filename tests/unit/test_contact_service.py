from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.repositories.contact_repository import ContactRepository, ContactRepositoryError
from app.schemas.contact import ContactRequestCreate
from app.schemas.contact_storage import AiStatus, EmailStatus, ProcessingStatus
from app.schemas.email import EmailSendResult, EmailTemplateContext, EmailType
from app.services import contact_service as contact_service_module
from app.services.ai_service import FakeAIAnalysisService
from app.services.contact_service import ContactProcessingError, ContactService
from app.services.email_service import FakeEmailService
from tests.conftest import readable_test_id


TEST_REQUEST_ID = "test-request-id"


@pytest.fixture
def repository_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'contact-service.sqlite3'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
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


def make_contact_data(**overrides) -> ContactRequestCreate:
    data = {
        "name": "   Иван    Иванов   ",
        "phone": "8 (999) 123-45-67",
        "email": "  User@Example.COM  ",
        "comment": "Здравствуйте, хочу обсудить backend-сервис.",
    }
    data.update(overrides)
    return ContactRequestCreate(**data)


class RecordingEmailService(FakeEmailService):
    def __init__(self, owner_mode: str = "success") -> None:
        super().__init__(owner_mode=owner_mode)
        self.owner_contexts: list[EmailTemplateContext] = []

    def send_owner_notification(self, context: EmailTemplateContext) -> EmailSendResult:
        self.owner_contexts.append(context)
        return super().send_owner_notification(context)


class RaisingAIService:
    def __init__(self) -> None:
        self.called = False

    def analyze_comment(self, comment: str):
        self.called = True
        raise RuntimeError("test ai error")


class TrackingAIService(FakeAIAnalysisService):
    def __init__(self, mode: str = "success") -> None:
        super().__init__(mode=mode)
        self.called = False

    def analyze_comment(self, comment: str):
        self.called = True
        return super().analyze_comment(comment)


class CreateFailingRepository:
    def create(self, contact_data):
        raise ContactRepositoryError("create failed")


@readable_test_id("полный успех contact service завершает pipeline")
def test_contact_service_processes_full_success(repository: ContactRepository, monkeypatch, _case_id) -> None:
    """PIPELINE-SUCCESS-001: успешный pipeline сохраняет обращение, AI и owner email status."""
    logger_spy = Mock()
    monkeypatch.setattr(contact_service_module, "logger", logger_spy)
    email_service = RecordingEmailService()
    service = ContactService(repository, TrackingAIService(), email_service)

    response = service.process_contact(make_contact_data(), TEST_REQUEST_ID)
    contact = repository.get_by_id(response.id)

    assert contact is not None
    assert contact.name == "Иван Иванов"
    assert contact.phone == "+79991234567"
    assert contact.ai_status == AiStatus.SUCCESS.value
    assert contact.owner_email_status == EmailStatus.SENT.value
    assert contact.processing_status == ProcessingStatus.COMPLETED.value
    assert response.status == ProcessingStatus.COMPLETED
    assert response.ai_processed is True
    assert response.owner_email_status == EmailStatus.SENT
    assert response.request_id == TEST_REQUEST_ID
    assert len(email_service.sent_messages) == 1
    assert email_service.sent_messages[0]["email_type"] == EmailType.OWNER_NOTIFICATION
    assert email_service.owner_contexts[0].email == contact.email

    log_text = " ".join(str(arg) for call in logger_spy.info.call_args_list for arg in call.args)
    assert "Иван Иванов" not in log_text
    assert "user@example.com" not in log_text
    assert "backend-сервис" not in log_text


@readable_test_id("ai fallback сохраняется и pipeline продолжается")
def test_contact_service_continues_after_ai_fallback(repository: ContactRepository, _case_id) -> None:
    """PIPELINE-AI-FALLBACK-001: AI fallback сохраняется и письмо владельцу всё равно отправляется."""
    email_service = RecordingEmailService()
    service = ContactService(repository, TrackingAIService(mode="fallback"), email_service)

    response = service.process_contact(make_contact_data(), TEST_REQUEST_ID)
    contact = repository.get_by_id(response.id)

    assert contact is not None
    assert contact.ai_status == AiStatus.FALLBACK.value
    assert contact.ai_error == "fake_fallback"
    assert len(email_service.sent_messages) == 1
    assert email_service.owner_contexts[0].ai_status == AiStatus.FALLBACK
    assert response.status == ProcessingStatus.COMPLETED_WITH_ERRORS
    assert response.ai_processed is False


@readable_test_id("ai exception превращается в fallback")
def test_contact_service_converts_ai_exception_to_fallback(repository: ContactRepository, _case_id) -> None:
    """PIPELINE-AI-EXCEPTION-001: исключение AI-сервиса не останавливает pipeline."""
    email_service = RecordingEmailService()
    service = ContactService(repository, RaisingAIService(), email_service)

    response = service.process_contact(make_contact_data(), TEST_REQUEST_ID)
    contact = repository.get_by_id(response.id)

    assert contact is not None
    assert contact.ai_status == AiStatus.FALLBACK.value
    assert contact.ai_error == "ai_service_exception"
    assert response.status == ProcessingStatus.COMPLETED_WITH_ERRORS
    assert len(email_service.sent_messages) == 1


@readable_test_id("ошибка письма владельцу даёт частичный успех")
def test_owner_email_failure_results_in_completed_with_errors(repository: ContactRepository, _case_id) -> None:
    """PIPELINE-OWNER-EMAIL-FAILED-001: сбой письма владельцу даёт completed_with_errors."""
    email_service = RecordingEmailService(owner_mode="failed")
    service = ContactService(repository, TrackingAIService(), email_service)

    response = service.process_contact(make_contact_data(), TEST_REQUEST_ID)
    contact = repository.get_by_id(response.id)

    assert contact is not None
    assert contact.owner_email_status == EmailStatus.FAILED.value
    assert response.status == ProcessingStatus.COMPLETED_WITH_ERRORS
    assert response.owner_email_status == EmailStatus.FAILED
    assert len(email_service.sent_messages) == 1


@readable_test_id("pipeline отправляет только письмо владельцу")
def test_contact_service_sends_single_owner_email_without_user_autoreply(repository: ContactRepository, _case_id) -> None:
    """PIPELINE-SINGLE-EMAIL-001: pipeline не формирует автоматическое письмо пользователю."""
    email_service = RecordingEmailService()
    service = ContactService(repository, TrackingAIService(), email_service)

    response = service.process_contact(make_contact_data(), TEST_REQUEST_ID)
    contact = repository.get_by_id(response.id)

    assert contact is not None
    assert contact.owner_email_status == EmailStatus.SENT.value
    assert response.owner_email_status == EmailStatus.SENT
    assert response.status == ProcessingStatus.COMPLETED
    assert len(email_service.sent_messages) == 1
    assert email_service.sent_messages[0]["email_type"] == EmailType.OWNER_NOTIFICATION
    assert not hasattr(email_service, "send_user_confirmation")


@readable_test_id("ошибка письма владельцу сохраняет ai результат")
def test_owner_email_failure_keeps_ai_result(repository: ContactRepository, _case_id) -> None:
    """PIPELINE-EMAILS-FAILED-001: owner email failed не удаляет сохранённый AI-анализ."""
    email_service = RecordingEmailService(owner_mode="failed")
    service = ContactService(repository, TrackingAIService(), email_service)

    response = service.process_contact(make_contact_data(), TEST_REQUEST_ID)
    contact = repository.get_by_id(response.id)

    assert contact is not None
    assert contact.ai_status == AiStatus.SUCCESS.value
    assert contact.owner_email_status == EmailStatus.FAILED.value
    assert response.status == ProcessingStatus.COMPLETED_WITH_ERRORS


@readable_test_id("skipped письмо владельцу считается частичной ошибкой")
def test_skipped_owner_email_results_in_completed_with_errors(repository: ContactRepository, _case_id) -> None:
    """PIPELINE-EMAIL-SKIPPED-001: skipped owner email переводит итог в completed_with_errors."""
    email_service = RecordingEmailService(owner_mode="skipped")
    service = ContactService(repository, TrackingAIService(), email_service)

    response = service.process_contact(make_contact_data(), TEST_REQUEST_ID)

    assert response.owner_email_status == EmailStatus.SKIPPED
    assert response.status == ProcessingStatus.COMPLETED_WITH_ERRORS


@readable_test_id("repository create error останавливает внешние этапы")
def test_repository_create_error_stops_external_stages(_case_id) -> None:
    """PIPELINE-REPOSITORY-CREATE-FAILED-001: при ошибке create AI и email не вызываются."""
    ai_service = TrackingAIService()
    email_service = RecordingEmailService()
    service = ContactService(CreateFailingRepository(), ai_service, email_service)

    with pytest.raises(ContactProcessingError):
        service.process_contact(make_contact_data(), TEST_REQUEST_ID)

    assert ai_service.called is False
    assert email_service.sent_messages == []


@readable_test_id("repository ai update error считается критической")
def test_repository_ai_update_error_stops_email(repository: ContactRepository, monkeypatch, _case_id) -> None:
    """PIPELINE-REPOSITORY-UPDATE-FAILED-001: если AI-результат нельзя сохранить, email не отправляется."""
    email_service = RecordingEmailService()
    service = ContactService(repository, TrackingAIService(), email_service)
    monkeypatch.setattr(repository, "update_ai_result", Mock(side_effect=ContactRepositoryError("ai update failed")))

    with pytest.raises(ContactProcessingError):
        service.process_contact(make_contact_data(), TEST_REQUEST_ID)

    assert email_service.sent_messages == []


@readable_test_id("repository email status update error считается критической")
def test_repository_email_status_update_error_is_critical(repository: ContactRepository, monkeypatch, _case_id) -> None:
    """PIPELINE-REPOSITORY-EMAIL-UPDATE-FAILED-001: отправка могла состояться, но несохранённый статус критичен."""
    email_service = RecordingEmailService()
    service = ContactService(repository, TrackingAIService(), email_service)
    monkeypatch.setattr(
        repository,
        "update_owner_email_status",
        Mock(side_effect=ContactRepositoryError("owner email update failed")),
    )

    with pytest.raises(ContactProcessingError):
        service.process_contact(make_contact_data(), TEST_REQUEST_ID)

    assert len(email_service.sent_messages) == 1


@readable_test_id("processing failed только при критической ошибке")
def test_processing_failed_is_not_used_for_external_errors(repository: ContactRepository, _case_id) -> None:
    """PIPELINE-STATUS-001: external errors дают completed_with_errors, а не failed."""
    service = ContactService(
        repository,
        TrackingAIService(mode="fallback"),
        RecordingEmailService(owner_mode="failed"),
    )

    response = service.process_contact(make_contact_data(), TEST_REQUEST_ID)

    assert response.status == ProcessingStatus.COMPLETED_WITH_ERRORS
    assert response.status != ProcessingStatus.FAILED
