from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event
from app.bitrix import BitrixError
from app.document_transfer import queue_application_documents
from app.models import application_submit_attempts, portal_applications

CreateDeal = Callable[[dict[str, Any]], Awaitable[int]]
FindDeal = Callable[[int | str], Awaitable[int | None]]

SUBMIT_ALLOWED_STATUSES = {"draft", "returned_for_revision", "submit_error"}


def _safe_metadata(base_metadata: dict[str, Any], *, reason_code: str | None = None) -> dict[str, Any]:
    metadata = dict(base_metadata)
    if reason_code:
        metadata["reason_code"] = reason_code
    return metadata


def _next_attempt_no(session: Session, application_id: int) -> int:
    current = session.execute(
        select(func.max(application_submit_attempts.c.attempt_no)).where(
            application_submit_attempts.c.application_id == application_id
        )
    ).scalar_one()
    return int(current or 0) + 1


def _has_previous_attempt(session: Session, application_id: int) -> bool:
    return bool(
        session.execute(
            select(application_submit_attempts.c.id)
            .where(application_submit_attempts.c.application_id == application_id)
            .limit(1)
        ).first()
    )


def _create_attempt(session: Session, application_id: int) -> int:
    attempt_no = _next_attempt_no(session, application_id)
    return session.execute(
        application_submit_attempts.insert()
        .values(
            application_id=application_id,
            attempt_no=attempt_no,
            idempotency_key=f"application:{application_id}:submit:{attempt_no}",
            status="started",
        )
        .returning(application_submit_attempts.c.id)
    ).scalar_one()


def _finish_attempt(
    session: Session,
    attempt_id: int,
    *,
    status: str,
    bitrix_deal_id: int | None = None,
    error_code: str | None = None,
) -> None:
    session.execute(
        update(application_submit_attempts)
        .where(application_submit_attempts.c.id == attempt_id)
        .values(
            status=status,
            bitrix_deal_id=bitrix_deal_id,
            error_code=error_code,
            finished_at=func.now(),
        )
    )


def _lock_application(session: Session, application_id: int):
    return (
        session.execute(
            select(portal_applications).where(portal_applications.c.id == application_id).with_for_update()
        )
        .mappings()
        .one()
    )


def _mark_received(session: Session, application_id: int, *, deal_id: int, category_id: int | None = None) -> None:
    values: dict[str, Any] = {
        "bitrix_deal_id": deal_id,
        "portal_status": "received",
        "submitted_at": func.now(),
        "last_synced_at": func.now(),
    }
    if category_id is not None:
        values["bitrix_category_id"] = category_id
    session.execute(update(portal_applications).where(portal_applications.c.id == application_id).values(**values))


def _mark_submit_error(session: Session, application_id: int) -> None:
    session.execute(
        update(portal_applications)
        .where(portal_applications.c.id == application_id)
        .values(portal_status="submit_error", last_synced_at=func.now())
    )


def _response(application_id: int, deal_id: int) -> dict[str, Any]:
    return {
        "status": "ok",
        "id": f"app_{application_id}",
        "portal_status": "received",
        "bitrix_deal_id": deal_id,
    }


async def submit_application_to_bitrix(
    *,
    session: Session,
    request: Request,
    application_id: int,
    user: Any,
    application_type: str,
    deal_fields: dict[str, Any],
    safe_metadata: dict[str, Any],
    create_deal: CreateDeal,
    find_deal_by_portal_application_id: FindDeal,
    category_id: int | None = None,
) -> dict[str, Any]:
    application = _lock_application(session, application_id)
    if application.bitrix_deal_id:
        queue_application_documents(session, application_id=application_id, bitrix_deal_id=application.bitrix_deal_id)
        audit_event(
            session,
            action="duplicate_submit_prevented",
            object_type="application",
            object_id=str(application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application_id,
            bitrix_deal_id=application.bitrix_deal_id,
            metadata=_safe_metadata(safe_metadata),
        )
        session.commit()
        return _response(application_id, application.bitrix_deal_id)

    if application.portal_status == "submitting":
        session.commit()
        return {"status": "sync_error", "error_code": "APPLICATION_SUBMIT_IN_PROGRESS"}
    if application.portal_status not in SUBMIT_ALLOWED_STATUSES:
        session.commit()
        return {"status": "sync_error", "error_code": "APPLICATION_ALREADY_SUBMITTED"}

    should_lookup_existing = _has_previous_attempt(session, application_id)
    attempt_id = _create_attempt(session, application_id)
    session.execute(
        update(portal_applications)
        .where(portal_applications.c.id == application_id)
        .values(portal_status="submitting", last_synced_at=func.now())
    )
    audit_event(
        session,
        action=f"{application_type}_application_submit_started",
        object_type="application",
        object_id=str(application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application_id,
        metadata=_safe_metadata(safe_metadata),
    )

    if should_lookup_existing:
        audit_event(
            session,
            action="bitrix_deal_lookup_started",
            object_type="application",
            object_id=str(application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application_id,
            metadata=_safe_metadata(safe_metadata),
        )
        try:
            existing_deal_id = await find_deal_by_portal_application_id(application_id)
        except BitrixError as exc:
            _mark_submit_error(session, application_id)
            _finish_attempt(session, attempt_id, status="retry_required", error_code="BITRIX_DEAL_LOOKUP_FAILED")
            audit_event(
                session,
                action=f"{application_type}_application_submit_failed",
                object_type="application",
                object_id=str(application_id),
                request=request,
                actor_user_id=user.id,
                bitrix_company_id=application.bitrix_company_id,
                application_id=application_id,
                metadata=_safe_metadata(safe_metadata, reason_code=exc.error_code),
            )
            session.commit()
            return {"status": "sync_error", "error_code": "BITRIX_DEAL_LOOKUP_FAILED"}
        if existing_deal_id:
            _mark_received(session, application_id, deal_id=existing_deal_id, category_id=category_id)
            queue_application_documents(session, application_id=application_id, bitrix_deal_id=existing_deal_id)
            _finish_attempt(session, attempt_id, status="succeeded", bitrix_deal_id=existing_deal_id)
            audit_event(
                session,
                action="bitrix_deal_lookup_found_existing",
                object_type="application",
                object_id=str(application_id),
                request=request,
                actor_user_id=user.id,
                bitrix_company_id=application.bitrix_company_id,
                application_id=application_id,
                bitrix_deal_id=existing_deal_id,
                metadata=_safe_metadata(safe_metadata),
            )
            audit_event(
                session,
                action=f"{application_type}_application_submitted",
                object_type="application",
                object_id=str(application_id),
                request=request,
                actor_user_id=user.id,
                bitrix_company_id=application.bitrix_company_id,
                application_id=application_id,
                bitrix_deal_id=existing_deal_id,
                metadata=_safe_metadata(safe_metadata),
            )
            session.commit()
            return _response(application_id, existing_deal_id)

    try:
        audit_event(
            session,
            action="bitrix_deal_create_started",
            object_type="application",
            object_id=str(application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application_id,
            metadata=_safe_metadata(safe_metadata),
        )
        deal_id = await create_deal(deal_fields)
    except BitrixError as exc:
        _mark_submit_error(session, application_id)
        _finish_attempt(session, attempt_id, status="retry_required", error_code="BITRIX_DEAL_CREATE_FAILED")
        audit_event(
            session,
            action="bitrix_deal_create_failed",
            object_type="application",
            object_id=str(application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application_id,
            metadata=_safe_metadata(safe_metadata, reason_code=exc.error_code),
        )
        audit_event(
            session,
            action=f"{application_type}_application_submit_failed",
            object_type="application",
            object_id=str(application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application_id,
            metadata=_safe_metadata(safe_metadata, reason_code=exc.error_code),
        )
        session.commit()
        return {"status": "sync_error", "error_code": "BITRIX_DEAL_CREATE_FAILED"}

    _mark_received(session, application_id, deal_id=deal_id, category_id=category_id)
    queue_application_documents(session, application_id=application_id, bitrix_deal_id=deal_id)
    _finish_attempt(session, attempt_id, status="succeeded", bitrix_deal_id=deal_id)
    audit_event(
        session,
        action="bitrix_deal_created",
        object_type="application",
        object_id=str(application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application_id,
        bitrix_deal_id=deal_id,
        metadata=_safe_metadata(safe_metadata),
    )
    audit_event(
        session,
        action="documents_queued_for_transfer",
        object_type="application",
        object_id=str(application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application_id,
        bitrix_deal_id=deal_id,
        metadata=_safe_metadata(safe_metadata),
    )
    audit_event(
        session,
        action=f"{application_type}_application_submitted",
        object_type="application",
        object_id=str(application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application_id,
        bitrix_deal_id=deal_id,
        metadata=_safe_metadata(safe_metadata),
    )
    session.commit()
    return _response(application_id, deal_id)
