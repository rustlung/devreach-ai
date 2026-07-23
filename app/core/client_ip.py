from __future__ import annotations

import hashlib
import ipaddress
import logging

from fastapi import Request

from app.core.config import Settings
from app.core.logging import get_request_id


logger = logging.getLogger(__name__)
UNKNOWN_CLIENT_IP = "unknown-client"


def resolve_client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = _first_valid_forwarded_ip(forwarded_for)
            if client_ip:
                # На Render исходный клиент приходит через reverse proxy. Доверяем
                # X-Forwarded-For только при явной настройке, чтобы локально не
                # позволять произвольному заголовку подменять ключ rate limit.
                return client_ip
            logger.warning(
                "event=client_ip_resolution_failed request_id=%s source=x_forwarded_for fallback_used=true",
                get_request_id(),
            )

    direct_host = getattr(getattr(request, "client", None), "host", None)
    if direct_host and _is_valid_ip(direct_host):
        return direct_host

    logger.warning(
        "event=client_ip_resolution_failed request_id=%s source=request_client fallback_used=true",
        get_request_id(),
    )
    return UNKNOWN_CLIENT_IP


def build_client_key(client_ip: str) -> str:
    digest = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:8]
    return f"ip_sha256:{digest}"


def _first_valid_forwarded_ip(header_value: str) -> str | None:
    for raw_part in header_value.split(","):
        candidate = raw_part.strip()
        if _is_valid_ip(candidate):
            return candidate
    return None


def _is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True
