from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.logging import get_request_id
from app.core.version import APP_VERSION
from app.db.session import create_database_engine
from app.schemas.contact_storage import AiStatus, ContactCategory, ContactMetrics, EmailStatus, ProcessingStatus
from app.schemas.health import DatabaseHealth, DependencyHealth, HealthResponse
from app.schemas.metrics import ContactMetricsResponse, EmailMetrics


logger = logging.getLogger(__name__)
UNKNOWN_METRIC_KEY = "unknown"


def measure_database_health(settings: Settings) -> DatabaseHealth:
    start_time = time.perf_counter()
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.exception(
            "event=health_check_failed stage=database error_type=%s request_id=%s duration_ms=%s",
            type(exc).__name__,
            get_request_id(),
            latency_ms,
        )
        raise
    finally:
        engine.dispose()

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return DatabaseHealth(status="available", latency_ms=latency_ms)


def build_dependency_health(settings: Settings) -> DependencyHealth:
    ai_status = _integration_status(
        enabled=settings.ai_live_requests_enabled,
        required_values=[
            settings.openai_api_key,
            settings.openai_base_url,
            settings.openai_model,
        ],
    )
    email_status = _integration_status(
        enabled=settings.email_live_requests_enabled,
        required_values=[
            settings.resend_api_key,
            settings.email_from_address,
            settings.owner_email,
        ],
    )
    return DependencyHealth(ai=ai_status, email=email_status)


def build_health_response(settings: Settings, database: DatabaseHealth) -> HealthResponse:
    dependencies = build_dependency_health(settings)
    health_status = "ok" if dependencies.ai == "configured" and dependencies.email == "configured" else "degraded"

    if health_status == "degraded":
        logger.warning(
            "event=health_check_degraded request_id=%s ai_status=%s email_status=%s",
            get_request_id(),
            dependencies.ai,
            dependencies.email,
        )
    else:
        logger.debug(
            "event=health_check_completed status=ok database_status=%s database_latency_ms=%s request_id=%s",
            database.status,
            database.latency_ms,
            get_request_id(),
        )

    return HealthResponse(
        status=health_status,
        service=settings.app_name,
        version=APP_VERSION,
        environment=settings.app_env,
        database=database,
        dependencies=dependencies,
        timestamp=datetime.now(timezone.utc),
        request_id=get_request_id(),
    )


def build_unavailable_health_response(settings: Settings, database: DatabaseHealth) -> HealthResponse:
    return HealthResponse(
        status="unavailable",
        service=settings.app_name,
        version=APP_VERSION,
        environment=settings.app_env,
        database=database,
        dependencies=build_dependency_health(settings),
        timestamp=datetime.now(timezone.utc),
        request_id=get_request_id(),
        message="База данных временно недоступна",
    )


def build_metrics_response(metrics: ContactMetrics, request_id: str | None = None) -> ContactMetricsResponse:
    return ContactMetricsResponse(
        total_contacts=metrics.total_contacts,
        processing=_normalize_metric_map(metrics.by_processing_status, [status.value for status in ProcessingStatus]),
        ai=_normalize_metric_map(metrics.by_ai_status, [status.value for status in AiStatus]),
        emails=EmailMetrics(
            owner=_normalize_metric_map(metrics.owner_email, [status.value for status in EmailStatus]),
            user=_normalize_metric_map(metrics.user_email, [status.value for status in EmailStatus]),
        ),
        categories=_normalize_metric_map(
            metrics.by_category,
            [category.value for category in ContactCategory],
            include_unknown=True,
        ),
        generated_at=datetime.now(timezone.utc),
        request_id=request_id or get_request_id(),
    )


def _integration_status(enabled: bool, required_values: list[str | None]) -> str:
    if not enabled:
        return "disabled"
    if all(required_values):
        return "configured"
    return "not_configured"


def _normalize_metric_map(
    raw_values: dict[str, int],
    known_keys: list[str],
    include_unknown: bool = True,
) -> dict[str, int]:
    normalized = {key: 0 for key in known_keys}
    if include_unknown:
        normalized[UNKNOWN_METRIC_KEY] = 0

    for key, count in raw_values.items():
        normalized_key = key if key in normalized else UNKNOWN_METRIC_KEY
        if normalized_key == UNKNOWN_METRIC_KEY and key not in {UNKNOWN_METRIC_KEY, "None", "none", ""}:
            logger.warning(
                "event=metrics_unknown_value_detected request_id=%s metric_key=%s",
                get_request_id(),
                key,
            )
        normalized[normalized_key] = normalized.get(normalized_key, 0) + count

    return normalized
