import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.logging import get_request_id
from app.core.version import APP_VERSION


logger = logging.getLogger(__name__)
router = APIRouter(tags=["pages"])

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "web"
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request) -> HTMLResponse:
    request_id = get_request_id()
    settings = request.app.state.settings
    try:
        response = templates.TemplateResponse(
            request,
            "index.html",
            {
                "app_name": settings.app_name,
                "app_version": APP_VERSION,
            },
        )
        logger.debug("event=landing_page_rendered request_id=%s template=index.html", request_id)
        return response
    except Exception as exc:
        logger.exception(
            "event=landing_page_render_failed request_id=%s template=index.html error_type=%s",
            request_id,
            type(exc).__name__,
        )
        raise
