from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event, now_utc
from app.bitrix import BitrixError, call_bitrix_method
from app.config import get_settings
from app.models import document_transfer_logs, portal_applications

UPLOAD_ALLOWED_STATUSES = {
    "draft",
    "returned_for_revision",
    "approval_pending",
    "sent_to_work",
    "in_work",
    "documents_expected",
    "payment_expected",
    "policy_issuing",
}
DELETE_ALLOWED_STATUSES = {"draft", "returned_for_revision"}
REQUIRED_DOCUMENT_STATUSES = ("uploaded", "transferring", "sent", "retry_required")
QUEUE_STATUSES = ("uploaded", "retry_required")
EXPIRE_STATUSES = ("uploaded", "failed", "retry_required")
SENT_STATUS = "sent"

Uploader = Callable[[Any, Any, Path], Awaitable[str]]


def storage_path(storage_key: str) -> Path:
    return Path(get_settings().document_temp_storage_path) / storage_key


def safe_unlink_storage_key(storage_key: str | None) -> bool:
    if not storage_key:
        return False
    root = Path(get_settings().document_temp_storage_path).resolve()
    path = (root / storage_key).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return False
    if not path.exists() or not path.is_file():
        return False
    path.unlink()
    return True


def queue_application_documents(session: Session, *, application_id: int, bitrix_deal_id: int) -> None:
    session.execute(
        update(document_transfer_logs)
        .where(
            document_transfer_logs.c.application_id == application_id,
            document_transfer_logs.c.transfer_status.in_(QUEUE_STATUSES),
        )
        .values(bitrix_deal_id=bitrix_deal_id, updated_at=func.now())
    )


async def upload_document_to_bitrix(document_row, application_row, file_path: Path) -> str:
    settings = get_settings()
    if settings.bitrix_document_folder_id is None:
        raise BitrixError("BITRIX_DOCUMENT_FOLDER_NOT_CONFIGURED")
    extension = file_path.suffix.lower() or ".bin"
    bitrix_name = f"portal-document-{document_row.id}{extension}"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    result = await call_bitrix_method(
        "disk.folder.uploadfile",
        {
            "id": settings.bitrix_document_folder_id,
            "data": {"NAME": bitrix_name},
            "fileContent": [bitrix_name, encoded],
            "generateUniqueName": True,
        },
    )
    bitrix_file_id = result.get("ID") or result.get("FILE_ID")
    if not bitrix_file_id:
        raise BitrixError("BITRIX_UNEXPECTED_RESPONSE")
    return str(bitrix_file_id)


async def process_document_transfer_queue(
    session: Session,
    *,
    request: Request | None = None,
    uploader: Uploader | None = None,
    limit: int = 20,
) -> int:
    upload = uploader or upload_document_to_bitrix
    document_ids = list(
        session.execute(
            select(document_transfer_logs.c.id)
            .join(portal_applications, portal_applications.c.id == document_transfer_logs.c.application_id)
            .where(
                document_transfer_logs.c.transfer_status.in_(QUEUE_STATUSES),
                document_transfer_logs.c.bitrix_deal_id.is_not(None),
                portal_applications.c.bitrix_deal_id == document_transfer_logs.c.bitrix_deal_id,
                document_transfer_logs.c.local_deleted_at.is_(None),
            )
            .order_by(document_transfer_logs.c.created_at.asc(), document_transfer_logs.c.id.asc())
            .limit(limit)
        )
        .scalars()
    )
    processed = 0
    for document_id in document_ids:
        document_row = (
            session.execute(select(document_transfer_logs).where(document_transfer_logs.c.id == document_id))
            .mappings()
            .one()
        )
        application_row = (
            session.execute(select(portal_applications).where(portal_applications.c.id == document_row.application_id))
            .mappings()
            .one()
        )
        now = now_utc()
        session.execute(
            update(document_transfer_logs)
            .where(document_transfer_logs.c.id == document_id)
            .values(transfer_status="transferring", transfer_started_at=now, updated_at=func.now())
        )
        audit_event(
            session,
            action="document_transfer_started",
            object_type="document",
            object_id=str(document_id),
            request=request,
            actor_user_id=None,
            bitrix_company_id=document_row.bitrix_company_id,
            application_id=document_row.application_id,
            bitrix_deal_id=document_row.bitrix_deal_id,
            metadata={"document_id": document_id, "transfer_status": "transferring"},
        )
        session.flush()

        try:
            if not document_row.storage_key:
                raise BitrixError("DOCUMENT_DOWNLOAD_NOT_AVAILABLE")
            path = storage_path(document_row.storage_key)
            if not path.exists() or not path.is_file():
                raise BitrixError("DOCUMENT_DOWNLOAD_NOT_AVAILABLE")
            bitrix_file_id = await upload(document_row, application_row, path)
        except Exception as exc:
            error_code = getattr(exc, "error_code", "DOCUMENT_TRANSFER_FAILED")
            retry_count = int(document_row.retry_count or 0) + 1
            session.execute(
                update(document_transfer_logs)
                .where(document_transfer_logs.c.id == document_id)
                .values(
                    transfer_status="retry_required" if retry_count < 3 else "failed",
                    retry_count=retry_count,
                    last_error_code=error_code,
                    updated_at=func.now(),
                )
            )
            audit_event(
                session,
                action="document_transfer_failed",
                object_type="document",
                object_id=str(document_id),
                request=request,
                actor_user_id=None,
                bitrix_company_id=document_row.bitrix_company_id,
                application_id=document_row.application_id,
                bitrix_deal_id=document_row.bitrix_deal_id,
                metadata={"document_id": document_id, "error_code": error_code},
            )
            processed += 1
            continue

        deleted = safe_unlink_storage_key(document_row.storage_key)
        completed_at = now_utc()
        session.execute(
            update(document_transfer_logs)
            .where(document_transfer_logs.c.id == document_id)
            .values(
                transfer_status=SENT_STATUS,
                bitrix_file_id=bitrix_file_id,
                transferred_at=completed_at,
                local_deleted_at=completed_at if deleted else document_row.local_deleted_at,
                last_error_code=None,
                updated_at=func.now(),
            )
        )
        audit_event(
            session,
            action="document_transferred_to_bitrix",
            object_type="document",
            object_id=str(document_id),
            request=request,
            actor_user_id=None,
            bitrix_company_id=document_row.bitrix_company_id,
            application_id=document_row.application_id,
            bitrix_deal_id=document_row.bitrix_deal_id,
            metadata={"document_id": document_id, "transfer_status": SENT_STATUS},
        )
        if deleted:
            audit_event(
                session,
                action="document_temporary_file_deleted",
                object_type="document",
                object_id=str(document_id),
                request=request,
                actor_user_id=None,
                bitrix_company_id=document_row.bitrix_company_id,
                application_id=document_row.application_id,
                bitrix_deal_id=document_row.bitrix_deal_id,
                metadata={"document_id": document_id, "transfer_status": SENT_STATUS},
            )
        processed += 1
    session.commit()
    return processed


async def cleanup_temporary_documents(session: Session, *, request: Request | None = None) -> int:
    now = now_utc()
    rows = (
        session.execute(
            select(document_transfer_logs).where(
                (
                    and_(
                        document_transfer_logs.c.transfer_status == SENT_STATUS,
                        document_transfer_logs.c.local_deleted_at.is_(None),
                    )
                )
                | and_(
                    document_transfer_logs.c.transfer_status.in_(EXPIRE_STATUSES),
                    document_transfer_logs.c.expires_at.is_not(None),
                    document_transfer_logs.c.expires_at < now,
                    document_transfer_logs.c.local_deleted_at.is_(None),
                )
            )
        )
        .mappings()
        .all()
    )
    cleaned = 0
    for row in rows:
        deleted = safe_unlink_storage_key(row.storage_key)
        if row.transfer_status == SENT_STATUS:
            new_status = SENT_STATUS
            action = "document_temporary_file_deleted"
        else:
            new_status = "expired"
            action = "document_temporary_file_expired"
        session.execute(
            update(document_transfer_logs)
            .where(document_transfer_logs.c.id == row.id)
            .values(
                transfer_status=new_status,
                local_deleted_at=now if deleted or new_status == "expired" else row.local_deleted_at,
                last_error_code="DOCUMENT_TEMPORARY_FILE_EXPIRED" if new_status == "expired" else row.last_error_code,
                updated_at=func.now(),
            )
        )
        audit_event(
            session,
            action=action,
            object_type="document",
            object_id=str(row.id),
            request=request,
            actor_user_id=None,
            bitrix_company_id=row.bitrix_company_id,
            application_id=row.application_id,
            bitrix_deal_id=row.bitrix_deal_id,
            metadata={"document_id": row.id, "transfer_status": new_status},
        )
        if new_status == "expired":
            audit_event(
                session,
                action="document_reupload_required",
                object_type="document",
                object_id=str(row.id),
                request=request,
                actor_user_id=None,
                bitrix_company_id=row.bitrix_company_id,
                application_id=row.application_id,
                bitrix_deal_id=row.bitrix_deal_id,
                metadata={"document_id": row.id, "error_code": "DOCUMENT_REUPLOAD_REQUIRED"},
            )
        cleaned += 1
    session.commit()
    return cleaned
