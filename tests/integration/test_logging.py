import logging

from fastapi.testclient import TestClient

from tests.conftest import readable_test_id


@readable_test_id("ответ содержит request id")
def test_http_response_contains_request_id(client: TestClient, _case_id) -> None:
    """LOGGING-001: HTTP-запрос получает request ID в заголовке ответа."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


@readable_test_id("завершение запроса записывается в логи")
def test_request_completion_is_written_to_logs(client: TestClient, caplog, _case_id) -> None:
    """LOGGING-002: завершение HTTP-запроса фиксируется в логах с request ID."""
    caplog.set_level(logging.INFO, logger="app.http")
    request_id = "test-request-id-001"

    response = client.get("/api/health", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    messages = [record.getMessage() for record in caplog.records]
    assert "Завершение обработки HTTP-запроса" in messages
    assert any(getattr(record, "request_id", None) == request_id for record in caplog.records)
