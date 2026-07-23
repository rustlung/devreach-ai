from fastapi import APIRouter
from fastapi.testclient import TestClient

from tests.conftest import readable_test_id


@readable_test_id("необработанная ошибка возвращает безопасный ответ")
def test_unhandled_exception_returns_safe_error(app, _case_id) -> None:
    """ERROR-001: необработанная ошибка возвращает единый безопасный ответ."""
    router = APIRouter()

    @router.get("/test/unhandled-error")
    def raise_unhandled_error() -> None:
        raise RuntimeError("internal secret detail")

    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test/unhandled-error", headers={"X-Request-ID": "error-request-id"})

    payload = response.json()
    assert response.status_code == 500
    assert payload == {
        "error": {
            "code": "internal_server_error",
            "message": "Внутренняя ошибка сервера",
            "details": [],
        },
        "request_id": "error-request-id",
    }
    assert "internal secret detail" not in str(payload)
