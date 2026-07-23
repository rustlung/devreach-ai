import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_request_id

logger = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    def __init__(self, retry_after_seconds: int | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds


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
    safe_errors = _redact_validation_inputs(_make_json_safe(exc.errors()))
    logger.warning(
        "Ошибка валидации входящего HTTP-запроса: method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        safe_errors,
    )
    if _has_honeypot_error(safe_errors):
        logger.warning(
            "event=contact_honeypot_triggered request_id=%s contact_pipeline_called=false",
            get_request_id(),
        )
    return JSONResponse(
        status_code=422,
        content=error_payload(
            code="validation_error",
            message="Переданные данные не прошли проверку",
            details=safe_errors,
        ),
    )


def _has_honeypot_error(errors: list) -> bool:
    for error in errors:
        location = error.get("loc") if isinstance(error, dict) else None
        if location and "website" in location:
            return True
        message = error.get("msg", "") if isinstance(error, dict) else ""
        if "Служебное поле должно оставаться пустым" in message:
            return True
    return False


def _redact_validation_inputs(errors: list) -> list:
    redacted_errors = []
    for error in errors:
        if isinstance(error, dict):
            safe_error = dict(error)
            safe_error.pop("input", None)
            if isinstance(safe_error.get("msg"), str):
                safe_error["msg"] = _clean_validation_message(safe_error["msg"])
            redacted_errors.append(safe_error)
        else:
            redacted_errors.append(error)
    return redacted_errors


def _clean_validation_message(message: str) -> str:
    # Pydantic добавляет технический префикс к ValueError. Для клиента оставляем
    # только понятную русскую причину, заданную в валидаторе.
    for prefix in ("Value error, ", "ValueError, "):
        if message.startswith(prefix):
            return message.removeprefix(prefix)
    return message


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


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceededError) -> JSONResponse:
    headers = {}
    if exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(
        status_code=429,
        content=error_payload(
            code="rate_limit_exceeded",
            message="Слишком много обращений. Попробуйте повторить позже.",
            details=[],
        ),
        headers=headers,
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
