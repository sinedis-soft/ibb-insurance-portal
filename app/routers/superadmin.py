from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event, now_utc
from app.company_access import CLIENT_COMPANY_ROLES, SYSTEM_BITRIX_COMPANY_IDS, normalize_company_id
from app.db import get_db
from app.models import (
    audit_logs,
    integration_errors,
    partner_client_links,
    portal_users,
    user_company_roles,
    user_sessions,
)
from app.routers.auth import auth_error, get_current_user_from_cookie, parse_public_user_id
from app.routers.company_access import public_company_role, public_partner_client_link

router = APIRouter(prefix="/superadmin", tags=["superadmin"])
DB_SESSION = Depends(get_db)

PORTAL_ROLE_CODES = {"client_executor", "client_admin", "client_viewer", "partner", "superadmin"}
USER_STATUSES = {"pending", "active", "blocked"}
BITRIX_LINK_STATUSES = {"not_checked", "confirmed", "not_found", "mismatch", "bitrix_unavailable"}
ACCESS_STATUSES = {"pending", "active", "revoked", "rejected"}


class RoleUpdatePayload(BaseModel):
    role_code: str | None = None


class CompanyLinkPayload(BaseModel):
    bitrix_company_id: int | str
    role_code: str
    access_status: str = "active"
    bitrix_link_status: str = "confirmed"
    company_title: str | None = Field(default=None, max_length=255)
    company_country_code: str | None = Field(default=None, max_length=16)


class BitrixLinksPayload(BaseModel):
    bitrix_contact_id: int | None = Field(default=None, ge=1)
    company_link_id: int | None = Field(default=None, ge=1)
    bitrix_company_id: int | str | None = None
    bitrix_link_status: str | None = None
    clear_company_link: bool = False


def parse_user_id(value: str) -> int | None:
    parsed = parse_public_user_id(value)
    if parsed is not None:
        return parsed
    try:
        user_id = int(value)
    except ValueError:
        return None
    return user_id if user_id > 0 else None


def parse_link_id(value: str) -> int | None:
    raw_value = value.removeprefix("ucr_")
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def require_superadmin(request: Request, session: Session):
    current_user = get_current_user_from_cookie(request, session)
    if current_user.role_code != "superadmin" or current_user.status != "active":
        raise auth_error(status.HTTP_403_FORBIDDEN, "SUPERADMIN_REQUIRED", request)
    return current_user


def target_user_or_404(session: Session, user_id: str, request: Request):
    parsed_user_id = parse_user_id(user_id)
    if parsed_user_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
    user = session.execute(select(portal_users).where(portal_users.c.id == parsed_user_id)).mappings().one_or_none()
    if user is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
    return user


def public_user_row(row, *, company_links: list[dict[str, Any]] | None = None, error_count: int = 0) -> dict[str, Any]:
    return {
        "id": f"usr_{row.id}",
        "email": row.email,
        "display_name": row.display_name_cache,
        "role_code": row.role_code,
        "roles": [row.role_code] if row.role_code else ([row.user_type] if row.user_type == "partner" else []),
        "user_type": row.user_type,
        "status": row.status,
        "language": row.language,
        "bitrix_contact_id": row.bitrix_contact_id,
        "is_partner": row.user_type == "partner",
        "is_blocked": row.status == "blocked",
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
        "company_links": company_links or [],
        "has_integration_errors": error_count > 0,
        "integration_error_count": error_count,
    }


def company_links_for_users(session: Session, user_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not user_ids:
        return {}
    rows = (
        session.execute(
            select(user_company_roles)
            .where(user_company_roles.c.user_id.in_(user_ids))
            .order_by(user_company_roles.c.created_at.desc())
        )
        .mappings()
        .all()
    )
    grouped: dict[int, list[dict[str, Any]]] = {user_id: [] for user_id in user_ids}
    for row in rows:
        grouped.setdefault(row.user_id, []).append(public_company_role(row))
    return grouped


def integration_error_counts(session: Session, user_ids: list[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    rows = (
        session.execute(
            select(integration_errors.c.object_id, func.count().label("count"))
            .where(
                integration_errors.c.object_type == "user",
                integration_errors.c.object_id.in_([str(user_id) for user_id in user_ids]),
                integration_errors.c.status != "resolved",
            )
            .group_by(integration_errors.c.object_id)
        )
        .mappings()
        .all()
    )
    return {int(row.object_id): int(row.count) for row in rows if str(row.object_id).isdigit()}


def public_audit(row) -> dict[str, Any]:
    return {
        "id": f"audit_{row.id}",
        "action": row.action,
        "object_type": row.object_type,
        "object_id": row.object_id,
        "actor_user_id": f"usr_{row.actor_user_id}" if row.actor_user_id else None,
        "target_user_id": f"usr_{row.target_user_id}" if row.target_user_id else None,
        "bitrix_company_id": row.bitrix_company_id,
        "application_id": f"app_{row.application_id}" if row.application_id else None,
        "bitrix_deal_id": row.bitrix_deal_id,
        "metadata": row.metadata_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def public_integration_error(row) -> dict[str, Any]:
    object_ref = None
    if row.object_type == "user" and row.object_id:
        object_ref = f"/superadmin/users/usr_{row.object_id}"
    elif row.object_type == "application" and row.object_id:
        object_ref = f"/applications/app_{row.object_id}"
    return {
        "id": f"err_{row.id}",
        "object_type": row.object_type,
        "object_id": row.object_id,
        "bitrix_entity_type": row.bitrix_entity_type,
        "bitrix_entity_id": row.bitrix_entity_id,
        "operation": row.operation,
        "status": row.status,
        "error_code": row.error_code,
        "safe_message": row.safe_message,
        "retry_count": row.retry_count,
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "object_url": object_ref,
    }


@router.get("/users")
def list_users(
    request: Request,
    role: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    email: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    has_bitrix_id: bool | None = Query(default=None),
    has_integration_errors: bool | None = Query(default=None),
    session: Session = DB_SESSION,
) -> dict[str, list[dict[str, Any]]]:
    require_superadmin(request, session)
    conditions = []
    if role:
        if role == "partner":
            conditions.append(portal_users.c.user_type == "partner")
        else:
            conditions.append(portal_users.c.role_code == role)
    if status_filter:
        conditions.append(portal_users.c.status == status_filter)
    if email:
        conditions.append(func.lower(portal_users.c.email).like(f"%{email.lower()}%"))
    if has_bitrix_id is not None:
        conditions.append(
            portal_users.c.bitrix_contact_id.is_not(None)
            if has_bitrix_id
            else portal_users.c.bitrix_contact_id.is_(None)
        )
    if company_id is not None:
        conditions.append(
            select(user_company_roles.c.id)
            .where(
                user_company_roles.c.user_id == portal_users.c.id,
                user_company_roles.c.bitrix_company_id == company_id,
            )
            .exists()
        )
    if has_integration_errors is not None:
        error_exists = (
            select(integration_errors.c.id)
            .where(
                integration_errors.c.object_type == "user",
                integration_errors.c.object_id == cast(portal_users.c.id, String),
                integration_errors.c.status != "resolved",
            )
            .exists()
        )
        conditions.append(error_exists if has_integration_errors else ~error_exists)
    rows = session.execute(select(portal_users).where(*conditions).order_by(portal_users.c.id.asc())).mappings().all()
    user_ids = [row.id for row in rows]
    links = company_links_for_users(session, user_ids)
    errors = integration_error_counts(session, user_ids)
    return {
        "items": [
            public_user_row(row, company_links=links.get(row.id), error_count=errors.get(row.id, 0))
            for row in rows
        ]
    }


@router.get("/users/{user_id}")
def get_user_card(user_id: str, request: Request, session: Session = DB_SESSION) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    user = target_user_or_404(session, user_id, request)
    company_rows = (
        session.execute(select(user_company_roles).where(user_company_roles.c.user_id == user.id))
        .mappings()
        .all()
    )
    partner_rows = (
        session.execute(select(partner_client_links).where(partner_client_links.c.partner_user_id == user.id))
        .mappings()
        .all()
    )
    audit_rows = (
        session.execute(
            select(audit_logs)
            .where(or_(audit_logs.c.actor_user_id == user.id, audit_logs.c.target_user_id == user.id))
            .order_by(audit_logs.c.created_at.desc(), audit_logs.c.id.desc())
            .limit(20)
        )
        .mappings()
        .all()
    )
    error_rows = (
        session.execute(
            select(integration_errors)
            .where(integration_errors.c.object_type == "user", integration_errors.c.object_id == str(user.id))
            .order_by(integration_errors.c.created_at.desc())
        )
        .mappings()
        .all()
    )
    audit_event(
        session,
        action="superadmin_user_card_viewed",
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=user.id,
        object_id=str(user.id),
    )
    session.commit()
    return {
        "user": public_user_row(
            user,
            company_links=[public_company_role(row) for row in company_rows],
            error_count=len([row for row in error_rows if row.status != "resolved"]),
        ),
        "company_links": [public_company_role(row) for row in company_rows],
        "partner_client_links": [public_partner_client_link(row) for row in partner_rows],
        "audit_events": [public_audit(row) for row in audit_rows],
        "integration_errors": [public_integration_error(row) for row in error_rows],
    }


@router.patch("/users/{user_id}/roles")
def update_user_role(
    user_id: str,
    payload: RoleUpdatePayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    if payload.role_code is not None and payload.role_code not in PORTAL_ROLE_CODES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "ROLE_NOT_ALLOWED", request)
    new_role = payload.role_code
    if target.id == actor.id and new_role != "superadmin":
        raise auth_error(status.HTTP_403_FORBIDDEN, "LAST_SUPERADMIN_REQUIRED", request)
    if target.role_code == "superadmin" and new_role != "superadmin":
        other_superadmins = session.execute(
            select(func.count())
            .select_from(portal_users)
            .where(
                portal_users.c.id != target.id,
                portal_users.c.role_code == "superadmin",
                portal_users.c.status == "active",
            )
        ).scalar_one()
        if other_superadmins == 0:
            raise auth_error(status.HTTP_403_FORBIDDEN, "LAST_SUPERADMIN_REQUIRED", request)

    values: dict[str, Any] = {"role_code": new_role}
    if new_role == "partner":
        values["user_type"] = "partner"
        values["role_code"] = None
    elif new_role in CLIENT_COMPANY_ROLES or new_role == "superadmin":
        values["user_type"] = "client"
    session.execute(update(portal_users).where(portal_users.c.id == target.id).values(**values))
    session.execute(
        update(user_sessions)
        .where(user_sessions.c.user_id == target.id, user_sessions.c.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )
    audit_event(
        session,
        action="user_role_updated",
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(target.id),
        metadata={"old_role": target.role_code or target.user_type, "new_role": new_role},
    )
    session.commit()
    updated = session.execute(select(portal_users).where(portal_users.c.id == target.id)).mappings().one()
    return {"user": public_user_row(updated), "status": "ok"}


@router.post("/users/{user_id}/company-links", status_code=status.HTTP_201_CREATED)
def create_company_link(
    user_id: str,
    payload: CompanyLinkPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    if target.user_type != "client" or payload.role_code not in CLIENT_COMPANY_ROLES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "ROLE_NOT_ALLOWED", request)
    if payload.access_status not in ACCESS_STATUSES or payload.bitrix_link_status not in BITRIX_LINK_STATUSES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "LINK_STATUS_NOT_ALLOWED", request)
    company_id = normalize_company_id(payload.bitrix_company_id)
    if company_id is None or company_id in SYSTEM_BITRIX_COMPANY_IDS:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "BITRIX_COMPANY_NOT_FOUND", request)
    existing = session.execute(
        select(user_company_roles.c.id).where(
            user_company_roles.c.user_id == target.id,
            user_company_roles.c.bitrix_company_id == company_id,
            user_company_roles.c.role_code == payload.role_code,
            user_company_roles.c.access_status.in_(("pending", "active")),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise auth_error(status.HTTP_409_CONFLICT, "COMPANY_ROLE_ALREADY_EXISTS", request)
    now = now_utc()
    values = {
        "user_id": target.id,
        "bitrix_company_id": company_id,
        "role_code": payload.role_code,
        "access_status": payload.access_status,
        "bitrix_link_status": payload.bitrix_link_status,
        "company_title_cache": payload.company_title,
        "company_country_code_cache": payload.company_country_code.upper() if payload.company_country_code else None,
        "created_by_user_id": actor.id,
    }
    if payload.access_status == "active":
        values["confirmed_by_user_id"] = actor.id
        values["confirmed_at"] = now
    link_id = session.execute(
        insert(user_company_roles).values(**values).returning(user_company_roles.c.id)
    ).scalar_one()
    audit_event(
        session,
        action="superadmin_company_link_created",
        object_type="user_company_role",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(link_id),
        bitrix_company_id=company_id,
        metadata={"role_code": payload.role_code, "access_status": payload.access_status},
    )
    session.commit()
    row = session.execute(select(user_company_roles).where(user_company_roles.c.id == link_id)).mappings().one()
    return {"company_link": public_company_role(row)}


@router.delete("/users/{user_id}/company-links/{link_id}")
def revoke_company_link(user_id: str, link_id: str, request: Request, session: Session = DB_SESSION) -> dict[str, str]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    parsed_link_id = parse_link_id(link_id)
    if parsed_link_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "COMPANY_ROLE_NOT_FOUND", request)
    row = (
        session.execute(
            select(user_company_roles).where(
                user_company_roles.c.id == parsed_link_id,
                user_company_roles.c.user_id == target.id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "COMPANY_ROLE_NOT_FOUND", request)
    if row.access_status != "revoked":
        session.execute(
            update(user_company_roles)
            .where(user_company_roles.c.id == row.id)
            .values(access_status="revoked", revoked_by_user_id=actor.id, revoked_at=now_utc())
        )
        audit_event(
            session,
            action="superadmin_company_link_revoked",
            object_type="user_company_role",
            request=request,
            actor_user_id=actor.id,
            target_user_id=target.id,
            object_id=str(row.id),
            bitrix_company_id=row.bitrix_company_id,
            metadata={"role_code": row.role_code, "old_status": row.access_status, "new_status": "revoked"},
        )
    session.commit()
    return {"status": "ok"}


@router.patch("/users/{user_id}/bitrix-links")
def update_bitrix_links(
    user_id: str,
    payload: BitrixLinksPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    metadata: dict[str, Any] = {"old_bitrix_contact_id": target.bitrix_contact_id}
    if payload.bitrix_contact_id is not None or "bitrix_contact_id" in payload.model_fields_set:
        session.execute(
            update(portal_users)
            .where(portal_users.c.id == target.id)
            .values(bitrix_contact_id=payload.bitrix_contact_id)
        )
        metadata["new_bitrix_contact_id"] = payload.bitrix_contact_id
    if payload.company_link_id is not None:
        row = (
            session.execute(
                select(user_company_roles).where(
                    user_company_roles.c.id == payload.company_link_id,
                    user_company_roles.c.user_id == target.id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise auth_error(status.HTTP_404_NOT_FOUND, "COMPANY_ROLE_NOT_FOUND", request)
        update_values: dict[str, Any] = {}
        if payload.clear_company_link:
            update_values["bitrix_link_status"] = "not_checked"
            metadata["company_link_cleared"] = True
        if payload.bitrix_company_id is not None:
            company_id = normalize_company_id(payload.bitrix_company_id)
            if company_id is None or company_id in SYSTEM_BITRIX_COMPANY_IDS:
                raise auth_error(status.HTTP_400_BAD_REQUEST, "BITRIX_COMPANY_NOT_FOUND", request)
            update_values["bitrix_company_id"] = company_id
            metadata["old_bitrix_company_id"] = row.bitrix_company_id
            metadata["new_bitrix_company_id"] = company_id
        if payload.bitrix_link_status is not None:
            if payload.bitrix_link_status not in BITRIX_LINK_STATUSES:
                raise auth_error(status.HTTP_400_BAD_REQUEST, "LINK_STATUS_NOT_ALLOWED", request)
            update_values["bitrix_link_status"] = payload.bitrix_link_status
        if update_values:
            session.execute(update(user_company_roles).where(user_company_roles.c.id == row.id).values(**update_values))
    audit_event(
        session,
        action="superadmin_bitrix_links_updated",
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(target.id),
        metadata=metadata,
    )
    session.commit()
    updated = session.execute(select(portal_users).where(portal_users.c.id == target.id)).mappings().one()
    return {"user": public_user_row(updated), "status": "ok"}


@router.get("/integration-errors")
def list_integration_errors(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    object_type: str | None = Query(default=None),
    session: Session = DB_SESSION,
) -> dict[str, list[dict[str, Any]]]:
    require_superadmin(request, session)
    conditions = []
    if status_filter:
        conditions.append(integration_errors.c.status == status_filter)
    if object_type:
        conditions.append(integration_errors.c.object_type == object_type)
    rows = (
        session.execute(select(integration_errors).where(*conditions).order_by(integration_errors.c.created_at.desc()))
        .mappings()
        .all()
    )
    return {"items": [public_integration_error(row) for row in rows]}


@router.get("/integration-errors/{error_id}")
def get_integration_error(error_id: str, request: Request, session: Session = DB_SESSION) -> dict[str, Any]:
    require_superadmin(request, session)
    parsed_error_id = error_id.removeprefix("err_")
    if not parsed_error_id.isdigit():
        raise auth_error(status.HTTP_404_NOT_FOUND, "INTEGRATION_ERROR_NOT_FOUND", request)
    row = (
        session.execute(select(integration_errors).where(integration_errors.c.id == int(parsed_error_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "INTEGRATION_ERROR_NOT_FOUND", request)
    return {"error": public_integration_error(row)}


@router.post("/integration-errors/{error_id}/mark-resolved")
def mark_integration_error_resolved(
    error_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, str]:
    actor = require_superadmin(request, session)
    parsed_error_id = error_id.removeprefix("err_")
    if not parsed_error_id.isdigit():
        raise auth_error(status.HTTP_404_NOT_FOUND, "INTEGRATION_ERROR_NOT_FOUND", request)
    row = (
        session.execute(select(integration_errors).where(integration_errors.c.id == int(parsed_error_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "INTEGRATION_ERROR_NOT_FOUND", request)
    if row.status != "resolved":
        session.execute(
            update(integration_errors)
            .where(integration_errors.c.id == row.id)
            .values(status="resolved", resolved_at=now_utc())
        )
        audit_event(
            session,
            action="integration_error_resolved",
            object_type="integration_error",
            request=request,
            actor_user_id=actor.id,
            object_id=str(row.id),
            metadata={"old_status": row.status, "new_status": "resolved", "error_code": row.error_code},
        )
    session.commit()
    return {"status": "ok"}
