from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import audit_event, now_utc
from app.bitrix import BitrixError, get_company
from app.company_access import CLIENT_COMPANY_ROLES, OPEN_ACCESS_STATUSES, normalize_company_id
from app.config import Settings, get_settings
from app.db import get_db
from app.models import partner_client_links, portal_users, user_company_roles
from app.routers.auth import auth_error, get_current_user_from_cookie, parse_public_user_id
from app.security import policies

router = APIRouter(tags=["company-access"])
DB_SESSION = Depends(get_db)
APP_SETTINGS = Depends(get_settings)


class CompanyRoleRequest(BaseModel):
    bitrix_company_id: int | str
    role_code: str


class PartnerClientLinkRequest(BaseModel):
    bitrix_company_id: int | str
    client_user_id: str | None = None
    status: str = "active"


def parse_user_id(value: str) -> int | None:
    parsed = parse_public_user_id(value)
    if parsed is not None:
        return parsed
    try:
        user_id = int(value)
    except ValueError:
        return None
    return user_id if user_id > 0 else None


def require_superadmin_role(request: Request, session: Session):
    current_user = get_current_user_from_cookie(request, session)
    if current_user.role_code != "superadmin":
        raise auth_error(status.HTTP_403_FORBIDDEN, "SUPERADMIN_REQUIRED", request)
    return current_user


def public_company_role(row) -> dict[str, Any]:
    return {
        "id": f"ucr_{row.id}",
        "user_id": f"usr_{row.user_id}",
        "bitrix_company_id": str(row.bitrix_company_id),
        "role_code": row.role_code,
        "access_status": row.access_status,
        "bitrix_link_status": row.bitrix_link_status,
        "company_title": row.company_title_cache,
        "company_country_code": row.company_country_code_cache,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def public_partner_client_link(row) -> dict[str, Any]:
    return {
        "id": f"pcl_{row.id}",
        "partner_user_id": f"usr_{row.partner_user_id}",
        "client_user_id": f"usr_{row.client_user_id}" if row.client_user_id else None,
        "bitrix_company_id": str(row.bitrix_company_id),
        "status": row.status,
        "is_other_partner_client": row.is_other_partner_client,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def company_cache_values(company: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_title_cache": company.get("TITLE"),
        "company_country_code_cache": company.get("ADDRESS_COUNTRY_CODE") or company.get("REG_ADDRESS_COUNTRY_CODE"),
        "bitrix_updated_at_cache": company.get("DATE_MODIFY"),
        "cache_refreshed_at": now_utc(),
    }


def duplicate_exists(session: Session, *, user_id: int, bitrix_company_id: int, role_code: str) -> bool:
    return (
        session.execute(
            select(user_company_roles.c.id).where(
                user_company_roles.c.user_id == user_id,
                user_company_roles.c.bitrix_company_id == bitrix_company_id,
                user_company_roles.c.role_code == role_code,
                user_company_roles.c.access_status.in_(OPEN_ACCESS_STATUSES),
            )
        ).scalar_one_or_none()
        is not None
    )


def partner_link_duplicate_exists(session: Session, *, partner_user_id: int, bitrix_company_id: int) -> bool:
    return (
        session.execute(
            select(partner_client_links.c.id).where(
                partner_client_links.c.partner_user_id == partner_user_id,
                partner_client_links.c.bitrix_company_id == bitrix_company_id,
            )
        ).scalar_one_or_none()
        is not None
    )


async def resolve_company_link(
    *,
    bitrix_company_id: int,
    settings: Settings,
    request: Request,
    session: Session,
    actor_id: int,
) -> tuple[str, str, dict[str, Any]]:
    try:
        company = await get_company(bitrix_company_id, settings)
    except BitrixError as exc:
        if exc.error_code == "BITRIX_NOT_FOUND":
            raise auth_error(status.HTTP_404_NOT_FOUND, "BITRIX_COMPANY_NOT_FOUND", request) from exc
        audit_event(
            session,
            action="bitrix_company_link_check_failed",
            object_type="bitrix_company",
            request=request,
            actor_user_id=actor_id,
            object_id=str(bitrix_company_id),
            metadata={"bitrix_company_id": bitrix_company_id, "error_code": exc.error_code},
        )
        return "pending", "bitrix_unavailable", {}
    return "active", "confirmed", company_cache_values(company)


@router.get("/me/companies")
async def my_companies(request: Request, session: Session = DB_SESSION) -> dict[str, list[dict[str, Any]]]:
    current_user = get_current_user_from_cookie(request, session)
    company_ids = await policies.get_accessible_company_ids(session, current_user)
    if not company_ids:
        return {"items": []}
    rows = (
        session.execute(
            select(user_company_roles).where(
                user_company_roles.c.user_id == current_user.id,
                user_company_roles.c.bitrix_company_id.in_(company_ids),
                user_company_roles.c.access_status == "active",
            )
        )
        .mappings()
        .all()
    )
    return {"items": [public_company_role(row) for row in rows]}


@router.get("/partner/companies")
def partner_companies(request: Request, session: Session = DB_SESSION) -> dict[str, list[dict[str, Any]]]:
    current_user = get_current_user_from_cookie(request, session)
    if current_user.user_type != "partner":
        return {"items": []}
    rows = (
        session.execute(
            select(partner_client_links).where(
                partner_client_links.c.partner_user_id == current_user.id,
                partner_client_links.c.status == "active",
            )
        )
        .mappings()
        .all()
    )
    return {"items": [public_partner_client_link(row) for row in rows]}


@router.get("/admin/users/{user_id}/company-roles")
def list_company_roles(
    user_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, list[dict[str, Any]]]:
    require_superadmin_role(request, session)
    target_user_id = parse_user_id(user_id)
    if target_user_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
    rows = (
        session.execute(select(user_company_roles).where(user_company_roles.c.user_id == target_user_id))
        .mappings()
        .all()
    )
    return {"company_roles": [public_company_role(row) for row in rows]}


@router.get("/admin/partners/{partner_user_id}/client-links")
def list_partner_client_links(
    partner_user_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, list[dict[str, Any]]]:
    require_superadmin_role(request, session)
    partner_id = parse_user_id(partner_user_id)
    if partner_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
    rows = (
        session.execute(select(partner_client_links).where(partner_client_links.c.partner_user_id == partner_id))
        .mappings()
        .all()
    )
    return {"partner_client_links": [public_partner_client_link(row) for row in rows]}


@router.post("/admin/partners/{partner_user_id}/client-links", status_code=status.HTTP_201_CREATED)
def create_partner_client_link(
    partner_user_id: str,
    payload: PartnerClientLinkRequest,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    actor = require_superadmin_role(request, session)
    partner_id = parse_user_id(partner_user_id)
    if partner_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
    partner = session.execute(select(portal_users).where(portal_users.c.id == partner_id)).mappings().one_or_none()
    if partner is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
    if partner.status == "blocked":
        raise auth_error(status.HTTP_403_FORBIDDEN, "USER_BLOCKED", request)
    if partner.user_type != "partner":
        raise auth_error(status.HTTP_400_BAD_REQUEST, "PARTNER_ROLE_REQUIRED", request)
    if payload.status not in {"pending", "active", "another_partner", "rejected"}:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "PARTNER_LINK_STATUS_NOT_ALLOWED", request)
    company_id = normalize_company_id(payload.bitrix_company_id)
    if company_id is None:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "BITRIX_COMPANY_NOT_FOUND", request)
    client_id = parse_user_id(payload.client_user_id) if payload.client_user_id else None
    if client_id is not None:
        client = session.execute(select(portal_users).where(portal_users.c.id == client_id)).mappings().one_or_none()
        if client is None:
            raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
        if client.user_type != "client":
            raise auth_error(status.HTTP_400_BAD_REQUEST, "ROLE_NOT_ALLOWED", request)
    if partner_link_duplicate_exists(session, partner_user_id=partner.id, bitrix_company_id=company_id):
        raise auth_error(status.HTTP_409_CONFLICT, "PARTNER_CLIENT_LINK_ALREADY_EXISTS", request)
    now = now_utc()
    link_id = session.execute(
        insert(partner_client_links)
        .values(
            partner_user_id=partner.id,
            client_user_id=client_id,
            bitrix_company_id=company_id,
            status=payload.status,
            access_status="active" if payload.status in {"active", "another_partner"} else payload.status,
            is_other_partner_client=payload.status == "another_partner",
            created_by_user_id=actor.id,
            confirmed_by_user_id=actor.id if payload.status == "active" else None,
            confirmed_at=now if payload.status == "active" else None,
        )
        .returning(partner_client_links.c.id)
    ).scalar_one()
    audit_event(
        session,
        action="partner_client_link_created",
        object_type="partner_client_link",
        request=request,
        actor_user_id=actor.id,
        target_user_id=partner.id,
        object_id=str(link_id),
        bitrix_company_id=company_id,
        metadata={"status": payload.status, "partner_user_id": partner.id, "client_user_id": client_id},
    )
    session.commit()
    row = session.execute(select(partner_client_links).where(partner_client_links.c.id == link_id)).mappings().one()
    return {"partner_client_link": public_partner_client_link(row)}


@router.post("/admin/users/{user_id}/company-roles", status_code=status.HTTP_201_CREATED)
async def assign_company_role(
    user_id: str,
    payload: CompanyRoleRequest,
    request: Request,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, Any]:
    actor = require_superadmin_role(request, session)
    target_user_id = parse_user_id(user_id)
    if target_user_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
    target_user = (
        session.execute(select(portal_users).where(portal_users.c.id == target_user_id))
        .mappings()
        .one_or_none()
    )
    if target_user is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", request)
    if target_user.status == "blocked":
        raise auth_error(status.HTTP_403_FORBIDDEN, "USER_BLOCKED", request)
    if target_user.user_type != "client" or payload.role_code not in CLIENT_COMPANY_ROLES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "ROLE_NOT_ALLOWED", request)
    company_id = normalize_company_id(payload.bitrix_company_id)
    if company_id is None:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "BITRIX_COMPANY_NOT_FOUND", request)
    if duplicate_exists(session, user_id=target_user.id, bitrix_company_id=company_id, role_code=payload.role_code):
        raise auth_error(status.HTTP_409_CONFLICT, "COMPANY_ROLE_ALREADY_EXISTS", request)

    access_status, bitrix_link_status, cache = await resolve_company_link(
        bitrix_company_id=company_id,
        settings=settings,
        request=request,
        session=session,
        actor_id=actor.id,
    )
    values = {
        "user_id": target_user.id,
        "bitrix_company_id": company_id,
        "role_code": payload.role_code,
        "access_status": access_status,
        "bitrix_link_status": bitrix_link_status,
        "created_by_user_id": actor.id,
        **cache,
    }
    if access_status == "active":
        values["confirmed_by_user_id"] = actor.id
        values["confirmed_at"] = now_utc()
    try:
        role_link_id = session.execute(
            insert(user_company_roles).values(**values).returning(user_company_roles.c.id)
        ).scalar_one()
    except IntegrityError as exc:
        session.rollback()
        raise auth_error(status.HTTP_409_CONFLICT, "COMPANY_ROLE_ALREADY_EXISTS", request) from exc

    audit_event(
        session,
        action="company_role_assigned",
        object_type="user_company_role",
        request=request,
        actor_user_id=actor.id,
        target_user_id=target_user.id,
        object_id=str(role_link_id),
        metadata={
            "bitrix_company_id": company_id,
            "role_code": payload.role_code,
            "access_status": access_status,
            "bitrix_link_status": bitrix_link_status,
        },
    )
    session.commit()
    row = session.execute(select(user_company_roles).where(user_company_roles.c.id == role_link_id)).mappings().one()
    return {"company_role": public_company_role(row)}


@router.post("/admin/company-roles/{role_link_id}/revoke")
@router.delete("/admin/users/{user_id}/company-roles/{role_link_id}")
def revoke_company_role(
    role_link_id: int,
    request: Request,
    user_id: str | None = None,
    session: Session = DB_SESSION,
) -> dict[str, str]:
    actor = require_superadmin_role(request, session)
    row = (
        session.execute(select(user_company_roles).where(user_company_roles.c.id == role_link_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "COMPANY_ROLE_NOT_FOUND", request)
    if user_id is not None:
        target_user_id = parse_user_id(user_id)
        if target_user_id is None or target_user_id != row.user_id:
            raise auth_error(status.HTTP_404_NOT_FOUND, "COMPANY_ROLE_NOT_FOUND", request)
    if row.access_status != "revoked":
        session.execute(
            update(user_company_roles)
            .where(user_company_roles.c.id == row.id)
            .values(access_status="revoked", revoked_by_user_id=actor.id, revoked_at=now_utc())
        )
        audit_event(
            session,
            action="company_role_revoked",
            object_type="user_company_role",
            request=request,
            actor_user_id=actor.id,
            target_user_id=row.user_id,
            object_id=str(row.id),
            metadata={"bitrix_company_id": row.bitrix_company_id, "role_code": row.role_code},
        )
    session.commit()
    return {"status": "ok"}


@router.post("/admin/partner-client-links/{link_id}/revoke")
def revoke_partner_client_link(
    link_id: int,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, str]:
    actor = require_superadmin_role(request, session)
    row = (
        session.execute(select(partner_client_links).where(partner_client_links.c.id == link_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "PARTNER_CLIENT_LINK_NOT_FOUND", request)
    if row.status != "revoked":
        session.execute(
            update(partner_client_links)
            .where(partner_client_links.c.id == row.id)
            .values(status="revoked", access_status="revoked", revoked_by_user_id=actor.id, revoked_at=now_utc())
        )
        audit_event(
            session,
            action="partner_client_link_revoked",
            object_type="partner_client_link",
            request=request,
            actor_user_id=actor.id,
            target_user_id=row.partner_user_id,
            object_id=str(row.id),
            bitrix_company_id=row.bitrix_company_id,
            metadata={"status": "revoked", "partner_user_id": row.partner_user_id},
        )
    session.commit()
    return {"status": "ok"}
