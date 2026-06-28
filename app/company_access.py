from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import user_company_roles

CLIENT_COMPANY_ROLES = frozenset({"client_executor", "client_admin", "client_viewer"})
ACTIVE_ACCESS_STATUSES = frozenset({"active"})
OPEN_ACCESS_STATUSES = frozenset({"active", "pending"})


def is_superadmin(user) -> bool:
    return bool(user and user.role_code == "superadmin")


def normalize_company_id(value: int | str) -> int | None:
    try:
        company_id = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return company_id if company_id > 0 else None


def get_accessible_company_ids(session: Session, user_id: int) -> list[int]:
    return list(
        session.execute(
            select(user_company_roles.c.bitrix_company_id).where(
                user_company_roles.c.user_id == user_id,
                user_company_roles.c.access_status == "active",
            )
        ).scalars()
    )


def can_access_company(
    session: Session,
    user_id: int,
    bitrix_company_id: int | str,
    allowed_roles: Iterable[str] | None = None,
) -> bool:
    company_id = normalize_company_id(bitrix_company_id)
    if company_id is None:
        return False
    conditions = [
        user_company_roles.c.user_id == user_id,
        user_company_roles.c.bitrix_company_id == company_id,
        user_company_roles.c.access_status == "active",
    ]
    if allowed_roles is not None:
        conditions.append(user_company_roles.c.role_code.in_(set(allowed_roles)))
    return session.execute(select(user_company_roles.c.id).where(*conditions)).scalar_one_or_none() is not None


def require_company_access(
    session: Session,
    user,
    bitrix_company_id: int | str,
    allowed_roles: Iterable[str] | None = None,
) -> None:
    if not can_access_company(session, user.id, bitrix_company_id, allowed_roles):
        raise PermissionError("COMPANY_ACCESS_DENIED")
