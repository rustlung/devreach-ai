import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.health import DatabaseHealth, HealthResponse
from app.services.diagnostics import build_health_response, build_unavailable_health_response, measure_database_health

router = APIRouter(prefix="/api", tags=["health"])
logger = logging.getLogger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверить состояние приложения",
    description="Проверяет доступность БД и локальную готовность конфигурации AI/email без внешних запросов.",
    responses={
        200: {"description": "Приложение доступно: ok или degraded"},
        503: {"description": "База данных недоступна"},
    },
)
def get_health(request: Request) -> HealthResponse | JSONResponse:
    settings = request.app.state.settings
    try:
        database = measure_database_health(settings)
    except SQLAlchemyError:
        payload = build_unavailable_health_response(
            settings,
            DatabaseHealth(status="unavailable", latency_ms=None),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(mode="json"),
        )

    return build_health_response(settings, database)
