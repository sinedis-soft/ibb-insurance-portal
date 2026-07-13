from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import insert, or_, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event, now_utc
from app.models import (
    application_delegation_items,
    application_delegation_notifications,
    application_delegations,
    portal_applications,
    portal_users,
    user_company_roles,
    user_sessions,
)

ACTIVE_APPLICATION_STATUSES = frozenset(
    {"draft", "received", "in_review", "in_work", "submitted", "requires_assignment"}
)
FINAL_APPLICATION_STATUSES = frozenset({"cancelled", "policy_issued", "closed", "rejected"})
DELEGATE_ALLOWED_ROLES = frozenset({"client_executor", "client_admin"})
OPEN_DELEGATION_ITEM_STATUSES = ("scheduled", "active")
MAX_DELEGATION_DAYS = 30


@dataclass(slots=True)
class DelegationValidationError(Exception):
    problems: list[dict[str, str]]


def parse_app_id(value: str) -> int | None:
    raw = value.removeprefix("app_")
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def parse_user_id(value: str) -> int | None:
    raw = value.removeprefix("usr_")
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def public_delegation_id(value: int) -> str:
    return f"dlg_{value}"


def public_item_id(value: int) -> str:
    return f"dli_{value}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def revoke_sessions_for_user(session: Session, user_id: int) -> None:
    session.execute(
        update(user_sessions)
        .where(user_sessions.c.user_id == user_id, user_sessions.c.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )


def queue_delegation_notifications(
    session: Session, *, delegation_id: int, event_type: str, recipient_user_ids: list[int]
) -> None:
    for recipient_user_id in sorted(set(recipient_user_ids)):
        existing = session.execute(
            select(application_delegation_notifications.c.id).where(
                application_delegation_notifications.c.delegation_id == delegation_id,
                application_delegation_notifications.c.event_type == event_type,
                application_delegation_notifications.c.recipient_user_id == recipient_user_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.execute(
                insert(application_delegation_notifications).values(
                    delegation_id=delegation_id,
                    event_type=event_type,
                    recipient_user_id=recipient_user_id,
                )
            )


def active_company_role(session: Session, *, user_id: int, company_id: int, roles: frozenset[str]) -> str | None:
    return session.execute(
        select(user_company_roles.c.role_code).where(
            user_company_roles.c.user_id == user_id,
            user_company_roles.c.bitrix_company_id == company_id,
            user_company_roles.c.access_status == "active",
            user_company_roles.c.role_code.in_(roles),
        )
    ).scalar_one_or_none()


def user_is_active_client(session: Session, user_id: int):
    return (
        session.execute(
            select(portal_users).where(
                portal_users.c.id == user_id,
                portal_users.c.status == "active",
                portal_users.c.user_type == "client",
            )
        )
        .mappings()
        .one_or_none()
    )


def has_active_delegated_access(
    session: Session, *, user_id: int, application_id: int, action: str = "read"
) -> int | None:
    if action not in {
        "read",
        "upload_document",
        "request_policy_email",
        "request_policy_telegram",
        "request_cancellation",
        "request_change",
    }:
        return None
    now = now_utc()
    row = session.execute(
        select(application_delegations.c.id)
        .select_from(application_delegations.join(application_delegation_items))
        .where(
            application_delegations.c.delegate_user_id == user_id,
            application_delegations.c.status == "active",
            application_delegations.c.starts_at <= now,
            application_delegations.c.ends_at > now,
            application_delegation_items.c.application_id == application_id,
            application_delegation_items.c.status == "active",
        )
    ).scalar_one_or_none()
    return int(row) if row is not None else None


def active_delegation_payload(row, items: list[Any] | None = None) -> dict[str, Any]:
    return {
        "id": public_delegation_id(row.id),
        "company_id": str(row.company_id),
        "delegator_user_id": f"usr_{row.delegator_user_id}",
        "delegate_user_id": f"usr_{row.delegate_user_id}",
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "ends_at": row.ends_at.isoformat() if row.ends_at else None,
        "status": row.status,
        "reason": row.reason,
        "completion_reason": row.completion_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "items": [
            {
                "id": public_item_id(item.id),
                "application_id": f"app_{item.application_id}",
                "status": item.status,
                "access_started_at": item.access_started_at.isoformat() if item.access_started_at else None,
                "access_ended_at": item.access_ended_at.isoformat() if item.access_ended_at else None,
                "completion_reason": item.completion_reason,
            }
            for item in (items or [])
        ],
    }


def _problem(app_id: int | str, reason: str) -> dict[str, str]:
    return {"application_id": f"app_{app_id}" if isinstance(app_id, int) else str(app_id), "reason": reason}


def validate_delegation_request(
    session: Session,
    *,
    delegator_id: int,
    delegate_id: int,
    company_id: int,
    application_ids: list[int],
    starts_at: datetime,
    ends_at: datetime,
    ignore_delegation_id: int | None = None,
) -> list[dict[str, str]]:
    starts_at = _as_utc(starts_at)
    ends_at = _as_utc(ends_at)
    problems: list[dict[str, str]] = []
    now = now_utc()
    if delegator_id == delegate_id:
        problems.append(_problem("users", "delegator_equals_delegate"))
    if starts_at < now - timedelta(minutes=5):
        problems.append(_problem("period", "starts_at_in_past"))
    if ends_at <= starts_at:
        problems.append(_problem("period", "ends_at_before_starts_at"))
    if ends_at - starts_at > timedelta(days=MAX_DELEGATION_DAYS):
        problems.append(_problem("period", "max_period_exceeded"))
    if user_is_active_client(session, delegator_id) is None:
        problems.append(_problem("delegator", "delegator_not_active"))
    if user_is_active_client(session, delegate_id) is None:
        problems.append(_problem("delegate", "delegate_not_active"))
    if active_company_role(session, user_id=delegator_id, company_id=company_id, roles=DELEGATE_ALLOWED_ROLES) is None:
        problems.append(_problem("company", "delegator_company_access_denied"))
    if active_company_role(session, user_id=delegate_id, company_id=company_id, roles=DELEGATE_ALLOWED_ROLES) is None:
        problems.append(_problem("company", "delegate_not_allowed"))
    if not application_ids:
        problems.append(_problem("applications", "empty_selection"))
        return problems
    rows = (
        session.execute(select(portal_applications).where(portal_applications.c.id.in_(application_ids)))
        .mappings()
        .all()
    )
    by_id = {row.id: row for row in rows}
    for app_id in application_ids:
        row = by_id.get(app_id)
        if row is None:
            problems.append(_problem(app_id, "application_not_found"))
            continue
        if row.bitrix_company_id != company_id:
            problems.append(_problem(app_id, "different_company"))
        if row.assigned_to_user_id != delegator_id:
            problems.append(_problem(app_id, "not_current_responsible"))
        if row.portal_status in FINAL_APPLICATION_STATUSES:
            problems.append(_problem(app_id, "final_status"))
        conflict_conditions = [
            application_delegation_items.c.application_id == app_id,
            application_delegation_items.c.status.in_(OPEN_DELEGATION_ITEM_STATUSES),
            application_delegations.c.status.in_(("scheduled", "active")),
        ]
        if ignore_delegation_id is not None:
            conflict_conditions.append(application_delegations.c.id != ignore_delegation_id)
        conflict = session.execute(
            select(application_delegation_items.c.id)
            .select_from(application_delegation_items.join(application_delegations))
            .where(*conflict_conditions)
        ).scalar_one_or_none()
        if conflict is not None:
            problems.append(_problem(app_id, "delegation_conflict"))
    return problems


def create_delegation(
    session: Session,
    *,
    request: Request,
    actor,
    delegate_user_id: int,
    company_id: int,
    application_ids: list[int],
    all_active: bool,
    starts_at: datetime,
    ends_at: datetime,
    reason: str | None,
    idempotency_key: str | None,
) -> dict[str, Any]:
    starts_at = _as_utc(starts_at)
    ends_at = _as_utc(ends_at)
    if idempotency_key:
        existing = (
            session.execute(
                select(application_delegations).where(
                    application_delegations.c.created_by_user_id == actor.id,
                    application_delegations.c.idempotency_key == idempotency_key,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            items = (
                session.execute(
                    select(application_delegation_items).where(
                        application_delegation_items.c.delegation_id == existing.id
                    )
                )
                .mappings()
                .all()
            )
            return {"delegation": active_delegation_payload(existing, items), "idempotent": True}
    if all_active:
        application_ids = list(
            session.execute(
                select(portal_applications.c.id).where(
                    portal_applications.c.bitrix_company_id == company_id,
                    portal_applications.c.assigned_to_user_id == actor.id,
                    portal_applications.c.portal_status.not_in(FINAL_APPLICATION_STATUSES),
                )
            ).scalars()
        )
    application_ids = sorted(set(application_ids))
    problems = validate_delegation_request(
        session,
        delegator_id=actor.id,
        delegate_id=delegate_user_id,
        company_id=company_id,
        application_ids=application_ids,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    if problems:
        raise DelegationValidationError(problems)
    now = now_utc()
    delegation_status = "active" if starts_at <= now else "scheduled"
    delegation_id = session.execute(
        insert(application_delegations)
        .values(
            company_id=company_id,
            delegator_user_id=actor.id,
            delegate_user_id=delegate_user_id,
            starts_at=starts_at,
            ends_at=ends_at,
            status=delegation_status,
            reason=reason,
            created_by_user_id=actor.id,
            idempotency_key=idempotency_key,
        )
        .returning(application_delegations.c.id)
    ).scalar_one()
    for app_id in application_ids:
        session.execute(
            insert(application_delegation_items).values(
                delegation_id=delegation_id,
                application_id=app_id,
                status=delegation_status,
                access_started_at=now if delegation_status == "active" else None,
            )
        )
        if delegation_status == "active":
            audit_event(
                session,
                action="delegation_access_granted",
                object_type="application_delegation_item",
                object_id=str(app_id),
                request=request,
                actor_user_id=actor.id,
                target_user_id=delegate_user_id,
                bitrix_company_id=company_id,
                application_id=app_id,
                metadata={"delegation_id": delegation_id, "result": "success"},
            )
    queue_delegation_notifications(
        session,
        delegation_id=delegation_id,
        event_type="delegation_created",
        recipient_user_ids=[actor.id, delegate_user_id],
    )
    audit_event(
        session,
        action="delegation_created",
        object_type="application_delegation",
        object_id=str(delegation_id),
        request=request,
        actor_user_id=actor.id,
        target_user_id=delegate_user_id,
        bitrix_company_id=company_id,
        metadata={"application_count": len(application_ids), "status": delegation_status, "reason": reason},
    )
    if delegation_status == "active":
        queue_delegation_notifications(
            session,
            delegation_id=delegation_id,
            event_type="delegation_activated",
            recipient_user_ids=[actor.id, delegate_user_id],
        )
        audit_event(
            session,
            action="delegation_activated",
            object_type="application_delegation",
            object_id=str(delegation_id),
            request=request,
            actor_user_id=actor.id,
            target_user_id=delegate_user_id,
            bitrix_company_id=company_id,
            metadata={"application_count": len(application_ids), "result": "success"},
        )
        revoke_sessions_for_user(session, delegate_user_id)
    session.commit()
    row = (
        session.execute(select(application_delegations).where(application_delegations.c.id == delegation_id))
        .mappings()
        .one()
    )
    items = (
        session.execute(
            select(application_delegation_items).where(application_delegation_items.c.delegation_id == delegation_id)
        )
        .mappings()
        .all()
    )
    return {"delegation": active_delegation_payload(row, items)}


def expire_or_terminate_delegation(
    session: Session,
    *,
    delegation_id: int,
    actor_user_id: int | None,
    request: Request | None,
    status_value: str,
    reason: str,
) -> bool:
    row = (
        session.execute(select(application_delegations).where(application_delegations.c.id == delegation_id))
        .mappings()
        .one_or_none()
    )
    if row is None or row.status not in {"scheduled", "active"}:
        return False
    now = now_utc()
    session.execute(
        update(application_delegations)
        .where(application_delegations.c.id == delegation_id)
        .values(
            status=status_value,
            completion_reason=reason,
            cancelled_by_user_id=actor_user_id if status_value == "cancelled" else None,
            cancelled_at=now if status_value == "cancelled" else None,
        )
    )
    items = (
        session.execute(
            select(application_delegation_items).where(
                application_delegation_items.c.delegation_id == delegation_id,
                application_delegation_items.c.status.in_(OPEN_DELEGATION_ITEM_STATUSES),
            )
        )
        .mappings()
        .all()
    )
    for item in items:
        session.execute(
            update(application_delegation_items)
            .where(application_delegation_items.c.id == item.id)
            .values(status=status_value, access_ended_at=now, completion_reason=reason)
        )
        audit_event(
            session,
            action="delegation_access_revoked",
            object_type="application_delegation_item",
            object_id=str(item.id),
            request=request,
            actor_user_id=actor_user_id,
            target_user_id=row.delegate_user_id,
            bitrix_company_id=row.company_id,
            application_id=item.application_id,
            metadata={"delegation_id": delegation_id, "reason": reason},
        )
    audit_action = {
        "cancelled": "delegation_cancelled",
        "expired": "delegation_expired",
        "terminated": "delegation_terminated",
        "failed": "delegation_activation_failed",
    }.get(status_value, "delegation_terminated")
    queue_delegation_notifications(
        session,
        delegation_id=delegation_id,
        event_type=audit_action,
        recipient_user_ids=[row.delegator_user_id, row.delegate_user_id],
    )
    audit_event(
        session,
        action=audit_action,
        object_type="application_delegation",
        object_id=str(delegation_id),
        request=request,
        actor_user_id=actor_user_id,
        target_user_id=row.delegate_user_id,
        bitrix_company_id=row.company_id,
        metadata={
            "delegator_user_id": row.delegator_user_id,
            "delegate_user_id": row.delegate_user_id,
            "reason": reason,
            "item_count": len(items),
        },
    )
    revoke_sessions_for_user(session, row.delegate_user_id)
    return True


def run_delegation_worker(session: Session, *, request: Request | None = None) -> dict[str, int]:
    now = now_utc()
    activated = 0
    expired = 0
    scheduled = (
        session.execute(
            select(application_delegations).where(
                application_delegations.c.status == "scheduled", application_delegations.c.starts_at <= now
            )
        )
        .mappings()
        .all()
    )
    for row in scheduled:
        items = (
            session.execute(
                select(application_delegation_items).where(application_delegation_items.c.delegation_id == row.id)
            )
            .mappings()
            .all()
        )
        problems = validate_delegation_request(
            session,
            delegator_id=row.delegator_user_id,
            delegate_id=row.delegate_user_id,
            company_id=row.company_id,
            application_ids=[item.application_id for item in items],
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            ignore_delegation_id=row.id,
        )
        if _as_utc(row.ends_at) <= now or problems:
            expire_or_terminate_delegation(
                session,
                delegation_id=row.id,
                actor_user_id=None,
                request=request,
                status_value="failed",
                reason="activation_validation_failed",
            )
            continue
        session.execute(
            update(application_delegations)
            .where(application_delegations.c.id == row.id)
            .values(status="active", activated_notification_sent_at=now)
        )
        session.execute(
            update(application_delegation_items)
            .where(
                application_delegation_items.c.delegation_id == row.id,
                application_delegation_items.c.status == "scheduled",
            )
            .values(status="active", access_started_at=now)
        )
        for item in items:
            audit_event(
                session,
                action="delegation_access_granted",
                object_type="application_delegation_item",
                object_id=str(item.id),
                request=request,
                actor_user_id=row.delegator_user_id,
                target_user_id=row.delegate_user_id,
                bitrix_company_id=row.company_id,
                application_id=item.application_id,
                metadata={"delegation_id": row.id, "result": "success"},
            )
        queue_delegation_notifications(
            session,
            delegation_id=row.id,
            event_type="delegation_activated",
            recipient_user_ids=[row.delegator_user_id, row.delegate_user_id],
        )
        audit_event(
            session,
            action="delegation_activated",
            object_type="application_delegation",
            object_id=str(row.id),
            request=request,
            actor_user_id=row.delegator_user_id,
            target_user_id=row.delegate_user_id,
            bitrix_company_id=row.company_id,
            metadata={"application_count": len(items), "result": "success"},
        )
        revoke_sessions_for_user(session, row.delegate_user_id)
        activated += 1
    active = (
        session.execute(
            select(application_delegations).where(
                application_delegations.c.status == "active", application_delegations.c.ends_at <= now
            )
        )
        .mappings()
        .all()
    )
    for row in active:
        if expire_or_terminate_delegation(
            session,
            delegation_id=row.id,
            actor_user_id=None,
            request=request,
            status_value="expired",
            reason="ends_at_reached",
        ):
            expired += 1
    session.commit()
    return {"activated": activated, "expired": expired}


def terminate_delegations_for_user(
    session: Session, *, user_id: int, reason: str, request: Request | None = None, actor_user_id: int | None = None
) -> int:
    rows = (
        session.execute(
            select(application_delegations.c.id).where(
                application_delegations.c.status.in_(("scheduled", "active")),
                or_(
                    application_delegations.c.delegator_user_id == user_id,
                    application_delegations.c.delegate_user_id == user_id,
                ),
            )
        )
        .scalars()
        .all()
    )
    count = 0
    for delegation_id in rows:
        if expire_or_terminate_delegation(
            session,
            delegation_id=delegation_id,
            actor_user_id=actor_user_id,
            request=request,
            status_value="terminated",
            reason=reason,
        ):
            count += 1
    return count
