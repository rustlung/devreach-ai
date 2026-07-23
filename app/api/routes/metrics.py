import logging
import time

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.exception_handlers import error_payload
from app.core.logging import get_request_id
from app.api.dependencies import get_contact_repository
from app.repositories.contact_repository import ContactRepository, ContactRepositoryError
from app.schemas.metrics import ContactMetricsResponse
from app.services.diagnostics import build_metrics_response


router = APIRouter(prefix="/api", tags=["metrics"])
logger = logging.getLogger(__name__)


@router.get(
    "/metrics",
    response_model=ContactMetricsResponse,
    summary="Получить обезличенные агрегаты обращений",
    description="Возвращает только агрегированную статистику без персональных данных и без внешних запросов.",
    responses={
        200: {"description": "Метрики успешно собраны"},
        503: {"description": "База данных недоступна"},
    },
)
def get_metrics(repository: ContactRepository = Depends(get_contact_repository)) -> ContactMetricsResponse | JSONResponse:
    start_time = time.perf_counter()
    request_id = get_request_id()
    logger.info("event=metrics_collection_started request_id=%s", request_id)

    try:
        repository_metrics = repository.get_metrics()
        response = build_metrics_response(repository_metrics, request_id=request_id)
    except ContactRepositoryError as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.exception(
            "event=metrics_collection_failed request_id=%s stage=database_aggregation error_type=%s duration_ms=%s",
            request_id,
            type(exc).__name__,
            duration_ms,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_payload(
                code="database_unavailable",
                message="Диагностические метрики временно недоступны",
                details=[],
            ),
        )

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "event=metrics_collection_completed request_id=%s total_contacts=%s duration_ms=%s",
        request_id,
        response.total_contacts,
        duration_ms,
    )
    return response
