from types import SimpleNamespace

from app.core.client_ip import UNKNOWN_CLIENT_IP, build_client_key, resolve_client_ip
from app.core.config import Settings
from tests.conftest import readable_test_id


def make_settings(**overrides) -> Settings:
    data = {"APP_ENV": "test", "TRUST_PROXY_HEADERS": True}
    data.update(overrides)
    return Settings(**data)


def make_request(headers: dict | None = None, host: str | None = "127.0.0.1"):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=host) if host is not None else None,
    )


@readable_test_id("адрес клиента берется из request client host")
def test_client_ip_uses_request_client_host(_case_id) -> None:
    """RATE-LIMIT-IP-DIRECT-001: без proxy header используется request.client.host."""
    request = make_request(host="203.0.113.10")

    client_ip = resolve_client_ip(request, make_settings(TRUST_PROXY_HEADERS=False))

    assert client_ip == "203.0.113.10"


@readable_test_id("trusted x forwarded for имеет приоритет")
def test_client_ip_uses_x_forwarded_for_when_trusted(_case_id) -> None:
    """RATE-LIMIT-IP-PROXY-001: при доверии proxy headers используется X-Forwarded-For."""
    request = make_request(headers={"X-Forwarded-For": "198.51.100.7"}, host="10.0.0.1")

    client_ip = resolve_client_ip(request, make_settings(TRUST_PROXY_HEADERS=True))

    assert client_ip == "198.51.100.7"


@readable_test_id("из цепочки x forwarded for берется первый валидный адрес")
def test_client_ip_uses_first_valid_forwarded_address(_case_id) -> None:
    """RATE-LIMIT-IP-PROXY-002: из X-Forwarded-For берётся первый валидный IP."""
    request = make_request(headers={"X-Forwarded-For": "bad, 198.51.100.8, 10.0.0.1"})

    client_ip = resolve_client_ip(request, make_settings(TRUST_PROXY_HEADERS=True))

    assert client_ip == "198.51.100.8"


@readable_test_id("x forwarded for игнорируется без доверия proxy")
def test_client_ip_ignores_forwarded_header_when_untrusted(_case_id) -> None:
    """RATE-LIMIT-IP-UNTRUSTED-001: без доверия proxy header не влияет на client IP."""
    request = make_request(headers={"X-Forwarded-For": "198.51.100.7"}, host="203.0.113.10")

    client_ip = resolve_client_ip(request, make_settings(TRUST_PROXY_HEADERS=False))

    assert client_ip == "203.0.113.10"


@readable_test_id("некорректный proxy header приводит к fallback host")
def test_invalid_forwarded_header_falls_back_to_request_client(_case_id) -> None:
    """RATE-LIMIT-IP-FALLBACK-001: некорректный X-Forwarded-For не используется."""
    request = make_request(headers={"X-Forwarded-For": "not-an-ip"}, host="203.0.113.11")

    client_ip = resolve_client_ip(request, make_settings(TRUST_PROXY_HEADERS=True))

    assert client_ip == "203.0.113.11"


@readable_test_id("отсутствующий client host дает безопасный unknown")
def test_missing_client_host_returns_unknown(_case_id) -> None:
    """RATE-LIMIT-IP-FALLBACK-002: отсутствие client host даёт безопасный fallback."""
    request = make_request(host=None)

    client_ip = resolve_client_ip(request, make_settings(TRUST_PROXY_HEADERS=False))

    assert client_ip == UNKNOWN_CLIENT_IP


@readable_test_id("ipv4 адрес поддерживается")
def test_ipv4_address_is_supported(_case_id) -> None:
    """RATE-LIMIT-IP-V4-001: IPv4 проходит стандартную проверку."""
    request = make_request(host="192.0.2.15")

    assert resolve_client_ip(request, make_settings(TRUST_PROXY_HEADERS=False)) == "192.0.2.15"


@readable_test_id("ipv6 адрес поддерживается")
def test_ipv6_address_is_supported(_case_id) -> None:
    """RATE-LIMIT-IP-V6-001: IPv6 проходит стандартную проверку."""
    request = make_request(host="2001:db8::1")

    assert resolve_client_ip(request, make_settings(TRUST_PROXY_HEADERS=False)) == "2001:db8::1"


@readable_test_id("client key стабилен и не раскрывает ip")
def test_client_key_is_stable_and_masks_ip(_case_id) -> None:
    """RATE-LIMIT-CLIENT-KEY-001: hash стабилен и не содержит полный IP."""
    first_key = build_client_key("203.0.113.10")
    second_key = build_client_key("203.0.113.10")

    assert first_key == second_key
    assert first_key.startswith("ip_sha256:")
    assert "203.0.113.10" not in first_key
