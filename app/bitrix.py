from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings

BITRIX_ERROR_MAP = {
    "Access denied": "BITRIX_ACCESS_DENIED",
    "ACCESS_DENIED": "BITRIX_ACCESS_DENIED",
    "NO_AUTH_FOUND": "BITRIX_NO_AUTH_FOUND",
    "QUERY_LIMIT_EXCEEDED": "BITRIX_QUERY_LIMIT_EXCEEDED",
    "OPERATION_TIME_LIMIT": "BITRIX_OPERATION_TIME_LIMIT",
}


class BitrixError(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code


def map_bitrix_error(error: str | None) -> str:
    if not error:
        return "BITRIX_REQUEST_FAILED"
    return BITRIX_ERROR_MAP.get(error, "BITRIX_REQUEST_FAILED")


async def call_bitrix_method(method: str, payload: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    resolved = settings or get_settings()
    if not resolved.bitrix_webhook_url or resolved.bitrix_webhook_url == "replace_me":
        raise BitrixError("BITRIX_NOT_CONFIGURED")
    url = f"{resolved.bitrix_webhook_url.rstrip('/')}/{method}"
    try:
        async with httpx.AsyncClient(timeout=resolved.bitrix_timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise BitrixError("BITRIX_TRANSPORT_ERROR") from exc
    if response.status_code >= 400:
        raise BitrixError("BITRIX_HTTP_ERROR")
    data = response.json()
    if data.get("error"):
        raise BitrixError(map_bitrix_error(str(data.get("error"))))
    result = data.get("result")
    if not isinstance(result, dict):
        raise BitrixError("BITRIX_UNEXPECTED_RESPONSE")
    return result


async def get_contact(contact_id: int, settings: Settings | None = None) -> dict[str, Any]:
    return await call_bitrix_method("crm.contact.get", {"ID": contact_id}, settings)


def latest_email_from_contact(contact: dict[str, Any]) -> str | None:
    email_items = contact.get("EMAIL")
    if not isinstance(email_items, list):
        return None
    candidates = [
        item
        for item in email_items
        if isinstance(item, dict) and isinstance(item.get("VALUE"), str) and item["VALUE"].strip()
    ]
    if not candidates:
        return None

    def sort_key(item: dict[str, Any]) -> int:
        try:
            return int(item.get("ID") or 0)
        except (TypeError, ValueError):
            return 0

    return max(candidates, key=sort_key)["VALUE"].strip()
