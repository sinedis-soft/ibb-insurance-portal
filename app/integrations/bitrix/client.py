from __future__ import annotations

import asyncio
import base64
import random
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import Settings, get_settings
from app.integrations.bitrix.errors import (
    Bitrix24AuthError,
    Bitrix24ConfigurationError,
    Bitrix24Error,
    Bitrix24NotFoundError,
    Bitrix24PermissionError,
    Bitrix24RateLimitError,
    Bitrix24TimeoutError,
    Bitrix24TransportError,
    Bitrix24UnexpectedResponseError,
    Bitrix24ValidationError,
)
from app.integrations.bitrix.logging import log_bitrix24_call
from app.integrations.bitrix.schemas import Bitrix24Response

BITRIX_METHOD_PATTERN = re.compile(r"^[a-zA-Z0-9_.]+$")
RETRYABLE_HTTP_STATUSES = {429, 502, 503, 504}
RETRYABLE_BITRIX_ERRORS = {"QUERY_LIMIT_EXCEEDED", "OPERATION_TIME_LIMIT", "OVERLOAD_LIMIT"}

BITRIX_ERROR_CLASS_MAP: dict[str, type[Bitrix24Error]] = {
    "NO_AUTH_FOUND": Bitrix24AuthError,
    "expired_token": Bitrix24AuthError,
    "ACCESS_DENIED": Bitrix24PermissionError,
    "Access denied": Bitrix24PermissionError,
    "INVALID_CREDENTIALS": Bitrix24PermissionError,
    "insufficient_scope": Bitrix24PermissionError,
    "user_access_error": Bitrix24PermissionError,
    "NOT_FOUND": Bitrix24NotFoundError,
    "Not found": Bitrix24NotFoundError,
    "OWNER_NOT_FOUND": Bitrix24NotFoundError,
    "ERROR_NOT_FOUND": Bitrix24NotFoundError,
    "QUERY_LIMIT_EXCEEDED": Bitrix24RateLimitError,
    "OVERLOAD_LIMIT": Bitrix24RateLimitError,
    "INVALID_REQUEST": Bitrix24ValidationError,
    "INVALID_ARG_VALUE": Bitrix24ValidationError,
}


def _is_placeholder(value: str | None) -> bool:
    return value in {None, "", "replace_me", "replace-me"}


def validate_bitrix24_settings(settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    if not resolved.bitrix24_enabled:
        return
    if _is_placeholder(resolved.bitrix24_base_url) or _is_placeholder(resolved.bitrix24_webhook_token):
        raise Bitrix24ConfigurationError("BITRIX24_CONFIGURATION_ERROR")


class Bitrix24Client:
    def __init__(self, settings: Settings | None = None, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._http_client = http_client

    def _request_id(self, request_id: str | None) -> str:
        return request_id or f"req_{uuid4().hex}"

    def _method_url(self, method: str) -> str:
        if not BITRIX_METHOD_PATTERN.fullmatch(method):
            raise Bitrix24ValidationError("BITRIX24_METHOD_INVALID", bitrix_method=method)
        validate_bitrix24_settings(self.settings)
        if not self.settings.bitrix24_enabled:
            raise Bitrix24ConfigurationError("BITRIX24_DISABLED", bitrix_method=method)
        base_url = str(self.settings.bitrix24_base_url).rstrip("/")
        token = str(self.settings.bitrix24_webhook_token).strip("/")
        return f"{base_url}/{token}/{method}"

    def _error_for_response(
        self,
        *,
        method: str,
        request_id: str,
        http_status: int | None,
        error_code: str,
    ) -> Bitrix24Error:
        if http_status == 401:
            error_cls: type[Bitrix24Error] = Bitrix24AuthError
        elif http_status == 403:
            error_cls = Bitrix24PermissionError
        elif http_status == 404:
            error_cls = Bitrix24NotFoundError
        elif http_status == 429:
            error_cls = Bitrix24RateLimitError
        elif http_status and http_status >= 500:
            error_cls = Bitrix24TransportError
        else:
            error_cls = BITRIX_ERROR_CLASS_MAP.get(error_code, Bitrix24ValidationError)
        return error_cls(error_code, request_id=request_id, bitrix_method=method, http_status=http_status)

    def _is_retryable_error(self, error: Bitrix24Error) -> bool:
        if isinstance(error, (Bitrix24RateLimitError, Bitrix24TimeoutError, Bitrix24TransportError)):
            return True
        return error.error_code in RETRYABLE_BITRIX_ERRORS

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        request_id: str | None = None,
    ) -> Bitrix24Response:
        resolved_request_id = self._request_id(request_id)
        started = time.perf_counter()
        retry_count = 0
        http_status: int | None = None
        last_error: Bitrix24Error | None = None
        url = self._method_url(method)
        max_retries = max(0, self.settings.bitrix24_max_retries)

        for attempt in range(max_retries + 1):
            try:
                response = await self._post(url, params or {})
                http_status = response.status_code
                data = self._response_json(response, method=method, request_id=resolved_request_id)
                if response.status_code in RETRYABLE_HTTP_STATUSES:
                    raise Bitrix24RateLimitError(
                        "BITRIX24_RATE_LIMIT" if response.status_code == 429 else "BITRIX24_TRANSPORT_ERROR",
                        request_id=resolved_request_id,
                        bitrix_method=method,
                        http_status=response.status_code,
                    )
                if response.status_code == 401:
                    raise Bitrix24AuthError(
                        "BITRIX24_AUTH_ERROR",
                        request_id=resolved_request_id,
                        bitrix_method=method,
                        http_status=response.status_code,
                    )
                if response.status_code == 403:
                    raise Bitrix24PermissionError(
                        "BITRIX24_PERMISSION_ERROR",
                        request_id=resolved_request_id,
                        bitrix_method=method,
                        http_status=response.status_code,
                    )
                if response.status_code >= 400:
                    raise self._error_for_response(
                        method=method,
                        request_id=resolved_request_id,
                        http_status=response.status_code,
                        error_code="BITRIX24_HTTP_ERROR",
                    )
                if not isinstance(data, dict):
                    raise Bitrix24UnexpectedResponseError(
                        "BITRIX24_UNEXPECTED_RESPONSE",
                        request_id=resolved_request_id,
                        bitrix_method=method,
                        http_status=response.status_code,
                    )
                raw_error = data.get("error")
                if raw_error:
                    error_code = str(raw_error)
                    if error_code in RETRYABLE_BITRIX_ERRORS:
                        raise Bitrix24RateLimitError(
                            "BITRIX24_RATE_LIMIT" if error_code == "QUERY_LIMIT_EXCEEDED" else error_code,
                            request_id=resolved_request_id,
                            bitrix_method=method,
                            http_status=response.status_code,
                        )
                    raise self._error_for_response(
                        method=method,
                        request_id=resolved_request_id,
                        http_status=response.status_code,
                        error_code=error_code,
                    )
                duration_ms = int((time.perf_counter() - started) * 1000)
                log_bitrix24_call(
                    request_id=resolved_request_id,
                    bitrix_method=method,
                    duration_ms=duration_ms,
                    http_status=response.status_code,
                    status="ok",
                    retry_count=retry_count,
                )
                return Bitrix24Response(
                    ok=True,
                    result=data.get("result"),
                    http_status=response.status_code,
                    request_id=resolved_request_id,
                    duration_ms=duration_ms,
                )
            except Bitrix24Error as exc:
                last_error = exc
                if attempt >= max_retries or not self._is_retryable_error(exc):
                    break
                retry_count += 1
                await self._sleep_before_retry(attempt)
            except httpx.TimeoutException:
                last_error = Bitrix24TimeoutError(
                    "BITRIX24_TIMEOUT",
                    request_id=resolved_request_id,
                    bitrix_method=method,
                    http_status=http_status,
                )
                if attempt >= max_retries:
                    break
                retry_count += 1
                await self._sleep_before_retry(attempt)
            except httpx.HTTPError:
                last_error = Bitrix24TransportError(
                    "BITRIX24_TRANSPORT_ERROR",
                    request_id=resolved_request_id,
                    bitrix_method=method,
                    http_status=http_status,
                )
                if attempt >= max_retries:
                    break
                retry_count += 1
                await self._sleep_before_retry(attempt)

        assert last_error is not None
        duration_ms = int((time.perf_counter() - started) * 1000)
        log_bitrix24_call(
            request_id=resolved_request_id,
            bitrix_method=method,
            duration_ms=duration_ms,
            http_status=last_error.http_status,
            status="error",
            error_code=last_error.error_code,
            retry_count=retry_count,
        )
        raise last_error

    async def _post(self, url: str, params: dict[str, Any]) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.post(url, json=params)
        async with httpx.AsyncClient(timeout=self.settings.bitrix24_timeout_seconds) as client:
            return await client.post(url, json=params)

    def _response_json(self, response: httpx.Response, *, method: str, request_id: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise Bitrix24UnexpectedResponseError(
                "BITRIX24_UNEXPECTED_RESPONSE",
                request_id=request_id,
                bitrix_method=method,
                http_status=response.status_code,
            ) from exc

    async def _sleep_before_retry(self, attempt: int) -> None:
        backoff = max(0.0, self.settings.bitrix24_retry_backoff_seconds)
        delay = backoff * (2**attempt)
        if delay > 0:
            delay += random.uniform(0, min(0.25, delay / 4))
        await asyncio.sleep(delay)

    async def fetch_deal_fields(self, *, request_id: str | None = None) -> dict[str, Any]:
        return await self._dict_result("crm.deal.fields", request_id=request_id)

    async def fetch_company_fields(self, *, request_id: str | None = None) -> dict[str, Any]:
        return await self._dict_result("crm.company.fields", request_id=request_id)

    async def fetch_contact_fields(self, *, request_id: str | None = None) -> dict[str, Any]:
        return await self._dict_result("crm.contact.fields", request_id=request_id)

    async def get_deal(self, deal_id: int, *, request_id: str | None = None) -> dict[str, Any]:
        return await self._dict_result("crm.deal.get", {"ID": deal_id}, request_id=request_id)

    async def create_deal(self, fields: dict[str, Any], *, request_id: str | None = None) -> int:
        response = await self.call(
            "crm.deal.add",
            {"fields": fields, "params": {"REGISTER_SONET_EVENT": "N"}},
            request_id=request_id,
        )
        try:
            deal_id = int(response.result)
        except (TypeError, ValueError) as exc:
            raise Bitrix24UnexpectedResponseError(
                "BITRIX24_UNEXPECTED_RESPONSE",
                request_id=response.request_id,
                bitrix_method="crm.deal.add",
                http_status=response.http_status,
            ) from exc
        if deal_id <= 0:
            raise Bitrix24UnexpectedResponseError(
                "BITRIX24_UNEXPECTED_RESPONSE",
                request_id=response.request_id,
                bitrix_method="crm.deal.add",
                http_status=response.http_status,
            )
        return deal_id

    async def update_deal(self, deal_id: int, fields: dict[str, Any], *, request_id: str | None = None) -> bool:
        response = await self.call("crm.deal.update", {"ID": deal_id, "fields": fields}, request_id=request_id)
        return bool(response.result)

    async def get_company(self, company_id: int, *, request_id: str | None = None) -> dict[str, Any]:
        return await self._dict_result("crm.company.get", {"ID": company_id}, request_id=request_id)

    async def get_contact(self, contact_id: int, *, request_id: str | None = None) -> dict[str, Any]:
        return await self._dict_result("crm.contact.get", {"ID": contact_id}, request_id=request_id)

    async def add_timeline_comment(
        self,
        *,
        entity_id: int,
        comment: str,
        entity_type: str = "deal",
        request_id: str | None = None,
    ) -> int:
        response = await self.call(
            "crm.timeline.comment.add",
            {"fields": {"ENTITY_ID": entity_id, "ENTITY_TYPE": entity_type, "COMMENT": comment}},
            request_id=request_id,
        )
        try:
            return int(response.result)
        except (TypeError, ValueError) as exc:
            raise Bitrix24UnexpectedResponseError(
                "BITRIX24_UNEXPECTED_RESPONSE",
                request_id=response.request_id,
                bitrix_method="crm.timeline.comment.add",
                http_status=response.http_status,
            ) from exc

    async def upload_file_to_deal(
        self,
        *,
        folder_id: int,
        deal_id: int,
        file_path: Path,
        request_id: str | None = None,
    ) -> str:
        safe_name = f"portal-document-{deal_id}{file_path.suffix.lower() or '.bin'}"
        encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
        response = await self.call(
            "disk.folder.uploadfile",
            {
                "id": folder_id,
                "data": {"NAME": safe_name},
                "fileContent": [safe_name, encoded],
                "generateUniqueName": True,
            },
            request_id=request_id,
        )
        if not isinstance(response.result, dict):
            raise Bitrix24UnexpectedResponseError(
                "BITRIX24_UNEXPECTED_RESPONSE",
                request_id=response.request_id,
                bitrix_method="disk.folder.uploadfile",
                http_status=response.http_status,
            )
        bitrix_file_id = response.result.get("ID") or response.result.get("FILE_ID")
        if not bitrix_file_id:
            raise Bitrix24UnexpectedResponseError(
                "BITRIX24_UNEXPECTED_RESPONSE",
                request_id=response.request_id,
                bitrix_method="disk.folder.uploadfile",
                http_status=response.http_status,
            )
        await self.add_timeline_comment(
            entity_id=deal_id,
            comment=f"Portal document uploaded: {bitrix_file_id}",
            request_id=request_id,
        )
        return str(bitrix_file_id)

    async def _dict_result(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        response = await self.call(method, params, request_id=request_id)
        if not isinstance(response.result, dict):
            raise Bitrix24UnexpectedResponseError(
                "BITRIX24_UNEXPECTED_RESPONSE",
                request_id=response.request_id,
                bitrix_method=method,
                http_status=response.http_status,
            )
        return response.result


def get_bitrix24_client(settings: Settings | None = None) -> Bitrix24Client:
    return Bitrix24Client(settings=settings)
