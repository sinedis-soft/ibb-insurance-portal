from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings

CONTACT_LANGUAGE_FIELD = "UF_CRM_1753957395750"
DEFAULT_LANGUAGE = "ru"
BITRIX_CONTACT_LANGUAGE_MAP = {
    "3935": "be",
    "3937": "ru",
    "3939": "uk",
    "3941": "ka",
    "3943": "hy",
    "3945": "kk",
    "3947": "uz",
    "3949": "ky",
    "3951": "az",
    "3953": "en",
    "3955": "pl",
    "3957": "tr",
    "4761": "ar",
    "4763": "ckb",
    "4765": "kmr",
    "4767": "ro",
    "4769": "sr",
    "4771": "sq",
    "4773": "fa",
    "4775": "he",
    "4777": "mn",
}

BITRIX_ERROR_MAP = {
    "Access denied": "BITRIX_ACCESS_DENIED",
    "ACCESS_DENIED": "BITRIX_ACCESS_DENIED",
    "Not found": "BITRIX_NOT_FOUND",
    "NOT_FOUND": "BITRIX_NOT_FOUND",
    "NO_AUTH_FOUND": "BITRIX_NO_AUTH_FOUND",
    "QUERY_LIMIT_EXCEEDED": "BITRIX_QUERY_LIMIT_EXCEEDED",
    "OPERATION_TIME_LIMIT": "BITRIX_OPERATION_TIME_LIMIT",
}

BITRIX_DEAL_FIELDS = {
    "portal_application_id": "UF_CRM_1782659474410",
    "portal_application_type": "UF_CRM_1782660209555",
    "portal_source": "UF_CRM_1782660734915",
    "portal_channel": "UF_CRM_1782660775332",
    "portal_sync_status": "UF_CRM_1782660821873",
    "portal_last_sync_at": "UF_CRM_1782660834442",
    "portal_sync_error": "UF_CRM_1782660852370",
}


class BitrixError(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code


def map_bitrix_error(error: str | None) -> str:
    if not error:
        return "BITRIX_REQUEST_FAILED"
    return BITRIX_ERROR_MAP.get(error, "BITRIX_REQUEST_FAILED")


async def call_bitrix_raw(method: str, payload: dict[str, Any], settings: Settings | None = None) -> Any:
    resolved = settings or get_settings()
    bitrix_webhook_url = resolved.resolved_bitrix_webhook_url
    if not bitrix_webhook_url or bitrix_webhook_url == "replace_me":
        raise BitrixError("BITRIX_NOT_CONFIGURED")
    url = f"{bitrix_webhook_url.rstrip('/')}/{method}"
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
    return data.get("result")


async def call_bitrix_method(method: str, payload: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    result = await call_bitrix_raw(method, payload, settings)
    if not isinstance(result, dict):
        raise BitrixError("BITRIX_UNEXPECTED_RESPONSE")
    return result


async def create_deal(fields: dict[str, Any], settings: Settings | None = None) -> int:
    result = await call_bitrix_raw(
        "crm.deal.add",
        {"fields": fields, "params": {"REGISTER_SONET_EVENT": "N"}},
        settings,
    )
    try:
        deal_id = int(result)
    except (TypeError, ValueError) as exc:
        raise BitrixError("BITRIX_UNEXPECTED_RESPONSE") from exc
    if deal_id <= 0:
        raise BitrixError("BITRIX_UNEXPECTED_RESPONSE")
    return deal_id


async def get_contact(contact_id: int, settings: Settings | None = None) -> dict[str, Any]:
    return await call_bitrix_method("crm.contact.get", {"ID": contact_id}, settings)


async def get_company(company_id: int, settings: Settings | None = None) -> dict[str, Any]:
    return await call_bitrix_method("crm.company.get", {"ID": company_id}, settings)


def contact_language_from_contact(contact: dict[str, Any]) -> str:
    raw_value = contact.get(CONTACT_LANGUAGE_FIELD)
    if isinstance(raw_value, list):
        raw_value = raw_value[0] if raw_value else None
    if isinstance(raw_value, dict):
        raw_value = raw_value.get("ID") or raw_value.get("VALUE")
    if raw_value is None:
        return DEFAULT_LANGUAGE
    return BITRIX_CONTACT_LANGUAGE_MAP.get(str(raw_value).strip(), DEFAULT_LANGUAGE)


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
