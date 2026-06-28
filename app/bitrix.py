from __future__ import annotations

from typing import Any

from app.config import Settings
from app.integrations.bitrix.client import Bitrix24Client
from app.integrations.bitrix.errors import Bitrix24Error
from app.integrations.bitrix.field_mapping import BITRIX_DEAL_FIELDS, CONTACT_LANGUAGE_FIELD

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

__all__ = [
    "BITRIX_DEAL_FIELDS",
    "BitrixError",
    "call_bitrix_method",
    "call_bitrix_raw",
    "contact_language_from_contact",
    "create_deal",
    "get_company",
    "get_contact",
    "latest_email_from_contact",
]


class BitrixError(Bitrix24Error):
    pass


def _legacy_error(exc: Bitrix24Error) -> BitrixError:
    return BitrixError(
        exc.error_code,
        request_id=exc.request_id,
        bitrix_method=exc.bitrix_method,
        http_status=exc.http_status,
    )


async def call_bitrix_raw(method: str, payload: dict[str, Any], settings: Settings | None = None) -> Any:
    try:
        response = await Bitrix24Client(settings=settings).call(method, payload)
    except Bitrix24Error as exc:
        raise _legacy_error(exc) from exc
    return response.result


async def call_bitrix_method(method: str, payload: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    result = await call_bitrix_raw(method, payload, settings)
    if not isinstance(result, dict):
        raise BitrixError("BITRIX24_UNEXPECTED_RESPONSE", bitrix_method=method)
    return result


async def create_deal(fields: dict[str, Any], settings: Settings | None = None) -> int:
    try:
        return await Bitrix24Client(settings=settings).create_deal(fields)
    except Bitrix24Error as exc:
        raise _legacy_error(exc) from exc


async def get_contact(contact_id: int, settings: Settings | None = None) -> dict[str, Any]:
    try:
        return await Bitrix24Client(settings=settings).get_contact(contact_id)
    except Bitrix24Error as exc:
        raise _legacy_error(exc) from exc


async def get_company(company_id: int, settings: Settings | None = None) -> dict[str, Any]:
    try:
        return await Bitrix24Client(settings=settings).get_company(company_id)
    except Bitrix24Error as exc:
        raise _legacy_error(exc) from exc


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
