from __future__ import annotations

from typing import Any

from fastapi import Request, status
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event, now_utc
from app.integrations.bitrix.field_mapping import (
    PARTNER_CLIENT_CHECK_COMPANY_STATUS_ID_TO_PORTAL,
    PARTNER_CLIENT_CHECK_COMPANY_STATUS_VALUES,
)
from app.models import partner_client_links, partner_client_requests
from app.routers.auth import auth_error

REQUEST_ID_PREFIX = "pcr_"
PARTNER_CLIENT_BLOCKING_STATUSES = {"pending", "clarification_required", "rejected", "duplicate_found", "draft"}
PARTNER_CLIENT_LINKED_DECISION = "linked_to_existing"
PARTNER_CLIENT_STATUS_AUDIT_ACTIONS = {
    "confirmed": "partner_client_check_confirmed",
    "rejected": "partner_client_check_rejected",
    "clarification_required": "partner_client_check_clarification_required",
    "duplicate_found": "partner_client_check_duplicate_found",
    PARTNER_CLIENT_LINKED_DECISION: "partner_client_check_linked_to_existing",
}


def portal_status_from_bitrix_partner_client_check(value: str | int | None) -> str | None:
    if value is None:
        return None
    raw_value = str(value).strip()
    if not raw_value:
        return None
    if raw_value in PARTNER_CLIENT_CHECK_COMPANY_STATUS_ID_TO_PORTAL:
        return PARTNER_CLIENT_CHECK_COMPANY_STATUS_ID_TO_PORTAL[raw_value]
    if raw_value in PARTNER_CLIENT_CHECK_COMPANY_STATUS_VALUES:
        return PARTNER_CLIENT_CHECK_COMPANY_STATUS_VALUES[raw_value]
    normalized = raw_value.lower()
    if normalized in {"approved", "approve"}:
        return "confirmed"
    if normalized in {"linked_to_existing", "linked-to-existing", "linked", "duplicate_linked"}:
        return PARTNER_CLIENT_LINKED_DECISION
    if normalized in {"pending", "clarification_required", "confirmed", "duplicate_found", "rejected"}:
        return normalized
    return None


def public_partner_client_status(row) -> str:
    if getattr(row, "linked_to_existing", False) and row.status == "confirmed":
        return PARTNER_CLIENT_LINKED_DECISION
    return row.status


def final_partner_client_company_id(row) -> int | None:
    return row.linked_bitrix_company_id or row.confirmed_bitrix_company_id or row.confirmed_company_id


def parse_partner_client_request_id(value: str | None) -> int | None:
    if value is None:
        return None
    raw_value = value.removeprefix(REQUEST_ID_PREFIX)
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def public_partner_client_request(row) -> dict[str, Any]:
    public_status = public_partner_client_status(row)
    final_company_id = final_partner_client_company_id(row)
    return {
        "id": f"{REQUEST_ID_PREFIX}{row.id}",
        "partner_user_id": f"usr_{row.partner_user_id}",
        "company_name": row.company_name,
        "country": row.country,
        "registration_number": row.registration_number,
        "tax_id": row.tax_id,
        "address": row.address,
        "contact_name": row.contact_name,
        "contact_email": row.contact_email,
        "contact_phone": row.contact_phone,
        "comment": row.comment,
        "status": public_status,
        "bitrix_check_entity_type": row.bitrix_check_entity_type,
        "bitrix_check_entity_id": row.bitrix_check_entity_id,
        "bitrix_check_status": (
            public_status if public_status == PARTNER_CLIENT_LINKED_DECISION else row.bitrix_check_status
        ),
        "bitrix_sync_status": row.bitrix_sync_status,
        "bitrix_sync_error": row.bitrix_sync_error,
        "bitrix_synced_at": row.bitrix_synced_at.isoformat() if row.bitrix_synced_at else None,
        "confirmed_bitrix_company_id": str(final_company_id) if final_company_id else None,
        "linked_to_existing": bool(row.linked_to_existing),
        "decision_status": row.decision_status,
        "rejection_reason": row.rejection_reason if row.status == "rejected" else None,
        "clarification_comment": row.clarification_comment,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def ensure_partner_client_link(
    session: Session,
    *,
    partner_user_id: int,
    bitrix_company_id: int,
    created_by_user_id: int | None = None,
) -> None:
    if bitrix_company_id <= 0:
        return
    existing = session.execute(
        select(partner_client_links.c.id).where(
            partner_client_links.c.partner_user_id == partner_user_id,
            partner_client_links.c.bitrix_company_id == bitrix_company_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        session.execute(
            update(partner_client_links)
            .where(partner_client_links.c.id == existing)
            .values(
                status="active",
                access_status="active",
                confirmed_by_user_id=created_by_user_id,
                confirmed_at=now_utc(),
                revoked_by_user_id=None,
                revoked_at=None,
            )
        )
        return
    session.execute(
        insert(partner_client_links).values(
            partner_user_id=partner_user_id,
            bitrix_company_id=bitrix_company_id,
            status="active",
            access_status="active",
            created_by_user_id=created_by_user_id,
            confirmed_by_user_id=created_by_user_id,
            confirmed_at=now_utc(),
        )
    )


def require_confirmed_partner_client_request(
    session: Session,
    *,
    user,
    request_id_value: str | None,
    bitrix_company_id: int,
    request: Request,
):
    parsed_id = parse_partner_client_request_id(request_id_value)
    if parsed_id is None:
        raise auth_error(status.HTTP_403_FORBIDDEN, "PARTNER_CLIENT_REQUEST_REQUIRED", request)
    row = (
        session.execute(
            select(partner_client_requests).where(
                partner_client_requests.c.id == parsed_id,
                partner_client_requests.c.partner_user_id == user.id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "PARTNER_CLIENT_REQUEST_NOT_FOUND", request)
    final_company_id = final_partner_client_company_id(row)
    is_allowed_status = row.status == "confirmed" and row.bitrix_check_status == "confirmed"
    if not is_allowed_status or final_company_id != bitrix_company_id:
        if row.status == "rejected":
            reason_code = "PARTNER_CLIENT_REJECTED"
        elif row.status == "duplicate_found" and not row.linked_bitrix_company_id:
            reason_code = "PARTNER_CLIENT_DUPLICATE_UNRESOLVED"
        elif row.status in PARTNER_CLIENT_BLOCKING_STATUSES:
            reason_code = "PARTNER_CLIENT_NOT_CONFIRMED"
        else:
            reason_code = "PARTNER_CLIENT_COMPANY_MISMATCH"
        audit_event(
            session,
            action="partner_client_application_create_denied",
            object_type="partner_client_request",
            object_id=str(parsed_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=bitrix_company_id,
            metadata={"status": row.status, "reason_code": reason_code},
        )
        session.commit()
        raise auth_error(status.HTTP_403_FORBIDDEN, reason_code, request)
    ensure_partner_client_link(
        session,
        partner_user_id=user.id,
        bitrix_company_id=final_company_id,
        created_by_user_id=user.id,
    )
    return row
