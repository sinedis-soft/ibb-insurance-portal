from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Bitrix24Response(BaseModel):
    ok: bool
    result: Any | None = None
    error_code: str | None = None
    error_description: str | None = None
    http_status: int | None = None
    request_id: str
    duration_ms: int
