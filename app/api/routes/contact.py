from fastapi import APIRouter, Depends, Request, status
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import enforce_contact_rate_limit, get_contact_service
from app.core.client_ip import build_client_key, resolve_client_ip
from app.core.logging import get_request_id
from app.schemas.contact import ContactRequestCreate, ContactResponse
from app.services.contact_service import ContactService
from app.services.demo_access import resolve_notification_recipient


router = APIRouter(prefix="/api", tags=["contact"])


@router.post(
    "/contact",
    status_code=status.HTTP_201_CREATED,
    response_model=ContactResponse,
    summary="Принять обращение с сайта",
    description="Сохраняет обращение, запускает AI-анализ и email-уведомления через основной pipeline.",
    response_description="Обращение принято и сохранено",
    dependencies=[Depends(enforce_contact_rate_limit)],
    responses={
        201: {
            "description": "Обращение принято",
            "content": {
                "application/json": {
                    "example": {
                        "id": 15,
                        "status": "completed",
                        "message": "Обращение принято",
                        "ai_processed": True,
                        "ai_status": "success",
                        "owner_email_status": "sent",
                        "request_id": "example-request-id",
                    }
                }
            },
        },
        422: {"description": "Переданные данные не прошли проверку"},
        403: {"description": "Демонстрационный режим недоступен"},
        429: {"description": "Превышен лимит обращений"},
        500: {"description": "Внутренняя ошибка сервера"},
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "name": "Иван Иванов",
                        "phone": "+7 (999) 123-45-67",
                        "email": "ivan@example.com",
                        "comment": "Хотел бы обсудить разработку backend-сервиса.",
                    }
                }
            }
        }
    },
)
async def create_contact(
    request: Request,
    contact_data: ContactRequestCreate,
    contact_service: ContactService = Depends(get_contact_service),
) -> ContactResponse:
    request_id = get_request_id()
    settings = request.app.state.settings
    client_key = build_client_key(resolve_client_ip(request, settings))
    notification_recipient = resolve_notification_recipient(contact_data, settings, request_id, client_key)
    return await run_in_threadpool(contact_service.process_contact, contact_data, request_id, notification_recipient)
