from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import Request
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event
from app.document_transfer import safe_unlink_storage_key
from app.integrations.bitrix import (
    Bitrix24AuthError,
    Bitrix24Error,
    Bitrix24PermissionError,
    Bitrix24RateLimitError,
    Bitrix24TimeoutError,
    Bitrix24TransportError,
    Bitrix24ValidationError,
    get_bitrix24_client,
)
from app.integrations.bitrix.field_mapping import BITRIX_POLICY_FIELDS
from app.models import bitrix_stage_mappings, document_transfer_logs, portal_applications, portal_policies

ACTIVE_SYNC_STATUSES = {
    "received",
    "sent_to_work",
    "in_work",
    "documents_expected",
    "payment_expected",
    "insurer_review",
    "policy_issuing",
    "policy_issued",
    "submit_error",
}
POLICY_ISSUED_STATUSES = {"policy_issued"}


@dataclass(slots=True)
class SyncResult:
    application_id: int
    status: str
    updated: bool = False
    skipped: bool = False
    bitrix_deal_id: int | None = None
    portal_status: str | None = None
    error_code: str | None = None
    warning_code: str | None = None


@dataclass(slots=True)
class SyncSummary:
    status: str
    processed: int
    updated: int
    failed: int
    skipped: int


def _is_todo_field(field_code: str | None) -> bool:
    return not field_code or field_code.endswith("_TODO")


def _deal_value(deal: dict[str, Any], logical_name: str) -> Any:
    field_code = BITRIX_POLICY_FIELDS.get(logical_name)
    if _is_todo_field(field_code):
        return None
    return deal.get(field_code)


def _date_value(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _decimal_value(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _first_file_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, list):
        for item in value:
            file_id = _first_file_id(item)
            if file_id:
                return file_id
        return None
    if isinstance(value, dict):
        for key in ("ID", "id", "FILE_ID", "fileId", "VALUE", "value"):
            raw = value.get(key)
            if raw:
                return str(raw)
        return None
    return str(value)


def normalize_bitrix_sync_error(exc: Bitrix24Error) -> tuple[str, bool]:
    if isinstance(exc, Bitrix24AuthError) or exc.error_code == "NO_AUTH_FOUND":
        return "BITRIX24_NO_AUTH_FOUND", False
    if isinstance(exc, Bitrix24PermissionError) or exc.error_code in {"Access denied", "ACCESS_DENIED"}:
        return "BITRIX24_ACCESS_DENIED", False
    if isinstance(exc, Bitrix24RateLimitError) or exc.error_code == "QUERY_LIMIT_EXCEEDED":
        return "BITRIX24_QUERY_LIMIT_EXCEEDED", True
    if isinstance(exc, (Bitrix24TimeoutError, Bitrix24TransportError)):
        return exc.error_code, True
    if exc.error_code == "OPERATION_TIME_LIMIT":
        return "BITRIX24_OPERATION_TIME_LIMIT", True
    if isinstance(exc, Bitrix24ValidationError):
        return exc.error_code, False
    return exc.error_code or "BITRIX_SYNC_FAILED", False


def _stage_mapping(session: Session, category_id: int, stage_id: str):
    return (
        session.execute(
            select(bitrix_stage_mappings).where(
                bitrix_stage_mappings.c.bitrix_category_id == category_id,
                bitrix_stage_mappings.c.bitrix_stage_id == stage_id,
            )
        )
        .mappings()
        .one_or_none()
    )


def _policy_payload(application, deal: dict[str, Any]) -> dict[str, Any] | None:
    policy_number = _deal_value(deal, "policy_number")
    product = _deal_value(deal, "product") or application.product_type_code
    insurer = _deal_value(deal, "insurer")
    valid_from = _date_value(_deal_value(deal, "policy_start_date"))
    valid_to = _date_value(_deal_value(deal, "policy_end_date"))
    premium = _decimal_value(_deal_value(deal, "premium"))
    currency = _deal_value(deal, "premium_currency")
    policy_file_id = _first_file_id(_deal_value(deal, "policy_document"))
    if not all([policy_number, product, insurer, valid_from, valid_to, premium is not None, currency, policy_file_id]):
        return None
    return {
        "policy_number": str(policy_number),
        "product_type_code": str(product),
        "insurer_name": str(insurer),
        "valid_from": valid_from,
        "valid_to": valid_to,
        "premium_amount": premium,
        "premium_currency": str(currency),
        "policy_file_id": policy_file_id,
    }


def _upsert_policy_document(session: Session, application, policy_file_id: str) -> int:
    existing = (
        session.execute(
            select(document_transfer_logs).where(
                document_transfer_logs.c.application_id == application.id,
                document_transfer_logs.c.bitrix_file_id == policy_file_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        safe_unlink_storage_key(existing.storage_key)
        session.execute(
            update(document_transfer_logs)
            .where(document_transfer_logs.c.id == existing.id)
            .values(
                document_type="policy_file",
                is_policy_file=True,
                storage_provider="bitrix",
                storage_key=None,
                temporary_storage_path=None,
                transfer_status="sent",
                bitrix_deal_id=application.bitrix_deal_id,
                local_deleted_at=func.now() if existing.storage_key else existing.local_deleted_at,
                updated_at=func.now(),
            )
        )
        return int(existing.id)
    return session.execute(
        insert(document_transfer_logs)
        .values(
            application_id=application.id,
            bitrix_company_id=application.bitrix_company_id,
            bitrix_document_id=policy_file_id,
            document_type="policy_file",
            is_policy_file=True,
            storage_provider="bitrix",
            transfer_status="sent",
            bitrix_file_id=policy_file_id,
            bitrix_deal_id=application.bitrix_deal_id,
            transferred_at=func.now(),
        )
        .returning(document_transfer_logs.c.id)
    ).scalar_one()


def _upsert_policy_cache(session: Session, application, payload: dict[str, Any], document_id: int) -> int:
    existing = (
        session.execute(
            select(portal_policies).where(
                portal_policies.c.application_id == application.id,
                portal_policies.c.bitrix_deal_id == application.bitrix_deal_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    values = {
        "application_id": application.id,
        "bitrix_deal_id": application.bitrix_deal_id,
        "bitrix_company_id": application.bitrix_company_id,
        "policy_number": payload["policy_number"],
        "product_type_code": payload["product_type_code"],
        "insurer_name": payload["insurer_name"],
        "valid_from": payload["valid_from"],
        "valid_to": payload["valid_to"],
        "premium_amount": payload["premium_amount"],
        "premium_currency": payload["premium_currency"],
        "policy_status": "active",
        "document_transfer_log_id": document_id,
        "last_synced_at": func.now(),
    }
    if existing is None:
        return session.execute(insert(portal_policies).values(**values).returning(portal_policies.c.id)).scalar_one()
    session.execute(update(portal_policies).where(portal_policies.c.id == existing.id).values(**values))
    return int(existing.id)


async def sync_policy_from_deal(
    session: Session,
    application,
    deal: dict[str, Any],
    *,
    request: Request | None = None,
    actor_user_id: int | None = None,
) -> tuple[int | None, str | None]:
    payload = _policy_payload(application, deal)
    if payload is None:
        audit_event(
            session,
            action="policy_data_incomplete",
            object_type="application",
            object_id=str(application.id),
            request=request,
            actor_user_id=actor_user_id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application.id,
            bitrix_deal_id=application.bitrix_deal_id,
            metadata={"reason_code": "POLICY_DATA_INCOMPLETE"},
        )
        return None, "POLICY_DATA_INCOMPLETE"
    document_id = _upsert_policy_document(session, application, payload["policy_file_id"])
    policy_id = _upsert_policy_cache(session, application, payload, document_id)
    audit_event(
        session,
        action="policy_cache_updated",
        object_type="policy",
        object_id=str(policy_id),
        request=request,
        actor_user_id=actor_user_id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application.id,
        bitrix_deal_id=application.bitrix_deal_id,
        metadata={"policy_id": policy_id, "document_id": document_id},
    )
    audit_event(
        session,
        action="document_metadata_synced",
        object_type="document",
        object_id=str(document_id),
        request=request,
        actor_user_id=actor_user_id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application.id,
        bitrix_deal_id=application.bitrix_deal_id,
        metadata={"document_id": document_id},
    )
    return policy_id, None


async def sync_application_from_bitrix(
    session: Session,
    application_id: int,
    *,
    request: Request | None = None,
    actor_user_id: int | None = None,
    client=None,
) -> SyncResult:
    application = (
        session.execute(select(portal_applications).where(portal_applications.c.id == application_id))
        .mappings()
        .one_or_none()
    )
    if application is None or not application.bitrix_deal_id:
        return SyncResult(application_id=application_id, status="skipped", skipped=True)
    b24 = client or get_bitrix24_client()
    audit_event(
        session,
        action="bitrix_sync_started",
        object_type="application",
        object_id=str(application.id),
        request=request,
        actor_user_id=actor_user_id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application.id,
        bitrix_deal_id=application.bitrix_deal_id,
        metadata={"sync_status": "pending"},
    )
    try:
        deal = await b24.get_deal(int(application.bitrix_deal_id))
    except Bitrix24Error as exc:
        error_code, retryable = normalize_bitrix_sync_error(exc)
        sync_status = "retry_required" if retryable else "sync_error"
        session.execute(
            update(portal_applications)
            .where(portal_applications.c.id == application.id)
            .values(sync_status=sync_status, last_sync_error_code=error_code, last_synced_at=func.now())
        )
        audit_event(
            session,
            action="bitrix_sync_failed",
            object_type="application",
            object_id=str(application.id),
            request=request,
            actor_user_id=actor_user_id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application.id,
            bitrix_deal_id=application.bitrix_deal_id,
            metadata={"sync_status": sync_status, "reason_code": error_code},
        )
        if retryable:
            audit_event(
                session,
                action="bitrix_retry_scheduled",
                object_type="application",
                object_id=str(application.id),
                request=request,
                actor_user_id=actor_user_id,
                bitrix_company_id=application.bitrix_company_id,
                application_id=application.id,
                bitrix_deal_id=application.bitrix_deal_id,
                metadata={"reason_code": error_code},
            )
        session.commit()
        return SyncResult(
            application_id=application.id,
            status="failed",
            bitrix_deal_id=application.bitrix_deal_id,
            error_code=error_code,
        )

    stage_id = str(deal.get("STAGE_ID") or "")
    category_id = int(deal.get("CATEGORY_ID") or application.bitrix_category_id or 0)
    mapping = _stage_mapping(session, category_id, stage_id) if stage_id else None
    mapped_status = mapping.portal_status if mapping is not None else application.portal_status
    warning_code = None
    if mapped_status in POLICY_ISSUED_STATUSES:
        _policy_id, warning_code = await sync_policy_from_deal(
            session,
            application,
            deal,
            request=request,
            actor_user_id=actor_user_id,
        )
        if warning_code:
            mapped_status = "policy_issuing"

    session.execute(
        update(portal_applications)
        .where(portal_applications.c.id == application.id)
        .values(
            portal_status=mapped_status,
            bitrix_category_id=category_id,
            bitrix_stage_id=stage_id or application.bitrix_stage_id,
            sync_status="synced",
            last_sync_error_code=None,
            last_sync_warning_code=warning_code,
            last_synced_at=func.now(),
        )
    )
    if mapped_status != application.portal_status:
        audit_event(
            session,
            action="portal_status_updated_from_bitrix",
            object_type="application",
            object_id=str(application.id),
            request=request,
            actor_user_id=actor_user_id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application.id,
            bitrix_deal_id=application.bitrix_deal_id,
            metadata={"old_portal_status": application.portal_status, "new_portal_status": mapped_status},
        )
    audit_event(
        session,
        action="bitrix_sync_finished",
        object_type="application",
        object_id=str(application.id),
        request=request,
        actor_user_id=actor_user_id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application.id,
        bitrix_deal_id=application.bitrix_deal_id,
        metadata={"sync_status": "synced", "new_portal_status": mapped_status},
    )
    session.commit()
    return SyncResult(
        application_id=application.id,
        status="ok",
        updated=True,
        bitrix_deal_id=application.bitrix_deal_id,
        portal_status=mapped_status,
        warning_code=warning_code,
    )


async def sync_active_applications(
    session: Session,
    *,
    request: Request | None = None,
    actor_user_id: int | None = None,
    client=None,
    limit: int = 50,
) -> SyncSummary:
    application_ids = list(
        session.execute(
            select(portal_applications.c.id)
            .where(
                portal_applications.c.bitrix_deal_id.is_not(None),
                portal_applications.c.portal_status.in_(ACTIVE_SYNC_STATUSES),
            )
            .order_by(portal_applications.c.updated_at.asc(), portal_applications.c.id.asc())
            .limit(limit)
        ).scalars()
    )
    processed = updated = failed = skipped = 0
    for application_id in application_ids:
        result = await sync_application_from_bitrix(
            session,
            int(application_id),
            request=request,
            actor_user_id=actor_user_id,
            client=client,
        )
        processed += 1
        updated += int(result.updated)
        failed += int(result.status == "failed")
        skipped += int(result.skipped)
    return SyncSummary(status="ok", processed=processed, updated=updated, failed=failed, skipped=skipped)


def sync_error_rows(session: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        session.execute(
            select(
                portal_applications.c.id,
                portal_applications.c.bitrix_deal_id,
                portal_applications.c.sync_status,
                portal_applications.c.last_sync_error_code,
                portal_applications.c.last_sync_warning_code,
                portal_applications.c.last_synced_at,
            )
            .where(
                (portal_applications.c.sync_status.in_(("sync_error", "retry_required")))
                | (portal_applications.c.last_sync_warning_code.is_not(None))
            )
            .order_by(portal_applications.c.updated_at.desc(), portal_applications.c.id.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    return [
        {
            "application_id": f"app_{row.id}",
            "bitrix_deal_id": row.bitrix_deal_id,
            "sync_status": row.sync_status,
            "error_code": row.last_sync_error_code,
            "warning_code": row.last_sync_warning_code,
            "last_attempt_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        }
        for row in rows
    ]
