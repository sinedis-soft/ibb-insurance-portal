from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

LOGGER_NAME = "ibb_portal"


def configure_logging(level: str) -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger(LOGGER_NAME)
    logger.disabled = False
    logger.setLevel(resolved_level)


async def safe_request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex}"
    if hasattr(request, "state"):
        request.state.request_id = request_id
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logging.getLogger(LOGGER_NAME).info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.scope.get("route").path
                if request.scope.get("route")
                else request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
