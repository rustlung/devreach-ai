from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings


request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
request_method_context: ContextVar[str] = ContextVar("request_method", default="-")
request_path_context: ContextVar[str] = ContextVar("request_path", default="-")
response_status_context: ContextVar[str] = ContextVar("response_status", default="-")
request_duration_ms_context: ContextVar[str] = ContextVar("request_duration_ms", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        record.request_method = request_method_context.get()
        record.request_path = request_path_context.get()
        record.status_code = response_status_context.get()
        record.duration_ms = request_duration_ms_context.get()
        return True


def configure_logging(settings: Settings) -> None:
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    # В тестах pytest ставит свой LogCaptureHandler. Его нельзя удалять при
    # повторном create_app(), иначе caplog перестаёт видеть события логирования.
    preserved_handlers = [
        handler
        for handler in root_logger.handlers
        if handler.__class__.__module__.startswith("_pytest.")
    ]
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | "
        "request_id=%(request_id)s | method=%(request_method)s | path=%(request_path)s | "
        "status=%(status_code)s | duration_ms=%(duration_ms)s | %(message)s"
    )
    context_filter = RequestContextFilter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    for handler in preserved_handlers:
        root_logger.addHandler(handler)

    http_logger = logging.getLogger("app.http")
    http_logger.disabled = False
    http_logger.propagate = True
    http_logger.setLevel(settings.log_level)


def get_request_id() -> str:
    return request_id_context.get()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token_id = request_id_context.set(request_id)
        token_method = request_method_context.set(request.method)
        token_path = request_path_context.set(request.url.path)
        token_status = response_status_context.set("-")
        token_duration = request_duration_ms_context.set("-")
        start_time = time.perf_counter()
        logger = logging.getLogger("app.http")

        logger.info("Начало обработки HTTP-запроса")
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response_status_context.set("500")
            request_duration_ms_context.set(str(duration_ms))
            logger.exception("Необработанная ошибка на этапе обработки HTTP-запроса")
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response_status_context.set(str(response.status_code))
        request_duration_ms_context.set(str(duration_ms))
        logger.info("Завершение обработки HTTP-запроса")

        request_id_context.reset(token_id)
        request_method_context.reset(token_method)
        request_path_context.reset(token_path)
        response_status_context.reset(token_status)
        request_duration_ms_context.reset(token_duration)
        return response
