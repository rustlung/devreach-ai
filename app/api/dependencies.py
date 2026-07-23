import logging

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.exception_handlers import RateLimitExceededError
from app.core.client_ip import build_client_key, resolve_client_ip
from app.core.logging import get_request_id
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.db.session import get_db
from app.repositories.contact_repository import ContactRepository
from app.services.ai_service import OpenAIAnalysisService
from app.services.contact_service import ContactService
from app.services.email_service import ResendEmailService


logger = logging.getLogger(__name__)


def get_contact_rate_limiter(request: Request) -> SlidingWindowRateLimiter:
    return request.app.state.contact_rate_limiter


def enforce_contact_rate_limit(
    request: Request,
    limiter: SlidingWindowRateLimiter = Depends(get_contact_rate_limiter),
) -> None:
    settings = request.app.state.settings
    client_ip = resolve_client_ip(request, settings)
    client_key = build_client_key(client_ip)

    try:
        decision = limiter.check(client_key)
    except Exception as exc:
        logger.exception(
            "event=contact_rate_limit_failed stage=limiter_check error_type=%s request_id=%s contact_pipeline_called=false",
            type(exc).__name__,
            get_request_id(),
        )
        raise

    if decision.allowed:
        logger.debug(
            "event=contact_rate_limit_allowed request_id=%s client_key=%s remaining=%s window_seconds=%s",
            get_request_id(),
            client_key,
            decision.remaining,
            decision.window_seconds,
        )
        return

    logger.warning(
        "event=contact_rate_limit_exceeded request_id=%s client_key=%s limit=%s window_seconds=%s "
        "retry_after_seconds=%s contact_pipeline_called=false",
        get_request_id(),
        client_key,
        decision.limit,
        decision.window_seconds,
        decision.retry_after_seconds,
    )
    raise RateLimitExceededError(retry_after_seconds=decision.retry_after_seconds)


def get_contact_service(request: Request, db: Session = Depends(get_db)) -> ContactService:
    settings = request.app.state.settings
    repository = ContactRepository(db)
    # Production-клиенты создаются как зависимости, но реальные OpenAI/Resend
    # запросы остаются ленивыми и возможны только внутри соответствующих сервисов.
    ai_service = OpenAIAnalysisService(settings=settings)
    email_service = ResendEmailService(settings=settings)
    return ContactService(repository=repository, ai_service=ai_service, email_service=email_service)
