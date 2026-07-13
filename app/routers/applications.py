from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.company_access import normalize_company_id
from app.db import get_db
from app.i18n import portal_status_label
from app.models import bitrix_stage_mappings, portal_applications
from app.routers.auth import auth_error, get_current_user_from_cookie, request_locale
from app.security import policies
from app.security.policies import PolicyError

router = APIRouter(tags=["applications"])
DB_SESSION = Depends(get_db)

VISIBLE_STAGE = (bitrix_stage_mappings.c.is_visible_to_client.is_(True)) | (bitrix_stage_mappings.c.id.is_(None))
READ_ACTIONS = ("view_policy_status",)
WRITE_ACTIONS = (
    "upload_document",
    "request_policy_email",
    "request_policy_telegram",
    "request_change",
    "request_cancellation",
)


def parse_application_id(value: str) -> int | None:
    raw_value = value.removeprefix("app_")
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def application_join():
    return portal_applications.outerjoin(
        bitrix_stage_mappings,
        (portal_applications.c.bitrix_category_id == bitrix_stage_mappings.c.bitrix_category_id)
        & (portal_applications.c.bitrix_stage_id == bitrix_stage_mappings.c.bitrix_stage_id),
    )


def status_for(row) -> str:
    return row.mapped_portal_status or row.portal_status


def application_title(row) -> str:
    if row.title_cache:
        return row.title_cache
    if row.client_reference_number:
        return row.client_reference_number
    return f"APP-{row.id:06d}"


def public_application(row, *, locale: str, detail: bool = False, available_actions: list[str] | None = None):
    portal_status = status_for(row)
    payload: dict[str, Any] = {
        "id": f"app_{row.id}",
        "application_type": row.application_type,
        "bitrix_company_id": str(row.bitrix_company_id),
        "title": application_title(row),
        "portal_status": portal_status,
        "status_label": portal_status_label(locale, portal_status),
        "product_type_code": row.product_type_code,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if detail:
        payload.update(
            {
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
                "client_reference_number": row.client_reference_number,
                "sync_status": row.sync_status,
                "sync_warning": row.sync_status in {"pending", "retry_required", "sync_error"},
                "available_actions": available_actions or [],
                "document_requests": [],
                "client_messages": [],
            }
        )
    return payload


def base_application_statement():
    return (
        select(
            portal_applications,
            bitrix_stage_mappings.c.portal_status.label("mapped_portal_status"),
        )
        .select_from(application_join())
        .where(VISIBLE_STAGE)
    )


def apply_filters(statement, *, company_ids: list[int], status_filter: str | None, type_filter: str | None):
    statement = statement.where(portal_applications.c.bitrix_company_id.in_(company_ids))
    if status_filter:
        statement = statement.where(
            func.coalesce(bitrix_stage_mappings.c.portal_status, portal_applications.c.portal_status) == status_filter
        )
    if type_filter:
        statement = statement.where(portal_applications.c.application_type == type_filter)
    return statement


async def available_actions(session: Session, user, application_id: int) -> list[str]:
    actions = list(READ_ACTIONS)
    for action in WRITE_ACTIONS:
        if await policies.can_access_application(session, user, action, application_id):
            actions.append(action)
    return actions


def policy_error_response(session: Session, exc: PolicyError, request: Request):
    session.commit()
    raise auth_error(exc.status_code, exc.error_code, request) from exc


@router.get("/applications")
async def list_applications(
    request: Request,
    company_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    type_filter: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    if current_user.user_type == "partner":
        return {"items": [], "pagination": {"limit": limit, "offset": offset, "total": 0}}

    if company_id is not None:
        parsed_company_id = normalize_company_id(company_id)
        if parsed_company_id is None:
            raise auth_error(status.HTTP_404_NOT_FOUND, "COMPANY_ACCESS_DENIED", request)
        try:
            await policies.require_company_access(session, current_user, parsed_company_id, "read", request=request)
        except PolicyError as exc:
            policy_error_response(session, exc, request)
        company_ids = [parsed_company_id]
    else:
        company_ids = await policies.get_accessible_company_ids(session, current_user)

    if not company_ids:
        return {"items": [], "pagination": {"limit": limit, "offset": offset, "total": 0}}

    filtered = apply_filters(
        base_application_statement(),
        company_ids=company_ids,
        status_filter=status_filter,
        type_filter=type_filter,
    )
    candidate_rows = (
        session.execute(
            filtered.order_by(
                sa.desc(portal_applications.c.updated_at),
                sa.desc(portal_applications.c.created_at),
                sa.desc(portal_applications.c.id),
            )
        )
        .mappings()
        .all()
    )
    accessible_rows = [
        row for row in candidate_rows if await policies.can_access_application(session, current_user, "read", row.id)
    ]
    paginated_rows = accessible_rows[offset : offset + limit]
    locale = request_locale(request)
    return {
        "items": [public_application(row, locale=locale) for row in paginated_rows],
        "pagination": {"limit": limit, "offset": offset, "total": len(accessible_rows)},
    }


@router.get("/applications/{application_id}")
async def get_application(
    application_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    parsed_application_id = parse_application_id(application_id)
    if parsed_application_id is None or current_user.user_type == "partner":
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)

    try:
        await policies.require_application_access(
            session,
            current_user,
            "read",
            application_id=parsed_application_id,
            request=request,
        )
    except PolicyError as exc:
        policy_error_response(session, exc, request)

    row = (
        session.execute(base_application_statement().where(portal_applications.c.id == parsed_application_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)

    return public_application(
        row,
        locale=request_locale(request),
        detail=True,
        available_actions=await available_actions(session, current_user, parsed_application_id),
    )
