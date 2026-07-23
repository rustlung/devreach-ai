import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import check_database_connection
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse | JSONResponse:
    settings = request.app.state.settings
    try:
        check_database_connection(settings)
    except SQLAlchemyError:
        logger.exception("Health check обнаружил недоступность базы данных")
        payload = HealthResponse(
            status="error",
            service=settings.app_name,
            version=request.app.version,
            database="unavailable",
            message="База данных временно недоступна",
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=request.app.version,
        database="available",
    )
