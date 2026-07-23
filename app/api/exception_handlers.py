import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_request_id

logger = logging.getLogger(__name__)


def error_payload(code: str, message: str, details: list | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        },
        "request_id": get_request_id(),
    }


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "Ошибка валидации входящего HTTP-запроса: method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content=error_payload(
            code="validation_error",
            message="Переданные данные не прошли проверку",
            details=exc.errors(),
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(
        "Ожидаемая HTTP-ошибка: method=%s path=%s status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code="http_error",
            message=str(exc.detail),
        ),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Необработанная ошибка на этапе формирования ответа API: type=%s message=%s",
        type(exc).__name__,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content=error_payload(
            code="internal_server_error",
            message="Внутренняя ошибка сервера",
        ),
    )
