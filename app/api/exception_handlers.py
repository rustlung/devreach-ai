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


def _make_json_safe(value):
    if isinstance(value, dict):
        return {key: _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Pydantic может положить исходный ValueError в ctx.error. Перед JSONResponse
    # приводим такие объекты к строке, чтобы обработчик 422 сам не превращался в 500.
    safe_errors = _make_json_safe(exc.errors())
    logger.warning(
        "Ошибка валидации входящего HTTP-запроса: method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        safe_errors,
    )
    return JSONResponse(
        status_code=422,
        content=error_payload(
            code="validation_error",
            message="Переданные данные не прошли проверку",
            details=safe_errors,
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
