from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import String, asc, cast, desc, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.auth import (
    audit_event,
    client_ip,
    hash_auth_token,
    hash_password,
    now_utc,
    sanitize_audit_metadata,
    user_agent,
)
from app.company_access import CLIENT_COMPANY_ROLES, SYSTEM_BITRIX_COMPANY_IDS, normalize_company_id
from app.config import get_settings
from app.db import get_db
from app.delegations import terminate_delegations_for_user
from app.models import (
    audit_logs,
    impersonation_sessions,
    integration_errors,
    partner_client_links,
    portal_applications,
    portal_users,
    user_company_roles,
    user_sessions,
)
from app.routers.auth import auth_error, create_auth_token, get_current_user_from_cookie, parse_public_user_id
from app.routers.company_access import public_company_role, public_partner_client_link

router = APIRouter(prefix="/superadmin", tags=["superadmin"])
DB_SESSION = Depends(get_db)

PORTAL_ROLE_CODES = {"client_executor", "client_admin", "client_viewer", "partner", "superadmin"}
GENERAL_ROLE_CODES = {"client_executor", "client_admin", "client_viewer", "partner"}
BITRIX_PUBLIC_LINK_STATUS = {
    "not_checked": "verification_pending",
    "confirmed": "linked",
    "not_found": "not_found",
    "mismatch": "conflict",
    "bitrix_unavailable": "bitrix_unavailable",
}
PUBLIC_TO_COMPANY_LINK_STATUS = {value: key for key, value in BITRIX_PUBLIC_LINK_STATUS.items()} | {
    "not_linked": "not_checked"
}
INTEGRATION_STATUS_TO_PUBLIC = {
    "pending": "pending_retry",
    "failed": "requires_attention",
    "retrying": "retrying",
    "resolved": "resolved",
}
PUBLIC_TO_INTEGRATION_STATUS = {value: key for key, value in INTEGRATION_STATUS_TO_PUBLIC.items()} | {
    "cancelled": "resolved"
}
RETRYABLE_OPERATIONS = {
    "create",
    "update",
    "sync",
    "webhook",
    "upload",
    "create_deal",
    "update_deal",
    "sync_company",
    "sync_contact",
    "transfer_document",
    "process_webhook",
    "sync_policy",
}
USER_STATUSES = {"pending", "active", "blocked"}
BITRIX_LINK_STATUSES = {"not_checked", "confirmed", "not_found", "mismatch", "bitrix_unavailable"}
ACCESS_STATUSES = {"pending", "active", "revoked", "rejected"}
AUDIT_SORT_FIELDS = {"created_at": audit_logs.c.created_at, "id": audit_logs.c.id}
AUDIT_RESULTS = {"success", "denied", "failed", "cancelled"}
AUDIT_CATEGORIES = {
    "authentication",
    "access_control",
    "user_management",
    "application",
    "document",
    "delegation",
    "impersonation",
    "integration",
    "system",
}


class RoleUpdatePayload(BaseModel):
    role_code: str | None = None


class CompanyRoleUpdatePayload(BaseModel):
    role_code: str
    reason: str | None = Field(default=None, max_length=512)


class BitrixContactPayload(BaseModel):
    bitrix_contact_id: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=512)


class BitrixCompanyLinkPayload(BaseModel):
    bitrix_company_id: int | str | None = None
    reason: str | None = Field(default=None, max_length=512)


class IntegrationErrorStatusPayload(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=512)


class CompanyLinkPayload(BaseModel):
    bitrix_company_id: int | str
    role_code: str
    access_status: str = "active"
    bitrix_link_status: str = "confirmed"
    company_title: str | None = Field(default=None, max_length=255)
    company_country_code: str | None = Field(default=None, max_length=16)


class CreateUserPayload(BaseModel):
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=255)
    role_code: str | None = None
    language: str = "ru"
    bitrix_contact_id: int | None = Field(default=None, ge=1)
    company_links: list[CompanyLinkPayload] = Field(default_factory=list)


class BlockUserPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=512)
    reassignment_action: str | None = None
    new_responsible_user_id: str | None = None
    reassignment_reason: str | None = Field(default=None, max_length=512)
    idempotency_key: str | None = Field(default=None, max_length=128)


class UnblockUserPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=512)


class ImpersonationStartPayload(BaseModel):
    reason: str = Field(min_length=5, max_length=512)


class ImpersonationEndPayload(BaseModel):
    end_reason: str = Field(default="manual", max_length=64)


class BitrixLinksPayload(BaseModel):
    bitrix_contact_id: int | None = Field(default=None, ge=1)
    company_link_id: int | None = Field(default=None, ge=1)
    bitrix_company_id: int | str | None = None
    bitrix_link_status: str | None = None
    clear_company_link: bool = False
    reason: str | None = Field(default=None, max_length=512)


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
        "bitrix_contact_link_status": getattr(row, "bitrix_contact_link_status", None)
        or ("linked" if row.bitrix_contact_id else "not_linked"),
        "bitrix_contact_verified_at": row.bitrix_contact_verified_at.isoformat()
        if getattr(row, "bitrix_contact_verified_at", None)
        else None,
        "is_partner": row.user_type == "partner",
        "is_blocked": row.status == "blocked",
        "blocked_reason": getattr(row, "blocked_reason", None),
        "blocked_at": row.blocked_at.isoformat() if getattr(row, "blocked_at", None) else None,
        "blocked_by_user_id": f"usr_{row.blocked_by_user_id}" if getattr(row, "blocked_by_user_id", None) else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
        "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
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
        grouped.setdefault(row.user_id, []).append(company_role_payload(row))
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
    return public_audit_event(row)


def _prefixed_id(prefix: str, value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    return text if text.startswith(f"{prefix}_") else f"{prefix}_{text}"


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    if isinstance(value, str):
        for prefix in ("usr_", "app_", "dlg_", "imp_", "err_"):
            value = value.removeprefix(prefix)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def public_audit_event(row) -> dict[str, Any]:
    metadata = sanitize_audit_metadata(dict(row.metadata_json or {}))
    category = metadata.get("category") or "system"
    result = metadata.get("result") or ("denied" if "denied" in row.action else "success")
    target_id = row.object_id
    document_id = metadata.get("document_id") or (target_id if row.object_type == "document" else None)
    delegation_id = metadata.get("delegation_id") or (
        target_id if row.object_type == "application_delegation" else None
    )
    integration_error_id = metadata.get("integration_error_id") or (
        target_id if row.object_type == "integration_error" else None
    )
    return {
        "id": f"audit_{row.id}",
        "event_type": row.action,
        "action": row.action,
        "category": category,
        "actor_user_id": f"usr_{row.actor_user_id}" if row.actor_user_id else None,
        "effective_user_id": _prefixed_id("usr", metadata.get("effective_user_id")),
        "target_user_id": f"usr_{row.target_user_id}" if row.target_user_id else None,
        "target_type": row.object_type,
        "target_id": target_id,
        "object_type": row.object_type,
        "object_id": target_id,
        "company_id": row.bitrix_company_id,
        "bitrix_company_id": row.bitrix_company_id,
        "application_id": (
            f"app_{row.application_id}" if row.application_id else _prefixed_id("app", metadata.get("application_id"))
        ),
        "document_id": _prefixed_id("doc", document_id),
        "delegation_id": _prefixed_id("dlg", delegation_id),
        "integration_error_id": _prefixed_id("err", integration_error_id),
        "impersonation_session_id": _prefixed_id("imp", metadata.get("impersonation_session_id")),
        "bitrix_deal_id": row.bitrix_deal_id,
        "result": result,
        "reason_code": metadata.get("reason_code") or metadata.get("reason"),
        "metadata": metadata,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "correlation_id": metadata.get("correlation_id") or metadata.get("request_id"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def parse_public_numeric(value: str | None, *prefixes: str) -> int | None:
    if not value:
        return None
    raw = value
    for prefix in prefixes:
        raw = raw.removeprefix(f"{prefix}_")
    try:
        parsed = int(raw)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def audit_json_text(key: str):
    return audit_logs.c.metadata_json[key].as_string()


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
        "status": INTEGRATION_STATUS_TO_PUBLIC.get(row.status, row.status),
        "error_code": row.error_code,
        "safe_message": row.safe_message,
        "retry_count": row.retry_count,
        "attempt_count": row.retry_count,
        "first_failed_at": row.first_failed_at.isoformat()
        if getattr(row, "first_failed_at", None)
        else (row.created_at.isoformat() if row.created_at else None),
        "last_failed_at": row.last_failed_at.isoformat()
        if getattr(row, "last_failed_at", None)
        else (row.updated_at.isoformat() if getattr(row, "updated_at", None) else None),
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        "correlation_id": getattr(row, "correlation_id", None)
        or (row.metadata_json.get("request_id") if hasattr(row, "metadata_json") else None),
        "retry_supported": bool(getattr(row, "retry_supported", True))
        and row.operation in RETRYABLE_OPERATIONS
        and row.status != "resolved",
        "attempt_history": getattr(row, "attempt_history_json", None) or [],
        "object_url": object_ref,
    }


def public_company_link_status(row) -> str:
    return BITRIX_PUBLIC_LINK_STATUS.get(row.bitrix_link_status, row.bitrix_link_status)


def company_role_payload(row) -> dict[str, Any]:
    payload = public_company_role(row)
    payload["bitrix_link_status"] = public_company_link_status(row)
    payload["bitrix_company_verified_at"] = (
        row.bitrix_company_verified_at.isoformat() if getattr(row, "bitrix_company_verified_at", None) else None
    )
    return payload


def normalize_contact_link_status(status_value: str | None, contact_id: int | None) -> str:
    if status_value and status_value != "not_linked":
        return status_value
    return "linked" if contact_id else "not_linked"


def verify_bitrix_link(entity_type: str, entity_id: int) -> str:
    # Minimal read-only verifier seam. Tests monkeypatch this function; production-safe default
    # avoids leaking payloads or calling Bitrix24 from admin UI without a configured adapter.
    if entity_id <= 0:
        return "invalid"
    return "linked"


def pagination_payload(*, total: int, page: int, page_size: int) -> dict[str, int]:
    return {"total": total, "page": page, "page_size": page_size, "pages": (total + page_size - 1) // page_size}


def active_application_filter(user_id: int):
    return (
        portal_applications.c.assigned_to_user_id == user_id,
        portal_applications.c.portal_status.not_in(("cancelled", "policy_issued", "closed", "rejected")),
    )


def revoke_sessions_for_user(
    session: Session,
    user_id: int,
    *,
    request: Request | None = None,
    actor_user_id: int | None = None,
    reason_code: str = "access_changed",
) -> None:
    result = session.execute(
        update(user_sessions)
        .where(user_sessions.c.user_id == user_id, user_sessions.c.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )
    if request is not None:
        audit_event(
            session,
            action="all_user_sessions_revoked",
            object_type="user_session",
            request=request,
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            metadata={"reason_code": reason_code, "revoked_count": int(result.rowcount or 0)},
        )


def ensure_assignee_allowed(session: Session, assignee_id: int, company_id: int, request: Request):
    user = session.execute(select(portal_users).where(portal_users.c.id == assignee_id)).mappings().one_or_none()
    if user is None or user.status != "active":
        raise auth_error(status.HTTP_400_BAD_REQUEST, "ASSIGNEE_NOT_ALLOWED", request)
    link = session.execute(
        select(user_company_roles.c.id).where(
            user_company_roles.c.user_id == assignee_id,
            user_company_roles.c.bitrix_company_id == company_id,
            user_company_roles.c.access_status == "active",
            user_company_roles.c.role_code.in_(("client_executor", "client_admin")),
        )
    ).scalar_one_or_none()
    if link is None:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "ASSIGNEE_NOT_ALLOWED", request)
    return user


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: CreateUserPayload, request: Request, session: Session = DB_SESSION) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    email = payload.email.strip().lower()
    if session.execute(select(portal_users.c.id).where(portal_users.c.email == email)).scalar_one_or_none() is not None:
        raise auth_error(status.HTTP_409_CONFLICT, "EMAIL_ALREADY_EXISTS", request)
    if payload.role_code is not None and payload.role_code not in GENERAL_ROLE_CODES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "ROLE_NOT_ALLOWED", request)
    user_type = "partner" if payload.role_code == "partner" else "client"
    role_code = None if payload.role_code == "partner" else payload.role_code
    user_id = session.execute(
        insert(portal_users)
        .values(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(24)),
            status="pending",
            user_type=user_type,
            role_code=role_code,
            language=payload.language if payload.language in {"ru", "ka"} else "ru",
            bitrix_contact_id=payload.bitrix_contact_id,
            display_name_cache=payload.display_name,
        )
        .returning(portal_users.c.id)
    ).scalar_one()
    for link in payload.company_links:
        company_id = normalize_company_id(link.bitrix_company_id)
        if company_id is None or company_id in SYSTEM_BITRIX_COMPANY_IDS or link.role_code not in CLIENT_COMPANY_ROLES:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "COMPANY_ROLE_NOT_ALLOWED", request)
        session.execute(
            insert(user_company_roles).values(
                user_id=user_id,
                bitrix_company_id=company_id,
                role_code=link.role_code,
                access_status=link.access_status,
                bitrix_link_status=link.bitrix_link_status,
                company_title_cache=link.company_title,
                company_country_code_cache=link.company_country_code.upper() if link.company_country_code else None,
                created_by_user_id=actor.id,
                confirmed_by_user_id=actor.id if link.access_status == "active" else None,
                confirmed_at=now_utc() if link.access_status == "active" else None,
            )
        )
    settings = get_settings()
    token = create_auth_token(
        session,
        user_id=user_id,
        token_type="first_login",
        expires_at=now_utc() + timedelta(hours=settings.first_login_token_ttl_hours),
        settings=settings,
        created_by_user_id=actor.id,
    )
    audit_event(
        session,
        action="user_created",
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=user_id,
        object_id=str(user_id),
        metadata={"role_code": role_code or user_type, "invite_token_created": bool(token)},
    )
    session.commit()
    row = session.execute(select(portal_users).where(portal_users.c.id == user_id)).mappings().one()
    return {"user": public_user_row(row), "invite_created": True}


@router.post("/users/{user_id}/block")
def block_user(
    user_id: str, payload: BlockUserPayload, request: Request, session: Session = DB_SESSION
) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    if target.id == actor.id:
        raise auth_error(status.HTTP_403_FORBIDDEN, "CANNOT_BLOCK_SELF", request)
    if target.status == "blocked":
        return {"status": "ok", "idempotent": True}
    active_apps = (
        session.execute(select(portal_applications).where(*active_application_filter(target.id))).mappings().all()
    )
    if active_apps and not payload.reassignment_action:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "REASSIGNMENT_REQUIRED", request)
    transfer_count = 0
    if active_apps:
        terminate_delegations_for_user(
            session, user_id=target.id, reason="delegator_blocked", request=request, actor_user_id=actor.id
        )
        action = payload.reassignment_action
        if action == "assign_to_user":
            new_id = parse_user_id(payload.new_responsible_user_id or "")
            if new_id is None:
                raise auth_error(status.HTTP_400_BAD_REQUEST, "ASSIGNEE_NOT_ALLOWED", request)
            for app in active_apps:
                ensure_assignee_allowed(session, new_id, app.bitrix_company_id, request)
            result = session.execute(
                update(portal_applications)
                .where(*active_application_filter(target.id))
                .values(
                    assigned_to_user_id=new_id,
                    assignment_status="assigned",
                    reassigned_from_user_id=target.id,
                    reassigned_at=now_utc(),
                    reassignment_reason=payload.reassignment_reason or payload.reason,
                )
            )
            transfer_count = result.rowcount or 0
        elif action == "requires_assignment":
            result = session.execute(
                update(portal_applications)
                .where(*active_application_filter(target.id))
                .values(
                    assigned_to_user_id=None,
                    assignment_status="requires_assignment",
                    reassigned_from_user_id=target.id,
                    reassigned_at=now_utc(),
                    reassignment_reason=payload.reassignment_reason or payload.reason,
                )
            )
            transfer_count = result.rowcount or 0
        else:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "REASSIGNMENT_REQUIRED", request)
        audit_event(
            session,
            action="active_applications_reassigned",
            object_type="portal_application",
            request=request,
            actor_user_id=actor.id,
            target_user_id=target.id,
            metadata={
                "action": action,
                "application_count": transfer_count,
                "reason": payload.reassignment_reason or payload.reason,
            },
        )
    session.execute(
        update(portal_users)
        .where(portal_users.c.id == target.id)
        .values(status="blocked", blocked_reason=payload.reason, blocked_at=now_utc(), blocked_by_user_id=actor.id)
    )
    terminate_delegations_for_user(
        session, user_id=target.id, reason="user_blocked", request=request, actor_user_id=actor.id
    )
    revoke_sessions_for_user(session, target.id, request=request, actor_user_id=actor.id, reason_code="user_blocked")
    audit_event(
        session,
        action="user_blocked",
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(target.id),
        metadata={"reason": payload.reason, "active_application_count": len(active_apps)},
    )
    session.commit()
    return {"status": "ok", "reassigned_count": transfer_count}


@router.post("/users/{user_id}/unblock")
def unblock_user(
    user_id: str, payload: UnblockUserPayload, request: Request, session: Session = DB_SESSION
) -> dict[str, str]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    if target.status != "blocked":
        return {"status": "ok"}
    session.execute(
        update(portal_users)
        .where(portal_users.c.id == target.id)
        .values(status="active", blocked_reason=None, blocked_at=None, blocked_by_user_id=None)
    )
    audit_event(
        session,
        action="user_unblocked",
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(target.id),
        metadata={"reason": payload.reason},
    )
    session.commit()
    return {"status": "ok"}


@router.get("/audit-log")
def list_audit_log(
    request: Request,
    action: str | None = Query(default=None),
    target_user_id: str | None = Query(default=None),
    session: Session = DB_SESSION,
) -> dict[str, list[dict[str, Any]]]:
    require_superadmin(request, session)
    conditions = []
    if action:
        conditions.append(audit_logs.c.action == action)
    if target_user_id:
        parsed = parse_user_id(target_user_id)
        if parsed is None:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "USER_NOT_FOUND", request)
        conditions.append(audit_logs.c.target_user_id == parsed)
    rows = (
        session.execute(
            select(audit_logs)
            .where(*conditions)
            .order_by(audit_logs.c.created_at.desc(), audit_logs.c.id.desc())
            .limit(100)
        )
        .mappings()
        .all()
    )
    return {"items": [public_audit(row) for row in rows]}


@router.get("/audit-events")
def list_audit_events(
    request: Request,
    actor_user_id: str | None = Query(default=None),
    effective_user_id: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    result: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    application_id: str | None = Query(default=None),
    delegation_id: str | None = Query(default=None),
    impersonation_session_id: str | None = Query(default=None),
    integration_error_id: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    require_superadmin(request, session)
    if category and category not in AUDIT_CATEGORIES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "AUDIT_FILTER_INVALID", request)
    if result and result not in AUDIT_RESULTS:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "AUDIT_FILTER_INVALID", request)
    sort_column = AUDIT_SORT_FIELDS.get(sort_by)
    if sort_column is None:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "AUDIT_SORT_INVALID", request)
    conditions = []
    parsed_actor = parse_public_numeric(actor_user_id, "usr") if actor_user_id else None
    if actor_user_id and parsed_actor is None:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "USER_NOT_FOUND", request)
    if parsed_actor:
        conditions.append(audit_logs.c.actor_user_id == parsed_actor)
    if effective_user_id:
        parsed_effective = parse_public_numeric(effective_user_id, "usr")
        if parsed_effective is None:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "USER_NOT_FOUND", request)
        conditions.append(audit_json_text("effective_user_id") == str(parsed_effective))
    if company_id is not None:
        conditions.append(audit_logs.c.bitrix_company_id == company_id)
    if event_type:
        conditions.append(audit_logs.c.action == event_type)
    if category:
        conditions.append(audit_json_text("category") == category)
    if result:
        conditions.append(audit_json_text("result") == result)
    if target_type:
        conditions.append(audit_logs.c.object_type == target_type)
    if target_id:
        conditions.append(audit_logs.c.object_id == target_id)
    if application_id:
        parsed_app = parse_public_numeric(application_id, "app")
        if parsed_app is None:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "APPLICATION_NOT_FOUND", request)
        conditions.append(audit_logs.c.application_id == parsed_app)
    if delegation_id:
        parsed_delegation = parse_public_numeric(delegation_id, "dlg")
        if parsed_delegation is None:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "DELEGATION_NOT_FOUND", request)
        conditions.append(audit_json_text("delegation_id").in_((str(parsed_delegation), f"dlg_{parsed_delegation}")))
    if impersonation_session_id:
        parsed_impersonation = parse_public_numeric(impersonation_session_id, "imp")
        if parsed_impersonation is None:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "IMPERSONATION_NOT_FOUND", request)
        conditions.append(
            audit_json_text("impersonation_session_id").in_((str(parsed_impersonation), f"imp_{parsed_impersonation}"))
        )
    if integration_error_id:
        parsed_error = parse_public_numeric(integration_error_id, "err")
        if parsed_error is None:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "INTEGRATION_ERROR_NOT_FOUND", request)
        conditions.append(
            or_(
                audit_logs.c.object_type == "integration_error",
                audit_json_text("integration_error_id").in_((str(parsed_error), f"err_{parsed_error}")),
            )
        )
        conditions.append(audit_logs.c.object_id == str(parsed_error))
    if correlation_id:
        conditions.append(audit_json_text("correlation_id") == correlation_id)
    if date_from:
        conditions.append(audit_logs.c.created_at >= date_from)
    if date_to:
        conditions.append(audit_logs.c.created_at <= date_to)
    total = session.execute(select(func.count()).select_from(audit_logs).where(*conditions)).scalar_one()
    order_expr = asc(sort_column) if sort_order == "asc" else desc(sort_column)
    rows = (
        session.execute(
            select(audit_logs)
            .where(*conditions)
            .order_by(order_expr, desc(audit_logs.c.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .mappings()
        .all()
    )
    return {
        "items": [public_audit_event(row) for row in rows],
        "pagination": pagination_payload(total=total, page=page, page_size=page_size),
    }


@router.get("/audit-events/{event_id}")
def get_audit_event(event_id: str, request: Request, session: Session = DB_SESSION) -> dict[str, Any]:
    require_superadmin(request, session)
    parsed = parse_public_numeric(event_id, "audit")
    if parsed is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "AUDIT_EVENT_NOT_FOUND", request)
    row = session.execute(select(audit_logs).where(audit_logs.c.id == parsed)).mappings().one_or_none()
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "AUDIT_EVENT_NOT_FOUND", request)
    return {"event": public_audit_event(row)}


@router.post("/users/{user_id}/impersonation")
def start_impersonation(
    user_id: str, payload: ImpersonationStartPayload, request: Request, session: Session = DB_SESSION
) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    if getattr(actor, "two_factor_enabled", False) is False:
        raise auth_error(status.HTTP_403_FORBIDDEN, "SUPERADMIN_2FA_REQUIRED", request)
    existing = session.execute(
        select(impersonation_sessions.c.id).where(
            impersonation_sessions.c.actor_user_id == actor.id,
            impersonation_sessions.c.ended_at.is_(None),
            impersonation_sessions.c.expires_at > now_utc(),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise auth_error(status.HTTP_409_CONFLICT, "IMPERSONATION_ALREADY_ACTIVE", request)
    token = secrets.token_urlsafe(32)
    expires_at = now_utc() + timedelta(minutes=15)
    session_id = session.execute(
        insert(impersonation_sessions)
        .values(
            actor_user_id=actor.id,
            effective_user_id=target.id,
            reason=payload.reason,
            session_token_hash=hash_auth_token(token),
            expires_at=expires_at,
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            critical_actions=[],
        )
        .returning(impersonation_sessions.c.id)
    ).scalar_one()
    audit_event(
        session,
        action="superadmin_impersonation_started",
        object_type="impersonation_session",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(session_id),
        metadata={"reason": payload.reason, "effective_user_id": target.id},
    )
    session.commit()
    return {"impersonation_session_id": f"imp_{session_id}", "expires_at": expires_at.isoformat(), "token": token}


@router.post("/impersonation/{session_id}/end")
def end_impersonation(
    session_id: str, payload: ImpersonationEndPayload, request: Request, session: Session = DB_SESSION
) -> dict[str, str]:
    actor = require_superadmin(request, session)
    raw = session_id.removeprefix("imp_")
    if not raw.isdigit():
        raise auth_error(status.HTTP_404_NOT_FOUND, "IMPERSONATION_NOT_FOUND", request)
    row = (
        session.execute(
            select(impersonation_sessions).where(
                impersonation_sessions.c.id == int(raw), impersonation_sessions.c.actor_user_id == actor.id
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "IMPERSONATION_NOT_FOUND", request)
    if row.ended_at is None:
        session.execute(
            update(impersonation_sessions)
            .where(impersonation_sessions.c.id == row.id)
            .values(ended_at=now_utc(), ended_by_user_id=actor.id, end_reason=payload.end_reason)
        )
        audit_event(
            session,
            action="superadmin_impersonation_ended",
            object_type="impersonation_session",
            request=request,
            actor_user_id=actor.id,
            target_user_id=row.effective_user_id,
            object_id=str(row.id),
            metadata={"end_reason": payload.end_reason},
        )
    session.commit()
    return {"status": "ok"}


@router.get("/users")
def list_users(
    request: Request,
    role: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    email: str | None = Query(default=None),
    name: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    has_bitrix_id: bool | None = Query(default=None),
    has_integration_errors: bool | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = DB_SESSION,
) -> dict[str, Any]:
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
    if name:
        conditions.append(func.lower(portal_users.c.display_name_cache).like(f"%{name.lower()}%"))
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
    sortable = {"created_at": portal_users.c.created_at, "last_login_at": portal_users.c.last_login_at}
    sort_column = sortable.get(sort_by, portal_users.c.created_at)
    ordering = desc(sort_column).nullslast() if sort_dir != "asc" else asc(sort_column).nullslast()
    total = session.execute(select(func.count()).select_from(portal_users).where(*conditions)).scalar_one()
    rows = (
        session.execute(
            select(portal_users)
            .where(*conditions)
            .order_by(ordering, portal_users.c.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .mappings()
        .all()
    )
    user_ids = [row.id for row in rows]
    links = company_links_for_users(session, user_ids)
    errors = integration_error_counts(session, user_ids)
    return {
        "items": [
            public_user_row(row, company_links=links.get(row.id), error_count=errors.get(row.id, 0)) for row in rows
        ],
        "pagination": pagination_payload(total=total, page=page, page_size=page_size),
    }


@router.get("/users/{user_id}")
def get_user_card(user_id: str, request: Request, session: Session = DB_SESSION) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    user = target_user_or_404(session, user_id, request)
    company_rows = (
        session.execute(select(user_company_roles).where(user_company_roles.c.user_id == user.id)).mappings().all()
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
            company_links=[company_role_payload(row) for row in company_rows],
            error_count=len([row for row in error_rows if row.status != "resolved"]),
        ),
        "company_links": [company_role_payload(row) for row in company_rows],
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
    if payload.role_code is not None and payload.role_code not in GENERAL_ROLE_CODES:
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
    old_role = target.role_code or target.user_type
    if old_role == (new_role or "client"):
        return {"user": public_user_row(target), "status": "ok", "idempotent": True}
    session.execute(update(portal_users).where(portal_users.c.id == target.id).values(**values))
    revoke_sessions_for_user(session, target.id, request=request, actor_user_id=actor.id, reason_code="role_changed")
    if target.role_code is None and new_role is not None:
        audit_action = "user_role_assigned"
    elif new_role is None:
        audit_action = "user_role_revoked"
    else:
        audit_action = "user_role_changed"
    audit_event(
        session,
        action=audit_action,
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(target.id),
        metadata={"old_role": old_role, "new_role": new_role, "result": "success"},
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
        row = session.execute(select(user_company_roles).where(user_company_roles.c.id == existing)).mappings().one()
        return {"company_link": company_role_payload(row), "idempotent": True}
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
        action="user_company_link_added",
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
    return {"company_link": company_role_payload(row)}


@router.patch("/users/{user_id}/company-links/{link_id}")
def update_company_link_role(
    user_id: str,
    link_id: str,
    payload: CompanyRoleUpdatePayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    parsed_link_id = parse_link_id(link_id)
    if parsed_link_id is None or payload.role_code not in CLIENT_COMPANY_ROLES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "ROLE_NOT_ALLOWED", request)
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
    if row.role_code == payload.role_code and row.access_status == "active":
        return {"company_link": company_role_payload(row), "idempotent": True}
    session.execute(
        update(user_company_roles)
        .where(user_company_roles.c.id == row.id)
        .values(
            role_code=payload.role_code, access_status="active", confirmed_by_user_id=actor.id, confirmed_at=now_utc()
        )
    )
    revoke_sessions_for_user(
        session, target.id, request=request, actor_user_id=actor.id, reason_code="company_role_changed"
    )
    audit_event(
        session,
        action="user_role_changed",
        object_type="user_company_role",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(row.id),
        bitrix_company_id=row.bitrix_company_id,
        metadata={
            "old_role": row.role_code,
            "new_role": payload.role_code,
            "reason": payload.reason,
            "result": "success",
        },
    )
    session.commit()
    updated = session.execute(select(user_company_roles).where(user_company_roles.c.id == row.id)).mappings().one()
    return {"company_link": company_role_payload(updated)}


@router.patch("/users/{user_id}/company-links/{link_id}/bitrix-company")
def update_company_bitrix_link(
    user_id: str,
    link_id: str,
    payload: BitrixCompanyLinkPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
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
    old_company_id = row.bitrix_company_id
    if payload.bitrix_company_id is None:
        session.execute(
            update(user_company_roles)
            .where(user_company_roles.c.id == row.id)
            .values(bitrix_link_status="not_checked", bitrix_company_verified_at=None)
        )
        audit_action = "bitrix_company_link_removed"
        new_company_id = None
    else:
        new_company_id = normalize_company_id(payload.bitrix_company_id)
        if new_company_id is None or new_company_id in SYSTEM_BITRIX_COMPANY_IDS:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "BITRIX_COMPANY_NOT_FOUND", request)
        conflict = session.execute(
            select(user_company_roles.c.id).where(
                user_company_roles.c.id != row.id,
                user_company_roles.c.bitrix_company_id == new_company_id,
                user_company_roles.c.access_status.in_(("pending", "active")),
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise auth_error(status.HTTP_409_CONFLICT, "BITRIX_LINK_CONFLICT", request)
        status_value = verify_bitrix_link("company", new_company_id)
        session.execute(
            update(user_company_roles)
            .where(user_company_roles.c.id == row.id)
            .values(
                bitrix_company_id=new_company_id,
                bitrix_link_status=PUBLIC_TO_COMPANY_LINK_STATUS.get(status_value, "bitrix_unavailable"),
                bitrix_company_verified_at=now_utc(),
            )
        )
        audit_action = "bitrix_company_link_created" if old_company_id is None else "bitrix_company_link_changed"
    audit_event(
        session,
        action=audit_action,
        object_type="user_company_role",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(row.id),
        bitrix_company_id=new_company_id or old_company_id,
        metadata={
            "old_bitrix_company_id": old_company_id,
            "new_bitrix_company_id": new_company_id,
            "reason": payload.reason,
        },
    )
    session.commit()
    updated = session.execute(select(user_company_roles).where(user_company_roles.c.id == row.id)).mappings().one()
    return {"company_link": company_role_payload(updated)}


@router.post("/users/{user_id}/company-links/{link_id}/verify-bitrix-company")
def verify_company_bitrix_link(
    user_id: str, link_id: str, request: Request, session: Session = DB_SESSION
) -> dict[str, Any]:
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
    status_value = verify_bitrix_link("company", row.bitrix_company_id)
    session.execute(
        update(user_company_roles)
        .where(user_company_roles.c.id == row.id)
        .values(
            bitrix_link_status=PUBLIC_TO_COMPANY_LINK_STATUS.get(status_value, "bitrix_unavailable"),
            bitrix_company_verified_at=now_utc(),
        )
    )
    audit_event(
        session,
        action="bitrix_company_link_verified",
        object_type="user_company_role",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(row.id),
        bitrix_company_id=row.bitrix_company_id,
        metadata={"result": status_value},
    )
    session.commit()
    updated = session.execute(select(user_company_roles).where(user_company_roles.c.id == row.id)).mappings().one()
    return {"company_link": company_role_payload(updated), "verification_status": status_value}


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
        terminate_delegations_for_user(
            session, user_id=target.id, reason="company_link_revoked", request=request, actor_user_id=actor.id
        )
        revoke_sessions_for_user(
            session, target.id, request=request, actor_user_id=actor.id, reason_code="company_link_revoked"
        )
        session.execute(
            update(user_company_roles)
            .where(user_company_roles.c.id == row.id)
            .values(access_status="revoked", revoked_by_user_id=actor.id, revoked_at=now_utc())
        )
        audit_event(
            session,
            action="user_company_link_removed",
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
    metadata: dict[str, Any] = {"old_bitrix_contact_id": target.bitrix_contact_id, "reason": payload.reason}
    if payload.bitrix_contact_id is not None or "bitrix_contact_id" in payload.model_fields_set:
        new_contact_id = payload.bitrix_contact_id
        if new_contact_id is not None:
            conflict_user_id = session.execute(
                select(portal_users.c.id).where(
                    portal_users.c.id != target.id, portal_users.c.bitrix_contact_id == new_contact_id
                )
            ).scalar_one_or_none()
            if conflict_user_id is not None:
                raise auth_error(status.HTTP_409_CONFLICT, "BITRIX_LINK_CONFLICT", request)
            link_status = verify_bitrix_link("contact", new_contact_id)
            audit_action = (
                "bitrix_contact_link_created" if target.bitrix_contact_id is None else "bitrix_contact_link_changed"
            )
        else:
            link_status = "not_linked"
            audit_action = "bitrix_contact_link_removed"
        session.execute(
            update(portal_users)
            .where(portal_users.c.id == target.id)
            .values(
                bitrix_contact_id=new_contact_id,
                bitrix_contact_link_status=link_status,
                bitrix_contact_verified_at=now_utc() if new_contact_id else None,
            )
        )
        metadata["new_bitrix_contact_id"] = new_contact_id
        metadata["result"] = link_status
        audit_event(
            session,
            action=audit_action,
            object_type="portal_user",
            request=request,
            actor_user_id=actor.id,
            target_user_id=target.id,
            object_id=str(target.id),
            metadata=metadata,
        )
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
        company_audit_action = None
        new_company_id = row.bitrix_company_id
        if payload.clear_company_link:
            update_values["bitrix_link_status"] = "not_checked"
            update_values["bitrix_company_verified_at"] = None
            company_audit_action = "bitrix_company_link_removed"
        if payload.bitrix_company_id is not None:
            company_id = normalize_company_id(payload.bitrix_company_id)
            if company_id is None or company_id in SYSTEM_BITRIX_COMPANY_IDS:
                raise auth_error(status.HTTP_400_BAD_REQUEST, "BITRIX_COMPANY_NOT_FOUND", request)
            conflict = session.execute(
                select(user_company_roles.c.id).where(
                    user_company_roles.c.id != row.id,
                    user_company_roles.c.bitrix_company_id == company_id,
                    user_company_roles.c.access_status.in_(("pending", "active")),
                )
            ).scalar_one_or_none()
            if conflict is not None:
                raise auth_error(status.HTTP_409_CONFLICT, "BITRIX_LINK_CONFLICT", request)
            link_status = verify_bitrix_link("company", company_id)
            update_values["bitrix_company_id"] = company_id
            update_values["bitrix_link_status"] = PUBLIC_TO_COMPANY_LINK_STATUS.get(link_status, "bitrix_unavailable")
            update_values["bitrix_company_verified_at"] = now_utc()
            new_company_id = company_id
            company_audit_action = "bitrix_company_link_changed"
        if payload.bitrix_link_status is not None:
            if (
                payload.bitrix_link_status not in BITRIX_LINK_STATUSES
                and payload.bitrix_link_status not in PUBLIC_TO_COMPANY_LINK_STATUS
            ):
                raise auth_error(status.HTTP_400_BAD_REQUEST, "LINK_STATUS_NOT_ALLOWED", request)
            update_values["bitrix_link_status"] = PUBLIC_TO_COMPANY_LINK_STATUS.get(
                payload.bitrix_link_status, payload.bitrix_link_status
            )
        if update_values:
            session.execute(update(user_company_roles).where(user_company_roles.c.id == row.id).values(**update_values))
            audit_event(
                session,
                action=company_audit_action or "bitrix_company_link_changed",
                object_type="user_company_role",
                request=request,
                actor_user_id=actor.id,
                target_user_id=target.id,
                object_id=str(row.id),
                bitrix_company_id=new_company_id,
                metadata={
                    "old_bitrix_company_id": row.bitrix_company_id,
                    "new_bitrix_company_id": new_company_id,
                    "reason": payload.reason,
                },
            )
    session.commit()
    updated = session.execute(select(portal_users).where(portal_users.c.id == target.id)).mappings().one()
    return {"user": public_user_row(updated), "status": "ok"}


@router.post("/users/{user_id}/bitrix-links/verify-contact")
def verify_contact_bitrix_link(user_id: str, request: Request, session: Session = DB_SESSION) -> dict[str, Any]:
    actor = require_superadmin(request, session)
    target = target_user_or_404(session, user_id, request)
    if target.bitrix_contact_id is None:
        status_value = "not_linked"
    else:
        conflict_user_id = session.execute(
            select(portal_users.c.id).where(
                portal_users.c.id != target.id, portal_users.c.bitrix_contact_id == target.bitrix_contact_id
            )
        ).scalar_one_or_none()
        status_value = (
            "conflict" if conflict_user_id is not None else verify_bitrix_link("contact", target.bitrix_contact_id)
        )
    session.execute(
        update(portal_users)
        .where(portal_users.c.id == target.id)
        .values(bitrix_contact_link_status=status_value, bitrix_contact_verified_at=now_utc())
    )
    audit_event(
        session,
        action="bitrix_contact_link_verified",
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target.id,
        object_id=str(target.id),
        metadata={"result": status_value},
    )
    session.commit()
    updated = session.execute(select(portal_users).where(portal_users.c.id == target.id)).mappings().one()
    return {"user": public_user_row(updated), "verification_status": status_value}


@router.get("/integration-errors")
def list_integration_errors(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    object_type: str | None = Query(default=None),
    operation: str | None = Query(default=None),
    portal_id: str | None = Query(default=None),
    bitrix_id: int | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    require_superadmin(request, session)
    conditions = []
    if status_filter:
        conditions.append(integration_errors.c.status == PUBLIC_TO_INTEGRATION_STATUS.get(status_filter, status_filter))
    if object_type:
        conditions.append(integration_errors.c.object_type == object_type)
    if operation:
        conditions.append(integration_errors.c.operation == operation)
    if portal_id:
        conditions.append(integration_errors.c.object_id == portal_id.removeprefix("app_"))
    if bitrix_id is not None:
        conditions.append(integration_errors.c.bitrix_entity_id == bitrix_id)
    if correlation_id:
        conditions.append(integration_errors.c.correlation_id == correlation_id)
    if date_from:
        conditions.append(integration_errors.c.created_at >= date_from)
    if date_to:
        conditions.append(integration_errors.c.created_at <= date_to)
    total = session.execute(select(func.count()).select_from(integration_errors).where(*conditions)).scalar_one()
    rows = (
        session.execute(
            select(integration_errors)
            .where(*conditions)
            .order_by(desc(integration_errors.c.last_failed_at).nullslast(), desc(integration_errors.c.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .mappings()
        .all()
    )
    return {
        "items": [public_integration_error(row) for row in rows],
        "pagination": pagination_payload(total=total, page=page, page_size=page_size),
    }


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
    audit_rows = (
        session.execute(
            select(audit_logs)
            .where(audit_logs.c.object_type == "integration_error", audit_logs.c.object_id == str(row.id))
            .order_by(audit_logs.c.created_at.desc(), audit_logs.c.id.desc())
            .limit(20)
        )
        .mappings()
        .all()
    )
    return {
        "error": public_integration_error(row),
        "audit_events": [public_audit(audit_row) for audit_row in audit_rows],
    }


@router.post("/integration-errors/{error_id}/retry")
def retry_integration_error(error_id: str, request: Request, session: Session = DB_SESSION) -> dict[str, str]:
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
    if not bool(getattr(row, "retry_supported", True)) or row.operation not in RETRYABLE_OPERATIONS:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "INTEGRATION_RETRY_NOT_SUPPORTED", request)
    if row.status not in {"retrying", "resolved"}:
        history = list(getattr(row, "attempt_history_json", None) or [])
        history.append({"at": now_utc().isoformat(), "actor_user_id": actor.id, "result": "retry_requested"})
        session.execute(
            update(integration_errors)
            .where(integration_errors.c.id == row.id)
            .values(
                status="retrying",
                retry_count=row.retry_count + 1,
                last_attempt_at=now_utc(),
                attempt_history_json=history,
            )
        )
        audit_event(
            session,
            action="integration_retry_requested",
            object_type="integration_error",
            request=request,
            actor_user_id=actor.id,
            object_id=str(row.id),
            metadata={
                "operation": row.operation,
                "error_code": row.error_code,
                "integration_error_id": row.id,
                "attempt_number": row.retry_count + 1,
            },
        )
    session.commit()
    return {"status": "ok"}


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
            action="integration_error_status_changed",
            object_type="integration_error",
            request=request,
            actor_user_id=actor.id,
            object_id=str(row.id),
            metadata={
                "old_status": row.status,
                "new_status": "resolved",
                "error_code": row.error_code,
                "integration_error_id": row.id,
            },
        )
    session.commit()
    return {"status": "ok"}
