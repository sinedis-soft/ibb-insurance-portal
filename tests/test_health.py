from __future__ import annotations

import logging
from types import SimpleNamespace

from fastapi import Response
from fastapi.testclient import TestClient


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_health_and_live_return_ok(migrated_database: str) -> None:
    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    client = TestClient(create_app())

    assert client.get("/health").json() == {
        "status": "ok",
        "service": "ibb-portal-backend",
    }
    assert client.get("/health/live").json() == {"status": "ok"}


def test_ready_returns_ok_when_dependencies_are_available(
    monkeypatch,
    migrated_database: str,
) -> None:
    from app.config import get_settings
    from app.main import create_app
    from app.routers import health as health_module

    async def redis_ok() -> str:
        return "ok"

    get_settings.cache_clear()
    monkeypatch.setattr(health_module, "check_redis", redis_ok)
    client = TestClient(create_app())

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "database": "ok",
            "redis": "ok",
            "migrations": "ok",
            "reference_data": "ok",
        },
    }


async def test_request_logging_does_not_log_body_or_personal_data() -> None:
    from app.logging import safe_request_logging_middleware

    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    request = SimpleNamespace(
        headers={},
        method="POST",
        scope={"route": SimpleNamespace(path="/health")},
        url=SimpleNamespace(path="/health?email=client@example.com"),
        body={
            "email": "client@example.com",
            "phone": "+995555010101",
            "comment": "urgent policy request",
            "vin": "ABC123456789",
        },
    )

    async def call_next(_request) -> Response:
        return Response(status_code=200)

    try:
        await safe_request_logging_middleware(request, call_next)
    finally:
        logger.removeHandler(handler)

    log_text = "\n".join(handler.messages)
    assert "request_completed" in log_text
    assert "client@example.com" not in log_text
    assert "+995555010101" not in log_text
    assert "urgent policy request" not in log_text
    assert "ABC123456789" not in log_text
