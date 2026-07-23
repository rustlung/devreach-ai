import logging

from fastapi.testclient import TestClient

from app.core.logging import RequestContextFilter
from tests.conftest import readable_test_id


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@readable_test_id("ответ содержит request id")
def test_http_response_contains_request_id(client: TestClient, _case_id) -> None:
    """LOGGING-001: HTTP-запрос получает request ID в заголовке ответа."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


@readable_test_id("завершение запроса записывается в логи")
def test_request_completion_is_written_to_logs(client: TestClient, _case_id) -> None:
    """LOGGING-002: завершение HTTP-запроса фиксируется в логах с request ID."""
    logger = logging.getLogger("app.http")
    handler = ListHandler()
    handler.addFilter(RequestContextFilter())
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    request_id = "test-request-id-001"

    try:
        response = client.get("/api/health", headers={"X-Request-ID": request_id})
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    messages = [record.getMessage() for record in handler.records]
    assert "Завершение обработки HTTP-запроса" in messages
    assert any(getattr(record, "request_id", None) == request_id for record in handler.records)
