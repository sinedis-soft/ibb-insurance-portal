from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.company_access import normalize_company_id
from app.db import get_db
from app.i18n import policy_status_label
from app.models import document_transfer_logs, portal_policies, user_company_roles
from app.routers.auth import auth_error, get_current_user_from_cookie, request_locale
from app.security import policies
from app.security.policies import PolicyError

router = APIRouter(tags=["policies"])
DB_SESSION = Depends(get_db)
VISIBLE_POLICY_STATUSES = ("active", "expiring_soon")
EXPIRING_SOON_DAYS = 30


def parse_policy_id(value: str) -> int | None:
    raw_value = value.removeprefix("policy_")
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def policy_error_response(session: Session, exc: PolicyError, request: Request):
    session.commit()
    raise auth_error(exc.status_code, exc.error_code, request) from exc


def effective_status(row) -> str:
    today = date.today()
    if row.valid_to is not None and row.valid_to < today and row.policy_status in VISIBLE_POLICY_STATUSES:
        return "expired"
    if (
        row.policy_status == "active"
        and row.valid_to is not None
        and today <= row.valid_to <= today + timedelta(days=EXPIRING_SOON_DAYS)
    ):
        return "expiring_soon"
    return row.policy_status


def is_visible_policy(row) -> bool:
    today = date.today()
    return (
        effective_status(row) in VISIBLE_POLICY_STATUSES
        and row.valid_to is not None
        and row.valid_to >= today
        and (row.valid_from is None or row.valid_from <= today)
    )


def product_label(product_type_code: str | None) -> str | None:
    return product_type_code.replace("_", " ").title() if product_type_code else None


def decimal_to_string(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


async def document_metadata(session: Session, user, document_id: int | None) -> list[dict[str, Any]]:
    if document_id is None:
        return []
    if not await policies.can_access_document(session, user, document_id, "read_metadata"):
        return []
    row = (
        session.execute(select(document_transfer_logs).where(document_transfer_logs.c.id == document_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        return []
    is_download_available = await policies.can_access_document(session, user, document_id, "download")
    policy_row = (
        session.execute(
            select(portal_policies.c.application_id).where(portal_policies.c.document_transfer_log_id == document_id)
        )
        .mappings()
        .one_or_none()
    )
    if policy_row is not None:
        is_download_available = is_download_available and await policies.can_access_policy(
            session,
            user,
            policy_row.application_id,
            "download",
        )
    return [
        {
            "id": f"doc_{row.id}",
            "document_type": row.document_type,
            "label": row.document_type,
            "is_policy_file": bool(row.is_policy_file),
            "transfer_status": row.transfer_status,
            "is_download_available": is_download_available,
        }
    ]


async def public_policy(session: Session, user, row, *, locale: str) -> dict[str, Any]:
    status_code = effective_status(row)
    return {
        "id": f"policy_{row.id}",
        "application_id": f"app_{row.application_id}",
        "bitrix_deal_id": row.bitrix_deal_id,
        "bitrix_company_id": str(row.bitrix_company_id),
        "policy_number": row.policy_number,
        "product_type_code": row.product_type_code,
        "product_label": product_label(row.product_type_code),
        "valid_from": row.valid_from.isoformat() if row.valid_from else None,
        "valid_to": row.valid_to.isoformat() if row.valid_to else None,
        "premium_amount": decimal_to_string(row.premium_amount),
        "premium_currency": row.premium_currency,
        "policy_status": status_code,
        "status_label": policy_status_label(locale, status_code),
        "is_expiring_soon": status_code == "expiring_soon",
        "documents": await document_metadata(session, user, row.document_transfer_log_id),
    }


def apply_visible_scope(statement):
    today = date.today()
    return statement.where(
        portal_policies.c.policy_status.in_(VISIBLE_POLICY_STATUSES),
        (portal_policies.c.valid_from.is_(None)) | (portal_policies.c.valid_from <= today),
        portal_policies.c.valid_to.is_not(None),
        portal_policies.c.valid_to >= today,
    )


def apply_search(statement, query: str | None, *, company_ids: list[int]):
    normalized = (query or "").strip()
    if not normalized:
        return statement
    pattern = f"%{normalized.lower()}%"
    conditions = [
        func.lower(portal_policies.c.policy_number).like(pattern),
        func.lower(func.coalesce(portal_policies.c.product_type_code, "")).like(pattern),
        sa.exists(
            select(user_company_roles.c.id).where(
                user_company_roles.c.bitrix_company_id == portal_policies.c.bitrix_company_id,
                user_company_roles.c.bitrix_company_id.in_(company_ids),
                user_company_roles.c.access_status == "active",
                func.lower(func.coalesce(user_company_roles.c.company_title_cache, "")).like(pattern),
            )
        ),
    ]
    try:
        numeric_query = int(normalized)
    except ValueError:
        pass
    else:
        conditions.extend(
            [
                portal_policies.c.id == numeric_query,
                portal_policies.c.application_id == numeric_query,
                portal_policies.c.bitrix_deal_id == numeric_query,
            ]
        )
    return statement.where(sa.or_(*conditions))


async def scoped_company_ids(
    session: Session,
    user,
    request: Request,
    company_id: str | None,
) -> list[int]:
    if company_id is not None:
        parsed_company_id = normalize_company_id(company_id)
        if parsed_company_id is None:
            raise auth_error(status.HTTP_404_NOT_FOUND, "COMPANY_ACCESS_DENIED", request)
        try:
            await policies.require_company_access(session, user, parsed_company_id, "read", request=request)
        except PolicyError as exc:
            policy_error_response(session, exc, request)
        return [parsed_company_id]
    return await policies.get_accessible_company_ids(session, user)


@router.get("/policies")
async def list_policies(
    request: Request,
    company_id: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=128),
    product_type: str | None = Query(default=None, max_length=128),
    status_filter: str | None = Query(default=None, alias="status"),
    expires_within_days: int | None = Query(default=None, ge=1, le=366),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    if current_user.user_type == "partner":
        return {"items": [], "pagination": {"limit": limit, "offset": offset, "total": 0}}

    company_ids = await scoped_company_ids(session, current_user, request, company_id)
    if not company_ids:
        return {"items": [], "pagination": {"limit": limit, "offset": offset, "total": 0}}

    statement = apply_visible_scope(select(portal_policies).where(portal_policies.c.bitrix_company_id.in_(company_ids)))
    if product_type:
        statement = statement.where(portal_policies.c.product_type_code == product_type)
    if expires_within_days is not None:
        today = date.today()
        statement = statement.where(
            portal_policies.c.valid_to.is_not(None),
            portal_policies.c.valid_to >= today,
            portal_policies.c.valid_to <= today + timedelta(days=expires_within_days),
        )
    if status_filter == "expiring_soon":
        today = date.today()
        statement = statement.where(portal_policies.c.valid_to <= today + timedelta(days=EXPIRING_SOON_DAYS))
    elif status_filter == "active":
        statement = statement.where(portal_policies.c.policy_status == "active")
    elif status_filter:
        return {"items": [], "pagination": {"limit": limit, "offset": offset, "total": 0}}
    statement = apply_search(statement, q, company_ids=company_ids)

    candidate_rows = session.execute(
        statement.order_by(
            sa.asc(portal_policies.c.valid_to).nulls_last(),
            sa.desc(portal_policies.c.updated_at),
            sa.desc(portal_policies.c.id),
        )
    ).mappings()
    accessible_rows = [
        row
        for row in candidate_rows
        if await policies.can_access_policy(session, current_user, row.application_id, "read")
    ]
    paginated_rows = accessible_rows[offset : offset + limit]
    locale = request_locale(request)
    return {
        "items": [await public_policy(session, current_user, row, locale=locale) for row in paginated_rows],
        "pagination": {"limit": limit, "offset": offset, "total": len(accessible_rows)},
    }


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    current_user = get_current_user_from_cookie(request, session)
    parsed_policy_id = parse_policy_id(policy_id)
    if parsed_policy_id is None or current_user.user_type == "partner":
        raise auth_error(status.HTTP_404_NOT_FOUND, "POLICY_NOT_FOUND", request)

    row = (
        session.execute(select(portal_policies).where(portal_policies.c.id == parsed_policy_id))
        .mappings()
        .one_or_none()
    )
    if row is None or not is_visible_policy(row):
        raise auth_error(status.HTTP_404_NOT_FOUND, "POLICY_NOT_FOUND", request)

    try:
        await policies.require_policy_access(session, current_user, row.application_id, "read", request=request)
    except PolicyError as exc:
        policy_error_response(session, exc, request)

    return await public_policy(session, current_user, row, locale=request_locale(request))
