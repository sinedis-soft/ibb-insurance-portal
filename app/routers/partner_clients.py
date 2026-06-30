from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event, now_utc
from app.bitrix import BITRIX_COMPANY_FIELDS, BitrixError, create_company
from app.company_access import normalize_company_id
from app.config import Settings, get_settings
from app.db import get_db
from app.integrations.bitrix.field_mapping import PARTNER_CLIENT_CHECK_COMPANY_STATUS_IDS
from app.models import partner_client_requests
from app.partner_client_requests import (
    PARTNER_CLIENT_LINKED_DECISION,
    ensure_partner_client_link,
    parse_partner_client_request_id,
    public_partner_client_request,
)
from app.routers.auth import auth_error, get_current_user_from_cookie

router = APIRouter(tags=["partner-clients"])
DB_SESSION = Depends(get_db)
APP_SETTINGS = Depends(get_settings)
EDITABLE_STATUSES = {"pending", "clarification_required"}
PARTNER_CLIENT_STATUSES = {"pending", "clarification_required", "confirmed", "duplicate_found", "rejected"}
PARTNER_CLIENT_DECISIONS = PARTNER_CLIENT_STATUSES | {PARTNER_CLIENT_LINKED_DECISION}


class PartnerClientPayload(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    country: str | None = Field(default=None, max_length=16)
    registration_number: str | None = Field(default=None, max_length=128)
    tax_id: str | None = Field(default=None, max_length=128)
    address: str | None = Field(default=None, max_length=512)
    contact_name: str = Field(min_length=1, max_length=255)
    contact_email: str = Field(min_length=3, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=64)
    comment: str | None = Field(default=None, max_length=4000)


class PartnerClientStatusPayload(BaseModel):
    status: str
    confirmed_bitrix_company_id: int | str | None = None
    linked_bitrix_company_id: int | str | None = None
    rejection_reason: str | None = Field(default=None, max_length=4000)
    clarification_comment: str | None = Field(default=None, max_length=4000)


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def payload_values(payload: PartnerClientPayload) -> dict[str, Any]:
    contact_email = payload.contact_email.strip().lower()
    if "@" not in contact_email or "." not in contact_email.rsplit("@", maxsplit=1)[-1]:
        raise ValueError("INVALID_EMAIL")
    return {
        "company_name": payload.company_name.strip(),
        "country": clean_text(payload.country.upper() if payload.country else None),
        "registration_number": clean_text(payload.registration_number),
        "tax_id": clean_text(payload.tax_id),
        "address": clean_text(payload.address),
        "contact_name": payload.contact_name.strip(),
        "contact_email": contact_email,
        "contact_phone": clean_text(payload.contact_phone),
        "comment": clean_text(payload.comment),
    }


def require_partner(request: Request, session: Session):
    user = get_current_user_from_cookie(request, session)
    if user.user_type != "partner" or user.status != "active":
        raise auth_error(status.HTTP_403_FORBIDDEN, "PARTNER_ROLE_REQUIRED", request)
    return user


def require_superadmin(request: Request, session: Session):
    user = get_current_user_from_cookie(request, session)
    if user.role_code != "superadmin" or user.status != "active":
        raise auth_error(status.HTTP_403_FORBIDDEN, "SUPERADMIN_REQUIRED", request)
    return user


def owned_partner_client_request(session: Session, *, request_id: str, partner_user_id: int, request: Request):
    parsed_id = parse_partner_client_request_id(request_id)
    if parsed_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "PARTNER_CLIENT_REQUEST_NOT_FOUND", request)
    row = (
        session.execute(
            select(partner_client_requests).where(
                partner_client_requests.c.id == parsed_id,
                partner_client_requests.c.partner_user_id == partner_user_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        audit_event(
            session,
            action="partner_client_foreign_access_denied",
            object_type="partner_client_request",
            object_id=str(parsed_id),
            request=request,
            actor_user_id=partner_user_id,
            metadata={"reason_code": "PARTNER_CLIENT_REQUEST_NOT_FOUND"},
        )
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "PARTNER_CLIENT_REQUEST_NOT_FOUND", request)
    return row


def safe_join_comment(*parts: str | None) -> str | None:
    values = [part.strip() for part in parts if isinstance(part, str) and part.strip()]
    return "\n".join(values) if values else None


def bitrix_company_fields(request_id: int, values: dict[str, Any], partner_bitrix_id: int | None) -> dict[str, Any]:
    comment = safe_join_comment(
        values.get("comment"),
        f"Portal partner client request: pcr_{request_id}",
        "Portal source: IBB Insurance Portal / Partner Portal",
    )
    fields: dict[str, Any] = {
        "TITLE": values["company_name"],
        "ORIGINATOR_ID": "ibb_portal",
        "ORIGIN_ID": f"partner_client_request:{request_id}",
        "COMMENTS": comment,
        "ADDRESS": values.get("address"),
        "ADDRESS_COUNTRY_CODE": values.get("country"),
        BITRIX_COMPANY_FIELDS["partner_client_check_status"]: PARTNER_CLIENT_CHECK_COMPANY_STATUS_IDS["pending"],
        "EMAIL": [{"VALUE": values["contact_email"], "VALUE_TYPE": "WORK"}],
    }
    if partner_bitrix_id:
        fields[BITRIX_COMPANY_FIELDS["portal_partner_bitrix_id"]] = partner_bitrix_id
    if values.get("contact_phone"):
        fields["PHONE"] = [{"VALUE": values["contact_phone"], "VALUE_TYPE": "WORK"}]
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


async def sync_bitrix_check_object(
    session: Session,
    *,
    request_id: int,
    values: dict[str, Any],
    partner,
    request: Request,
    settings: Settings,
) -> None:
    audit_event(
        session,
        action="partner_client_check_bitrix_create_attempt",
        object_type="partner_client_request",
        object_id=str(request_id),
        request=request,
        actor_user_id=partner.id,
        metadata={"bitrix_check_entity_type": "company", "status": "pending"},
    )
    try:
        company_id = await create_company(
            bitrix_company_fields(request_id, values, partner.bitrix_contact_id),
            settings,
        )
    except BitrixError as exc:
        session.execute(
            update(partner_client_requests)
            .where(partner_client_requests.c.id == request_id)
            .values(
                bitrix_check_status="pending",
                bitrix_sync_status="failed",
                bitrix_sync_error_code=exc.error_code,
                bitrix_sync_error=exc.error_code,
            )
        )
        audit_event(
            session,
            action="partner_client_check_bitrix_create_failed",
            object_type="partner_client_request",
            object_id=str(request_id),
            request=request,
            actor_user_id=partner.id,
            metadata={"error_code": exc.error_code, "bitrix_check_entity_type": "company"},
        )
        return
    session.execute(
        update(partner_client_requests)
        .where(partner_client_requests.c.id == request_id)
        .values(
            bitrix_check_entity_type="company",
            bitrix_check_entity_id=company_id,
            bitrix_check_status="pending",
            bitrix_sync_status="synced",
            bitrix_sync_error_code=None,
            bitrix_sync_error=None,
            bitrix_synced_at=now_utc(),
        )
    )
    audit_event(
        session,
        action="partner_client_check_bitrix_created",
        object_type="partner_client_request",
        object_id=str(request_id),
        request=request,
        actor_user_id=partner.id,
        bitrix_company_id=company_id,
        metadata={"bitrix_check_entity_type": "company", "bitrix_check_entity_id": company_id},
    )


@router.post("/partner/clients", status_code=status.HTTP_201_CREATED)
async def create_partner_client(
    payload: PartnerClientPayload,
    request: Request,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, Any]:
    partner = require_partner(request, session)
    try:
        values = payload_values(payload)
    except ValueError as exc:
        raise auth_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_EMAIL", request) from exc
    request_id = session.execute(
        insert(partner_client_requests)
        .values(
            partner_user_id=partner.id,
            created_by_user_id=partner.id,
            status="pending",
            bitrix_sync_status="pending",
            **values,
        )
        .returning(partner_client_requests.c.id)
    ).scalar_one()
    audit_event(
        session,
        action="partner_client_created",
        object_type="partner_client_request",
        object_id=str(request_id),
        request=request,
        actor_user_id=partner.id,
        metadata={"status": "pending"},
    )
    await sync_bitrix_check_object(
        session,
        request_id=request_id,
        values=values,
        partner=partner,
        request=request,
        settings=settings,
    )
    session.commit()
    row = (
        session.execute(select(partner_client_requests).where(partner_client_requests.c.id == request_id))
        .mappings()
        .one()
    )
    return {"client": public_partner_client_request(row)}


@router.get("/partner/clients")
def list_partner_clients(request: Request, session: Session = DB_SESSION) -> dict[str, list[dict[str, Any]]]:
    partner = require_partner(request, session)
    rows = (
        session.execute(
            select(partner_client_requests)
            .where(partner_client_requests.c.partner_user_id == partner.id)
            .order_by(partner_client_requests.c.created_at.desc())
        )
        .mappings()
        .all()
    )
    return {"items": [public_partner_client_request(row) for row in rows]}


@router.get("/partner/clients/{client_request_id}")
def get_partner_client(
    client_request_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    partner = require_partner(request, session)
    row = owned_partner_client_request(
        session,
        request_id=client_request_id,
        partner_user_id=partner.id,
        request=request,
    )
    return {"client": public_partner_client_request(row)}


@router.patch("/partner/clients/{client_request_id}")
def update_partner_client(
    client_request_id: str,
    payload: PartnerClientPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    partner = require_partner(request, session)
    row = owned_partner_client_request(
        session,
        request_id=client_request_id,
        partner_user_id=partner.id,
        request=request,
    )
    if row.status not in EDITABLE_STATUSES:
        raise auth_error(status.HTTP_403_FORBIDDEN, "PARTNER_CLIENT_NOT_EDITABLE", request)
    try:
        values = payload_values(payload)
    except ValueError as exc:
        raise auth_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_EMAIL", request) from exc
    new_status = "pending" if row.status == "clarification_required" else row.status
    session.execute(
        update(partner_client_requests)
        .where(partner_client_requests.c.id == row.id)
        .values(**values, status=new_status, bitrix_sync_status="retry_required")
    )
    audit_event(
        session,
        action="partner_client_updated",
        object_type="partner_client_request",
        object_id=str(row.id),
        request=request,
        actor_user_id=partner.id,
        metadata={"old_status": row.status, "new_status": new_status},
    )
    session.commit()
    updated = (
        session.execute(select(partner_client_requests).where(partner_client_requests.c.id == row.id))
        .mappings()
        .one()
    )
    return {"client": public_partner_client_request(updated)}


@router.get("/admin/partner-clients")
def list_all_partner_clients(request: Request, session: Session = DB_SESSION) -> dict[str, list[dict[str, Any]]]:
    require_superadmin(request, session)
    rows = (
        session.execute(select(partner_client_requests).order_by(partner_client_requests.c.created_at.desc()))
        .mappings()
        .all()
    )
    return {"items": [public_partner_client_request(row) for row in rows]}


@router.patch("/admin/partner-clients/{client_request_id}/status")
def update_partner_client_status(
    client_request_id: str,
    payload: PartnerClientStatusPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    admin = require_superadmin(request, session)
    parsed_id = parse_partner_client_request_id(client_request_id)
    if parsed_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "PARTNER_CLIENT_REQUEST_NOT_FOUND", request)
    if payload.status not in PARTNER_CLIENT_DECISIONS:
        raise auth_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "PARTNER_CLIENT_STATUS_INVALID", request)
    row = (
        session.execute(select(partner_client_requests).where(partner_client_requests.c.id == parsed_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "PARTNER_CLIENT_REQUEST_NOT_FOUND", request)
    confirmed_company_id = (
        normalize_company_id(payload.confirmed_bitrix_company_id)
        if payload.confirmed_bitrix_company_id
        else None
    )
    linked_company_id = (
        normalize_company_id(payload.linked_bitrix_company_id)
        if payload.linked_bitrix_company_id
        else None
    )
    if payload.status == PARTNER_CLIENT_LINKED_DECISION and linked_company_id is None:
        raise auth_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "LINKED_BITRIX_COMPANY_REQUIRED", request)
    company_id = linked_company_id or confirmed_company_id
    stored_status = "confirmed" if payload.status == PARTNER_CLIENT_LINKED_DECISION else payload.status
    if stored_status == "confirmed" and company_id is None:
        raise auth_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "BITRIX_COMPANY_NOT_FOUND", request)
    values: dict[str, Any] = {
        "status": stored_status,
        "bitrix_check_status": "confirmed" if payload.status == PARTNER_CLIENT_LINKED_DECISION else stored_status,
        "decision_status": payload.status,
        "decision_reason": clean_text(payload.rejection_reason) if payload.status == "rejected" else None,
        "decided_at": now_utc(),
        "rejection_reason": clean_text(payload.rejection_reason),
        "clarification_comment": clean_text(payload.clarification_comment),
        "linked_to_existing": payload.status == PARTNER_CLIENT_LINKED_DECISION,
        "linked_bitrix_company_id": linked_company_id,
    }
    if company_id is not None:
        values["confirmed_bitrix_company_id"] = company_id
        values["confirmed_company_id"] = company_id
    if row.original_bitrix_company_id is None and row.bitrix_check_entity_id:
        values["original_bitrix_company_id"] = row.bitrix_check_entity_id
    session.execute(update(partner_client_requests).where(partner_client_requests.c.id == parsed_id).values(**values))
    if stored_status == "confirmed" and company_id is not None:
        ensure_partner_client_link(
            session,
            partner_user_id=row.partner_user_id,
            bitrix_company_id=company_id,
            created_by_user_id=admin.id,
        )
    audit_event(
        session,
        action="partner_client_status_changed",
        object_type="partner_client_request",
        object_id=str(parsed_id),
        request=request,
        actor_user_id=admin.id,
        bitrix_company_id=company_id,
        metadata={
            "old_status": row.status,
            "new_status": payload.status,
            "partner_id": row.partner_user_id,
            "original_bitrix_company_id": row.original_bitrix_company_id or row.bitrix_check_entity_id,
            "linked_bitrix_company_id": linked_company_id,
            "final_bitrix_company_id": company_id,
        },
    )
    session.commit()
    updated = (
        session.execute(select(partner_client_requests).where(partner_client_requests.c.id == parsed_id))
        .mappings()
        .one()
    )
    return {"client": public_partner_client_request(updated)}
