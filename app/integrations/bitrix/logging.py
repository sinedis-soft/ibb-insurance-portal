from __future__ import annotations

import logging

from app.logging import LOGGER_NAME


def log_bitrix24_call(
    *,
    request_id: str,
    bitrix_method: str,
    duration_ms: int,
    http_status: int | None,
    status: str,
    error_code: str | None = None,
    retry_count: int = 0,
) -> None:
    logging.getLogger(LOGGER_NAME).info(
        "bitrix24_call",
        extra={
            "request_id": request_id,
            "bitrix_method": bitrix_method,
            "duration_ms": duration_ms,
            "http_status": http_status,
            "status": status,
            "error_code": error_code,
            "retry_count": retry_count,
        },
    )
