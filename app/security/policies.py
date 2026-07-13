from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import Request, status
from sqlalchemy import Select, exists, select
from sqlalchemy.orm import Session

from app.auth import audit_event, request_id
from app.company_access import SYSTEM_BITRIX_COMPANY_IDS
from app.logging import LOGGER_NAME
from app.models import document_transfer_logs, partner_client_links, portal_applications, user_company_roles

CLIENT_ROLES = frozenset({"client_executor", "client_admin", "client_viewer"})
COMPANY_ACTION_ROLES = {
    "read": CLIENT_ROLES,
    "create_application": frozenset({"client_executor", "client_admin"}),
    "approve_application": frozenset({"client_admin"}),
    "manage_users": frozenset(),
}
APPLICATION_ACTION_ROLES = {
    "read": CLIENT_ROLES,
    "create": frozenset({"client_executor", "client_admin"}),
    "edit_draft": frozenset({"client_executor", "client_admin"}),
    "submit": frozenset({"client_executor", "client_admin"}),
    "upload_document": frozenset({"client_executor", "client_admin"}),
    "request_policy_email": frozenset({"client_executor", "client_admin"}),
    "request_policy_telegram": frozenset({"client_executor", "client_admin"}),
    "request_cancellation": frozenset({"client_executor", "client_admin"}),
    "request_change": frozenset({"client_executor", "client_admin"}),
    "approve": frozenset({"client_admin"}),
    "reject": frozenset({"client_admin"}),
    "return_for_revision": frozenset({"client_admin"}),
}
DOCUMENT_ACTION_ROLES = {
    "upload": frozenset({"client_executor", "client_admin"}),
    "read_metadata": CLIENT_ROLES,
    "download": frozenset({"client_executor", "client_admin"}),
    "request_send": frozenset({"client_executor", "client_admin"}),
}
POLICY_ACTION_ROLES = {
    "read": CLIENT_ROLES,
    "request_send": frozenset({"client_executor", "client_admin"}),
    "download": frozenset({"client_executor", "client_admin"}),
}
PARTNER_APPLICATION_ACTIONS = frozenset({"read", "create", "submit", "upload_document"})
PARTNER_DOCUMENT_ACTIONS = frozenset({"upload", "read_metadata"})
ACTIVE_STATUS = "active"
PARTNER_VISIBLE_LINK_STATUSES = frozenset({"active", "another_partner"})

SECURITY_SENSITIVE_DENIALS = {
    "company": frozenset({"create_application", "approve_application", "manage_users", "assign_role", "revoke_role"}),
    "application": frozenset(
        {
            "create",
            "edit_draft",
            "submit",
            "upload_document",
            "request_policy_email",
            "request_policy_telegram",
            "request_cancellation",
            "request_change",
            "approve",
            "reject",
            "return_for_revision",
        }
    ),
    "policy": frozenset({"request_send", "download", "request_policy_email", "request_policy_telegram"}),
    "document": frozenset({"upload", "download", "request_send"}),
}


def should_audit_denial(*, object_type: str, action: str, error_code: str) -> bool:
    if error_code.endswith("_NOT_FOUND"):
        return False
    return action in SECURITY_SENSITIVE_DENIALS.get(object_type, frozenset())


@dataclass(slots=True)
class PolicyError(Exception):
    error_code: str
    status_code: int
    object_type: str
    action: str
    object_id: str | None = None


def is_superadmin(user) -> bool:
    return bool(user and user.role_code == "superadmin" and user.status == ACTIVE_STATUS)


def _is_partner(user) -> bool:
    return bool(user and user.user_type == "partner" and user.status == ACTIVE_STATUS)


def _is_client(user) -> bool:
    return bool(user and user.user_type == "client" and user.status == ACTIVE_STATUS)


def _safe_log_access_denied(
    *,
    request: Request | None,
    user,
    object_type: str,
    object_id: str | None,
    action: str,
    error_code: str,
) -> None:
    logging.getLogger(LOGGER_NAME).warning(
        "access_denied",
        extra={
            "request_id": request_id(request) if request else None,
            "user_id": f"usr_{user.id}" if user else None,
            "object_type": object_type,
            "object_id": object_id,
            "action": action,
            "error_code": error_code,
        },
    )


def _audit_denied(
    session: Session,
    *,
    request: Request | None,
    user,
    object_type: str,
    object_id: str | None,
    action: str,
    error_code: str,
    bitrix_company_id: int | None = None,
    bitrix_deal_id: int | None = None,
) -> None:
    if request is None:
        return
    audit_event(
        session,
        action=f"{object_type}_access_denied",
        object_type=object_type,
        object_id=object_id,
        request=request,
        actor_user_id=user.id if user else None,
        bitrix_company_id=bitrix_company_id,
        application_id=int(object_id) if object_type == "application" and object_id and object_id.isdigit() else None,
        bitrix_deal_id=bitrix_deal_id,
        metadata={"reason_code": error_code, "action": action, "status": "denied"},
    )


def _deny(
    session: Session,
    *,
    request: Request | None,
    user,
    object_type: str,
    object_id: str | None,
    action: str,
    error_code: str,
    status_code: int,
    bitrix_company_id: int | None = None,
    bitrix_deal_id: int | None = None,
) -> None:
    _safe_log_access_denied(
        request=request,
        user=user,
        object_type=object_type,
        object_id=object_id,
        action=action,
        error_code=error_code,
    )
    if should_audit_denial(object_type=object_type, action=action, error_code=error_code):
        _audit_denied(
            session,
            request=request,
            user=user,
            object_type=object_type,
            object_id=object_id,
            action=action,
            error_code=error_code,
            bitrix_company_id=bitrix_company_id,
            bitrix_deal_id=bitrix_deal_id,
        )
    raise PolicyError(error_code, status_code, object_type, action, object_id)


def _company_role_for_action(
    session: Session,
    *,
    user_id: int,
    bitrix_company_id: int,
    allowed_roles: frozenset[str],
) -> str | None:
    if not allowed_roles:
        return None
    return session.execute(
        select(user_company_roles.c.role_code).where(
            user_company_roles.c.user_id == user_id,
            user_company_roles.c.bitrix_company_id == bitrix_company_id,
            user_company_roles.c.access_status == ACTIVE_STATUS,
            user_company_roles.c.role_code.in_(allowed_roles),
        )
    ).scalar_one_or_none()


def _executor_owns_application(user, application) -> bool:
    return application.created_by_user_id is None or application.created_by_user_id == user.id


def _company_role_exists(
    session: Session,
    *,
    user_id: int,
    bitrix_company_id: int,
    allowed_roles: frozenset[str],
) -> bool:
    if not allowed_roles:
        return False
    return (
        session.execute(
            select(user_company_roles.c.id).where(
                user_company_roles.c.user_id == user_id,
                user_company_roles.c.bitrix_company_id == bitrix_company_id,
                user_company_roles.c.access_status == ACTIVE_STATUS,
                user_company_roles.c.role_code.in_(allowed_roles),
            )
        ).scalar_one_or_none()
        is not None
    )


def _partner_company_link_exists(session: Session, *, user_id: int, bitrix_company_id: int) -> bool:
    return (
        session.execute(
            select(partner_client_links.c.id).where(
                partner_client_links.c.partner_user_id == user_id,
                partner_client_links.c.bitrix_company_id == bitrix_company_id,
                partner_client_links.c.status == ACTIVE_STATUS,
            )
        ).scalar_one_or_none()
        is not None
    )


def _partner_company_link_status(session: Session, *, user_id: int, bitrix_company_id: int) -> str | None:
    return session.execute(
        select(partner_client_links.c.status).where(
            partner_client_links.c.partner_user_id == user_id,
            partner_client_links.c.bitrix_company_id == bitrix_company_id,
            partner_client_links.c.status.in_(PARTNER_VISIBLE_LINK_STATUSES),
        )
    ).scalar_one_or_none()


async def get_accessible_company_ids(session: Session, user) -> list[int]:
    if not user or user.status != ACTIVE_STATUS:
        return []
    if is_superadmin(user):
        return list(
            session.execute(
                select(user_company_roles.c.bitrix_company_id)
                .where(user_company_roles.c.bitrix_company_id.not_in(SYSTEM_BITRIX_COMPANY_IDS))
                .distinct()
            ).scalars()
        )
    if _is_partner(user):
        return list(
            session.execute(
                select(partner_client_links.c.bitrix_company_id).where(
                    partner_client_links.c.partner_user_id == user.id,
                    partner_client_links.c.status == ACTIVE_STATUS,
                    partner_client_links.c.bitrix_company_id.not_in(SYSTEM_BITRIX_COMPANY_IDS),
                )
            ).scalars()
        )
    return list(
        session.execute(
            select(user_company_roles.c.bitrix_company_id)
            .where(user_company_roles.c.user_id == user.id, user_company_roles.c.access_status == ACTIVE_STATUS)
            .where(user_company_roles.c.bitrix_company_id.not_in(SYSTEM_BITRIX_COMPANY_IDS))
            .distinct()
        ).scalars()
    )


async def can_access_company(session: Session, user, bitrix_company_id: int, action: str = "read") -> bool:
    if not user or user.status != ACTIVE_STATUS:
        return False
    if is_superadmin(user):
        return True
    allowed_roles = COMPANY_ACTION_ROLES.get(action, frozenset())
    if _is_client(user):
        return _company_role_exists(
            session,
            user_id=user.id,
            bitrix_company_id=bitrix_company_id,
            allowed_roles=allowed_roles,
        )
    return (
        action == "read"
        and _is_partner(user)
        and _partner_company_link_exists(
            session,
            user_id=user.id,
            bitrix_company_id=bitrix_company_id,
        )
    )


async def require_company_access(
    session: Session,
    user,
    bitrix_company_id: int,
    action: str = "read",
    request: Request | None = None,
) -> None:
    if not await can_access_company(session, user, bitrix_company_id, action):
        _deny(
            session,
            request=request,
            user=user,
            object_type="company",
            object_id=str(bitrix_company_id),
            action=action,
            error_code="COMPANY_ACCESS_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            bitrix_company_id=bitrix_company_id,
        )


def _application_query(application_id: int | None = None, bitrix_deal_id: int | None = None) -> Select[Any]:
    query = select(portal_applications)
    if application_id is not None:
        return query.where(portal_applications.c.id == application_id)
    return query.where(portal_applications.c.bitrix_deal_id == bitrix_deal_id)


async def get_accessible_application_filter(session: Session, user) -> list[int]:
    if not user or user.status != ACTIVE_STATUS:
        return []
    if is_superadmin(user):
        return list(session.execute(select(portal_applications.c.id)).scalars())
    if _is_partner(user):
        return list(
            session.execute(
                select(portal_applications.c.id).where(
                    portal_applications.c.partner_user_id == user.id,
                    portal_applications.c.is_hidden_from_partner.is_(False),
                    exists(
                        select(partner_client_links.c.id).where(
                            partner_client_links.c.partner_user_id == user.id,
                            partner_client_links.c.bitrix_company_id == portal_applications.c.bitrix_company_id,
                            partner_client_links.c.status.in_(PARTNER_VISIBLE_LINK_STATUSES),
                        )
                    ),
                )
            ).scalars()
        )
    company_ids = await get_accessible_company_ids(session, user)
    if not company_ids:
        return []
    return list(
        session.execute(
            select(portal_applications.c.id).where(portal_applications.c.bitrix_company_id.in_(company_ids))
        ).scalars()
    )


async def can_access_application(
    session: Session,
    user,
    action: str,
    application_id: int | None = None,
    bitrix_deal_id: int | None = None,
) -> bool:
    if application_id is None and bitrix_deal_id is None:
        return False
    try:
        await require_application_access(
            session,
            user,
            action,
            application_id=application_id,
            bitrix_deal_id=bitrix_deal_id,
        )
    except PolicyError:
        return False
    return True


async def require_application_access(
    session: Session,
    user,
    action: str,
    application_id: int | None = None,
    bitrix_deal_id: int | None = None,
    request: Request | None = None,
):
    row = session.execute(_application_query(application_id, bitrix_deal_id)).mappings().one_or_none()
    object_id = str(application_id or bitrix_deal_id)
    if row is None:
        _deny(
            session,
            request=request,
            user=user,
            object_type="application",
            object_id=object_id,
            action=action,
            error_code="APPLICATION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if is_superadmin(user):
        return row
    if _is_partner(user):
        link_status = _partner_company_link_status(session, user_id=user.id, bitrix_company_id=row.bitrix_company_id)
        partner_can_act = link_status == ACTIVE_STATUS and action in PARTNER_APPLICATION_ACTIONS
        partner_can_read_limited = action == "read" and link_status in PARTNER_VISIBLE_LINK_STATUSES
        if (
            row.partner_user_id == user.id
            and not row.is_hidden_from_partner
            and (partner_can_act or partner_can_read_limited)
        ):
            return row
        _deny(
            session,
            request=request,
            user=user,
            object_type="application",
            object_id=str(row.id),
            action=action,
            error_code="PARTNER_ACCESS_DENIED",
            status_code=status.HTTP_404_NOT_FOUND if action == "read" else status.HTTP_403_FORBIDDEN,
            bitrix_company_id=row.bitrix_company_id,
            bitrix_deal_id=row.bitrix_deal_id,
        )
    allowed_roles = APPLICATION_ACTION_ROLES.get(action, frozenset())
    if _is_client(user):
        matched_role = _company_role_for_action(
            session,
            user_id=user.id,
            bitrix_company_id=row.bitrix_company_id,
            allowed_roles=allowed_roles,
        )
        if matched_role == "client_executor" and not _executor_owns_application(user, row):
            matched_role = None
        if matched_role is not None:
            return row
    masked_status = status.HTTP_404_NOT_FOUND if action == "read" else status.HTTP_403_FORBIDDEN
    _deny(
        session,
        request=request,
        user=user,
        object_type="application",
        object_id=str(row.id),
        action=action,
        error_code="APPLICATION_ACCESS_DENIED",
        status_code=masked_status,
        bitrix_company_id=row.bitrix_company_id,
        bitrix_deal_id=row.bitrix_deal_id,
    )


async def can_access_policy(
    session: Session,
    user,
    policy_id_or_application_id: int,
    action: str,
) -> bool:
    try:
        await require_policy_access(session, user, policy_id_or_application_id, action)
    except PolicyError:
        return False
    return True


async def require_policy_access(
    session: Session,
    user,
    policy_id_or_application_id: int,
    action: str,
    request: Request | None = None,
):
    if _is_partner(user) and action in {"request_send", "download"}:
        _deny(
            session,
            request=request,
            user=user,
            object_type="policy",
            object_id=str(policy_id_or_application_id),
            action=action,
            error_code="POLICY_ACCESS_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    application_action = "read" if action == "read" else "request_policy_email"
    row = await require_application_access(
        session,
        user,
        application_action,
        application_id=policy_id_or_application_id,
        request=request,
    )
    if is_superadmin(user) or _is_partner(user):
        return row
    allowed_roles = POLICY_ACTION_ROLES.get(action, frozenset())
    if _company_role_exists(
        session,
        user_id=user.id,
        bitrix_company_id=row.bitrix_company_id,
        allowed_roles=allowed_roles,
    ):
        return row
    _deny(
        session,
        request=request,
        user=user,
        object_type="policy",
        object_id=str(policy_id_or_application_id),
        action=action,
        error_code="POLICY_ACCESS_DENIED",
        status_code=status.HTTP_403_FORBIDDEN,
        bitrix_company_id=row.bitrix_company_id,
        bitrix_deal_id=row.bitrix_deal_id,
    )


async def can_access_document(session: Session, user, document_id: int, action: str) -> bool:
    try:
        await require_document_access(session, user, document_id, action)
    except PolicyError:
        return False
    return True


async def require_document_access(
    session: Session,
    user,
    document_id: int,
    action: str,
    request: Request | None = None,
):
    row = (
        session.execute(select(document_transfer_logs).where(document_transfer_logs.c.id == document_id))
        .mappings()
        .one_or_none()
    )
    if row is None:
        _deny(
            session,
            request=request,
            user=user,
            object_type="document",
            object_id=str(document_id),
            action=action,
            error_code="DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    application = (
        session.execute(select(portal_applications).where(portal_applications.c.id == row.application_id))
        .mappings()
        .one_or_none()
    )
    if application is None:
        _deny(
            session,
            request=request,
            user=user,
            object_type="document",
            object_id=str(document_id),
            action=action,
            error_code="DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if _is_partner(user):
        link_status = _partner_company_link_status(
            session,
            user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
        )
        if (
            row.is_policy_file
            or action not in PARTNER_DOCUMENT_ACTIONS
            or application.partner_user_id != user.id
            or application.is_hidden_from_partner
            or link_status != ACTIVE_STATUS
        ):
            _deny(
                session,
                request=request,
                user=user,
                object_type="document",
                object_id=str(document_id),
                action=action,
                error_code="DOCUMENT_ACCESS_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
                bitrix_company_id=application.bitrix_company_id,
                bitrix_deal_id=application.bitrix_deal_id,
            )
        return row
    allowed_roles = DOCUMENT_ACTION_ROLES.get(action, frozenset())
    if is_superadmin(user):
        return row
    if _is_client(user):
        matched_role = _company_role_for_action(
            session,
            user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            allowed_roles=allowed_roles,
        )
        if matched_role == "client_executor" and not _executor_owns_application(user, application):
            matched_role = None
        if matched_role is not None:
            return row
    _deny(
        session,
        request=request,
        user=user,
        object_type="document",
        object_id=str(document_id),
        action=action,
        error_code="DOCUMENT_ACCESS_DENIED",
        status_code=status.HTTP_403_FORBIDDEN,
        bitrix_company_id=application.bitrix_company_id,
        bitrix_deal_id=application.bitrix_deal_id,
    )


async def get_accessible_document_filter(session: Session, user) -> list[int]:
    application_ids = await get_accessible_application_filter(session, user)
    if not application_ids:
        return []
    query = select(document_transfer_logs.c.id).where(document_transfer_logs.c.application_id.in_(application_ids))
    if _is_partner(user):
        query = query.where(document_transfer_logs.c.is_policy_file.is_(False))
    return list(session.execute(query).scalars())


async def search_accessible_applications(session: Session, user, query: str | None = None) -> list[Any]:
    application_ids = await get_accessible_application_filter(session, user)
    if not application_ids:
        return []
    statement = select(portal_applications).where(portal_applications.c.id.in_(application_ids))
    normalized = (query or "").strip()
    if normalized:
        try:
            numeric_query = int(normalized)
        except ValueError:
            return []
        statement = statement.where(
            (portal_applications.c.id == numeric_query) | (portal_applications.c.bitrix_deal_id == numeric_query)
        )
    return list(session.execute(statement).mappings().all())


async def search_accessible_documents(session: Session, user, query: str | None = None) -> list[Any]:
    document_ids = await get_accessible_document_filter(session, user)
    if not document_ids:
        return []
    statement = select(document_transfer_logs).where(document_transfer_logs.c.id.in_(document_ids))
    normalized = (query or "").strip()
    if normalized:
        try:
            numeric_query = int(normalized)
        except ValueError:
            statement = statement.where(document_transfer_logs.c.bitrix_document_id == normalized)
        else:
            statement = statement.where(document_transfer_logs.c.id == numeric_query)
    return list(session.execute(statement).mappings().all())


async def require_superadmin(user) -> None:
    if not is_superadmin(user):
        raise PolicyError("SUPERADMIN_REQUIRED", status.HTTP_403_FORBIDDEN, "admin", "superadmin")


async def require_client_role(session: Session, user, bitrix_company_id: int, allowed_roles: frozenset[str]) -> None:
    if not _is_client(user) or not _company_role_exists(
        session,
        user_id=user.id,
        bitrix_company_id=bitrix_company_id,
        allowed_roles=allowed_roles,
    ):
        raise PolicyError("ACTION_NOT_ALLOWED", status.HTTP_403_FORBIDDEN, "company", "client_role")


async def require_partner_application_access(session: Session, user, application_id: int, action: str):
    row = await require_application_access(session, user, action, application_id=application_id)
    if not _is_partner(user):
        raise PolicyError("PARTNER_ACCESS_DENIED", status.HTTP_403_FORBIDDEN, "application", action)
    return row
