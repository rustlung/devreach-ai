from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    service: str
    version: str
    database: Literal["available", "unavailable"]
    message: str | None = None
