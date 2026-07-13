from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.delegations import (
    DelegationValidationError,
    active_delegation_payload,
    create_delegation,
    expire_or_terminate_delegation,
    parse_app_id,
    parse_user_id,
    run_delegation_worker,
)
from app.models import application_delegation_items, application_delegations, user_company_roles
from app.routers.auth import AuthError, auth_error, error_payload, get_current_user_from_cookie
from app.security import policies

router = APIRouter(tags=["delegations"])
DB_SESSION = Depends(get_db)


class DelegationCreatePayload(BaseModel):
    company_id: int
    delegate_user_id: str
    application_ids: list[str] = Field(default_factory=list)
    all_active: bool = False
    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=512)
    idempotency_key: str | None = Field(default=None, max_length=128)


class DelegationCancelPayload(BaseModel):
    reason: str = Field(default="manual", max_length=512)


class DelegationRequestCancelPayload(BaseModel):
    reason: str = Field(default="delegate_request", max_length=512)


def parse_delegation_id(value: str) -> int | None:
    raw = value.removeprefix("dlg_")
    try:
        parsed = int(raw)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def pagination_payload(*, total: int, page: int, page_size: int) -> dict[str, int]:
    return {"total": total, "page": page, "page_size": page_size, "pages": (total + page_size - 1) // page_size}


async def access_condition(session: Session, user):
    if policies.is_superadmin(user):
        return True
    if user.user_type != "client" or user.status != "active":
        return application_delegations.c.id == -1
    admin_companies = list(
        session.execute(
            select(user_company_roles.c.bitrix_company_id).where(
                user_company_roles.c.user_id == user.id,
                user_company_roles.c.access_status == "active",
                user_company_roles.c.role_code == "client_admin",
            )
        ).scalars()
    )
    conditions = [
        application_delegations.c.delegator_user_id == user.id,
        application_delegations.c.delegate_user_id == user.id,
    ]
    if admin_companies:
        conditions.append(application_delegations.c.company_id.in_(admin_companies))
    return or_(*conditions)


def _items_for(session: Session, delegation_id: int):
    return (
        session.execute(
            select(application_delegation_items).where(application_delegation_items.c.delegation_id == delegation_id)
        )
        .mappings()
        .all()
    )


@router.post("/delegations", status_code=status.HTTP_201_CREATED)
async def create_application_delegation(
    payload: DelegationCreatePayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    delegate_id = parse_user_id(payload.delegate_user_id)
    if delegate_id is None:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "DELEGATE_NOT_ALLOWED", request)
    app_ids = []
    for raw_id in payload.application_ids:
        parsed = parse_app_id(raw_id)
        if parsed is None:
            raise auth_error(status.HTTP_400_BAD_REQUEST, "APPLICATION_NOT_FOUND", request)
        app_ids.append(parsed)
    try:
        return create_delegation(
            session,
            request=request,
            actor=current_user,
            delegate_user_id=delegate_id,
            company_id=payload.company_id,
            application_ids=app_ids,
            all_active=payload.all_active,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
        )
    except DelegationValidationError as exc:
        payload_data = error_payload("DELEGATION_VALIDATION_FAILED", request)
        payload_data["problems"] = exc.problems  # type: ignore[assignment]
        raise AuthError(status.HTTP_409_CONFLICT, payload_data) from exc


@router.get("/delegations")
async def list_delegations(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    role: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    condition = await access_condition(session, current_user)
    conditions = [condition]
    if status_filter:
        conditions.append(application_delegations.c.status == status_filter)
    if role == "delegator":
        conditions.append(application_delegations.c.delegator_user_id == current_user.id)
    if role == "delegate":
        conditions.append(application_delegations.c.delegate_user_id == current_user.id)
    total = session.execute(select(func.count()).select_from(application_delegations).where(*conditions)).scalar_one()
    rows = (
        session.execute(
            select(application_delegations)
            .where(*conditions)
            .order_by(application_delegations.c.created_at.desc(), application_delegations.c.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .mappings()
        .all()
    )
    return {
        "items": [active_delegation_payload(row, _items_for(session, row.id)) for row in rows],
        "pagination": pagination_payload(total=total, page=page, page_size=page_size),
    }


@router.get("/delegations/{delegation_id}")
async def get_delegation(delegation_id: str, request: Request, session: Session = DB_SESSION) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    parsed = parse_delegation_id(delegation_id)
    if parsed is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DELEGATION_NOT_FOUND", request)
    condition = await access_condition(session, current_user)
    row = (
        session.execute(select(application_delegations).where(application_delegations.c.id == parsed, condition))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DELEGATION_NOT_FOUND", request)
    return {"delegation": active_delegation_payload(row, _items_for(session, row.id))}


@router.post("/delegations/{delegation_id}/cancel")
async def cancel_delegation(
    delegation_id: str,
    payload: DelegationCancelPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, str]:
    current_user = get_current_user_from_cookie(request, session)
    parsed = parse_delegation_id(delegation_id)
    if parsed is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DELEGATION_NOT_FOUND", request)
    row = (
        session.execute(select(application_delegations).where(application_delegations.c.id == parsed))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DELEGATION_NOT_FOUND", request)
    allowed = row.delegator_user_id == current_user.id or policies.is_superadmin(current_user)
    if not allowed:
        admin_role = session.execute(
            select(user_company_roles.c.id).where(
                user_company_roles.c.user_id == current_user.id,
                user_company_roles.c.bitrix_company_id == row.company_id,
                user_company_roles.c.access_status == "active",
                user_company_roles.c.role_code == "client_admin",
            )
        ).scalar_one_or_none()
        allowed = admin_role is not None
    if not allowed:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DELEGATION_NOT_FOUND", request)
    expire_or_terminate_delegation(
        session,
        delegation_id=row.id,
        actor_user_id=current_user.id,
        request=request,
        status_value="cancelled",
        reason=payload.reason,
    )
    session.commit()
    return {"status": "ok"}


@router.post("/delegations/{delegation_id}/request-cancel")
async def request_cancel_delegation(
    delegation_id: str,
    payload: DelegationRequestCancelPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, str]:
    current_user = get_current_user_from_cookie(request, session)
    parsed = parse_delegation_id(delegation_id)
    if parsed is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DELEGATION_NOT_FOUND", request)
    row = (
        session.execute(
            select(application_delegations).where(
                application_delegations.c.id == parsed,
                application_delegations.c.delegate_user_id == current_user.id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DELEGATION_NOT_FOUND", request)
    from app.auth import audit_event

    audit_event(
        session,
        action="delegation_cancel_requested",
        object_type="application_delegation",
        object_id=str(row.id),
        request=request,
        actor_user_id=current_user.id,
        target_user_id=row.delegator_user_id,
        bitrix_company_id=row.company_id,
        metadata={"reason": payload.reason},
    )
    session.commit()
    return {"status": "ok"}


@router.get("/applications/{application_id}/delegation")
async def get_application_delegation(
    application_id: str, request: Request, session: Session = DB_SESSION
) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    parsed = parse_app_id(application_id)
    if parsed is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    try:
        await policies.require_application_access(session, current_user, "read", application_id=parsed, request=request)
    except policies.PolicyError as exc:
        session.commit()
        raise auth_error(exc.status_code, exc.error_code, request) from exc
    row = (
        session.execute(
            select(application_delegations)
            .select_from(application_delegations.join(application_delegation_items))
            .where(
                application_delegation_items.c.application_id == parsed,
                application_delegations.c.status.in_(("scheduled", "active")),
                application_delegation_items.c.status.in_(("scheduled", "active")),
            )
            .order_by(application_delegations.c.starts_at.desc())
        )
        .mappings()
        .first()
    )
    if row is None:
        return {"delegation": None}
    return {"delegation": active_delegation_payload(row, _items_for(session, row.id))}


@router.post("/delegations/run-worker")
async def run_worker_for_tests(request: Request, session: Session = DB_SESSION) -> dict[str, int]:
    current_user = get_current_user_from_cookie(request, session)
    if not policies.is_superadmin(current_user):
        raise auth_error(status.HTTP_403_FORBIDDEN, "SUPERADMIN_REQUIRED", request)
    return run_delegation_worker(session, request=request)


@router.get("/superadmin/delegations")
async def list_superadmin_delegations(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    if not policies.is_superadmin(current_user):
        raise auth_error(status.HTTP_403_FORBIDDEN, "SUPERADMIN_REQUIRED", request)
    conditions = []
    if status_filter:
        conditions.append(application_delegations.c.status == status_filter)
    total = session.execute(select(func.count()).select_from(application_delegations).where(*conditions)).scalar_one()
    rows = (
        session.execute(
            select(application_delegations)
            .where(*conditions)
            .order_by(application_delegations.c.created_at.desc(), application_delegations.c.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .mappings()
        .all()
    )
    return {
        "items": [active_delegation_payload(row, _items_for(session, row.id)) for row in rows],
        "pagination": pagination_payload(total=total, page=page, page_size=page_size),
    }


@router.post("/superadmin/delegations/{delegation_id}/terminate")
async def terminate_superadmin_delegation(
    delegation_id: str,
    payload: DelegationCancelPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, str]:
    current_user = get_current_user_from_cookie(request, session)
    if not policies.is_superadmin(current_user):
        raise auth_error(status.HTTP_403_FORBIDDEN, "SUPERADMIN_REQUIRED", request)
    parsed = parse_delegation_id(delegation_id)
    if parsed is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DELEGATION_NOT_FOUND", request)
    changed = expire_or_terminate_delegation(
        session,
        delegation_id=parsed,
        actor_user_id=current_user.id,
        request=request,
        status_value="terminated",
        reason=payload.reason,
    )
    session.commit()
    return {"status": "ok", "changed": str(changed)}
