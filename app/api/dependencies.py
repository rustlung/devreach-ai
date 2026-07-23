from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.contact_repository import ContactRepository
from app.services.ai_service import OpenAIAnalysisService
from app.services.contact_service import ContactService
from app.services.email_service import ResendEmailService


def get_contact_service(request: Request, db: Session = Depends(get_db)) -> ContactService:
    settings = request.app.state.settings
    repository = ContactRepository(db)
    # Production-клиенты создаются как зависимости, но реальные OpenAI/Resend
    # запросы остаются ленивыми и возможны только внутри соответствующих сервисов.
    ai_service = OpenAIAnalysisService(settings=settings)
    email_service = ResendEmailService(settings=settings)
    return ContactService(repository=repository, ai_service=ai_service, email_service=email_service)
