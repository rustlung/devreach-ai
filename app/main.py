from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_handlers import (
    RateLimitExceededError,
    http_exception_handler,
    rate_limit_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.routes.contact import router as contact_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.core.config import Settings, get_settings
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.core.version import APP_VERSION


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings)

    app = FastAPI(
        title=active_settings.app_name,
        version=APP_VERSION,
        debug=active_settings.debug,
    )
    app.state.settings = active_settings
    app.state.contact_rate_limiter = SlidingWindowRateLimiter(
        limit=active_settings.contact_rate_limit_requests,
        window_seconds=active_settings.contact_rate_limit_window_seconds,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RateLimitExceededError, rate_limit_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health_router)
    app.include_router(contact_router)
    app.include_router(metrics_router)
    return app


app = create_app()
