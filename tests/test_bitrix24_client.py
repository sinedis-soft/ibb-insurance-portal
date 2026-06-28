from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.integrations.bitrix.client import Bitrix24Client, validate_bitrix24_settings
from app.integrations.bitrix.errors import (
    Bitrix24AuthError,
    Bitrix24ConfigurationError,
    Bitrix24NotFoundError,
    Bitrix24PermissionError,
    Bitrix24RateLimitError,
    Bitrix24TimeoutError,
    Bitrix24TransportError,
    Bitrix24UnexpectedResponseError,
    Bitrix24ValidationError,
)
from app.scripts.check_secrets import main as check_secrets_main

ROOT = Path(__file__).resolve().parents[1]


class FakeHttpClient:
    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
        self.calls.append({"url": url, "json": json})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/15",
        "JWT_SECRET": "test_jwt_secret_with_minimum_32_bytes",
        "COOKIE_SECRET": "test_cookie_secret_with_minimum_32_bytes",
        "BITRIX24_ENABLED": True,
        "BITRIX24_BASE_URL": "https://bitrix.example.test/rest/1",
        "BITRIX24_WEBHOOK_TOKEN": "test-token",
        "BITRIX24_RETRY_BACKOFF_SECONDS": 0,
        "BITRIX24_MAX_RETRIES": 2,
    }
    values.update(overrides)
    return Settings(**values)


def json_response(status_code: int, payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request("POST", "https://example.invalid"))


def text_response(status_code: int, text: str) -> httpx.Response:
    return httpx.Response(status_code, text=text, request=httpx.Request("POST", "https://example.invalid"))


def test_missing_enabled_config_raises_safe_error() -> None:
    with pytest.raises(Bitrix24ConfigurationError) as exc:
        validate_bitrix24_settings(settings(BITRIX24_BASE_URL="replace_me"))

    assert exc.value.error_code == "BITRIX24_CONFIGURATION_ERROR"
    assert "https://" not in str(exc.value)


@pytest.mark.asyncio
async def test_disabled_bitrix24_mode_does_not_call_network() -> None:
    fake = FakeHttpClient([json_response(200, {"result": {}})])
    client = Bitrix24Client(settings=settings(BITRIX24_ENABLED=False), http_client=fake)  # type: ignore[arg-type]

    with pytest.raises(Bitrix24ConfigurationError) as exc:
        await client.call("crm.deal.fields")

    assert exc.value.error_code == "BITRIX24_DISABLED"
    assert fake.calls == []


@pytest.mark.asyncio
async def test_successful_call_returns_typed_response_and_builds_url_in_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = FakeHttpClient([json_response(200, {"result": {"ID": 10}})])
    client = Bitrix24Client(settings=settings(), http_client=fake)  # type: ignore[arg-type]

    with caplog.at_level(logging.INFO, logger="ibb_portal"):
        response = await client.call("crm.deal.get", {"ID": 10}, request_id="req_test")

    assert response.ok is True
    assert response.result == {"ID": 10}
    assert fake.calls[0]["url"] == "https://bitrix.example.test/rest/1/test-token/crm.deal.get"
    assert fake.calls[0]["json"] == {"ID": 10}
    log_record = next(record for record in caplog.records if record.getMessage() == "bitrix24_call")
    assert log_record.bitrix_method == "crm.deal.get"
    assert log_record.request_id == "req_test"
    assert log_record.status == "ok"
    assert "test-token" not in log_record.getMessage()
    assert "crm.deal.get" not in str(fake.calls[0]["json"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ({"error": "NO_AUTH_FOUND", "error_description": "Wrong authorization data"}, Bitrix24AuthError),
        ({"error": "ACCESS_DENIED", "error_description": "Access denied"}, Bitrix24PermissionError),
        ({"error": "NOT_FOUND", "error_description": "Not found"}, Bitrix24NotFoundError),
        ({"error": "INVALID_REQUEST", "error_description": "Bad request"}, Bitrix24ValidationError),
    ],
)
async def test_bitrix_error_response_raises_typed_error(
    payload: dict[str, Any],
    expected_error: type[Exception],
) -> None:
    fake = FakeHttpClient([json_response(200, payload)])
    client = Bitrix24Client(settings=settings(), http_client=fake)  # type: ignore[arg-type]

    with pytest.raises(expected_error):
        await client.call("crm.deal.add", {"fields": {"TITLE": "must not be logged"}})
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_timeout_network_rate_limit_and_invalid_json_are_typed() -> None:
    timeout_client = Bitrix24Client(
        settings=settings(BITRIX24_MAX_RETRIES=0),
        http_client=FakeHttpClient([httpx.TimeoutException("timeout")]),  # type: ignore[arg-type]
    )
    with pytest.raises(Bitrix24TimeoutError):
        await timeout_client.call("crm.deal.get", {"ID": 1})

    network_client = Bitrix24Client(
        settings=settings(BITRIX24_MAX_RETRIES=0),
        http_client=FakeHttpClient([httpx.ConnectError("network")]),  # type: ignore[arg-type]
    )
    with pytest.raises(Bitrix24TransportError):
        await network_client.call("crm.deal.get", {"ID": 1})

    rate_client = Bitrix24Client(
        settings=settings(BITRIX24_MAX_RETRIES=0),
        http_client=FakeHttpClient([json_response(429, {"error": "QUERY_LIMIT_EXCEEDED"})]),  # type: ignore[arg-type]
    )
    with pytest.raises(Bitrix24RateLimitError):
        await rate_client.call("crm.deal.get", {"ID": 1})

    invalid_json_client = Bitrix24Client(
        settings=settings(BITRIX24_MAX_RETRIES=0),
        http_client=FakeHttpClient([text_response(200, "not-json")]),  # type: ignore[arg-type]
    )
    with pytest.raises(Bitrix24UnexpectedResponseError):
        await invalid_json_client.call("crm.deal.get", {"ID": 1})


@pytest.mark.asyncio
async def test_retry_happens_only_for_retryable_errors() -> None:
    retry_fake = FakeHttpClient(
        [
            json_response(429, {"error": "QUERY_LIMIT_EXCEEDED"}),
            json_response(200, {"result": {"ID": 1}}),
        ]
    )
    retry_client = Bitrix24Client(settings=settings(), http_client=retry_fake)  # type: ignore[arg-type]
    response = await retry_client.call("crm.deal.get", {"ID": 1})
    assert response.result == {"ID": 1}
    assert len(retry_fake.calls) == 2

    auth_fake = FakeHttpClient(
        [
            json_response(200, {"error": "NO_AUTH_FOUND"}),
            json_response(200, {"result": {"ID": 1}}),
        ]
    )
    auth_client = Bitrix24Client(settings=settings(), http_client=auth_fake)  # type: ignore[arg-type]
    with pytest.raises(Bitrix24AuthError):
        await auth_client.call("crm.deal.get", {"ID": 1})
    assert len(auth_fake.calls) == 1


@pytest.mark.asyncio
async def test_safe_logging_never_contains_payload_token_or_personal_data(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeHttpClient([json_response(200, {"result": 123})])
    client = Bitrix24Client(settings=settings(), http_client=fake)  # type: ignore[arg-type]
    payload = {
        "fields": {
            "TITLE": "Jane Client",
            "EMAIL": "jane@example.test",
            "PHONE": "+9955550101",
            "VIN": "VINSHOULDNOTLOG123",
            "COMMENTS": "commercial details",
        }
    }

    with caplog.at_level(logging.INFO, logger="ibb_portal"):
        await client.call("crm.deal.add", payload, request_id="req_safe")

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert "test-token" not in rendered
    assert "bitrix.example.test" not in rendered
    assert "Jane Client" not in rendered
    assert "jane@example.test" not in rendered
    assert "+9955550101" not in rendered
    assert "VINSHOULDNOTLOG123" not in rendered
    assert "commercial details" not in rendered


def test_bitrix_mapping_and_http_usage_are_centralized() -> None:
    forbidden_http: list[str] = []
    forbidden_fields: list[str] = []
    allowed_http_files = {
        Path("app/integrations/bitrix/client.py"),
    }
    allowed_field_files = {
        Path("app/integrations/bitrix/field_mapping.py"),
    }
    for path in (ROOT / "app").rglob("*.py"):
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        if relative not in allowed_http_files and ("httpx." in text or "requests.post" in text):
            forbidden_http.append(str(relative))
        if relative not in allowed_field_files and "UF_CRM_" in text:
            forbidden_fields.append(str(relative))

    assert forbidden_http == []
    assert forbidden_fields == []


def test_check_secrets_script_passes_repository() -> None:
    assert check_secrets_main() == 0
