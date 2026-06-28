from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event, now_utc
from app.config import get_settings
from app.db import get_db
from app.document_transfer import (
    DELETE_ALLOWED_STATUSES,
    UPLOAD_ALLOWED_STATUSES,
    safe_unlink_storage_key,
    storage_path,
)
from app.models import document_transfer_logs, portal_policies
from app.routers.auth import auth_error, get_current_user_from_cookie
from app.security import policies
from app.security.policies import PolicyError

router = APIRouter(tags=["documents"])
DB_SESSION = Depends(get_db)
DOCUMENT_TYPE_FORM = Form(default="other")
DOCUMENT_FILE = File(...)
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
MAX_DOCUMENTS_PER_APPLICATION = 10
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc", ".xls", ".xlsx", ".rar", ".zip"}
ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel",
    "application/zip",
    "application/x-zip-compressed",
    "application/vnd.rar",
    "application/x-rar-compressed",
)
APPLICATION_DOCUMENT_TYPES = {
    "client_document",
    "invoice",
    "certificate",
    "other",
    "vehicle_registration_certificate",
    "lease_agreement",
    "previous_policy",
    "cmr",
    "transport_document",
    "cargo_description",
    "contract",
    "certificate_basis",
}


def parse_document_id(value: str) -> int | None:
    raw_value = value.removeprefix("doc_")
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def parse_application_id(value: str) -> int | None:
    raw_value = value.removeprefix("app_")
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def generic_document_stream(document_id: int):
    yield f"IBB portal document export\nDocument: doc_{document_id}\n".encode()


def document_payload(row) -> dict:
    uploaded_at = getattr(row, "uploaded_at", None) or row.created_at
    file_size = getattr(row, "file_size", None) if getattr(row, "file_size", None) is not None else row.size_bytes
    is_download_available = bool(
        row.storage_key
        and row.local_deleted_at is None
        and row.transfer_status in {"uploaded", "transferring", "failed", "retry_required"}
    )
    return {
        "id": f"doc_{row.id}",
        "application_id": f"app_{row.application_id}",
        "document_type": row.document_type,
        "mime_type": row.mime_type,
        "file_size": file_size,
        "transfer_status": row.transfer_status,
        "uploaded_at": uploaded_at.isoformat() if uploaded_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "is_download_available": is_download_available,
    }


def _file_extension(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    return suffix


def _mime_allowed(content_type: str | None) -> bool:
    if not content_type:
        return False
    return any(content_type == allowed or content_type.startswith(allowed) for allowed in ALLOWED_MIME_PREFIXES)


async def _require_application_for_documents(
    session: Session,
    user,
    application_id: str,
    request: Request,
    action: str = "upload_document",
):
    parsed_application_id = parse_application_id(application_id)
    if parsed_application_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    try:
        return await policies.require_application_access(
            session,
            user,
            action,
            application_id=parsed_application_id,
            request=request,
        )
    except PolicyError as exc:
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request) from exc


@router.post("/applications/{application_id}/documents")
async def upload_application_document(
    application_id: str,
    request: Request,
    document_type: str = DOCUMENT_TYPE_FORM,
    file: UploadFile = DOCUMENT_FILE,
    session: Session = DB_SESSION,
) -> dict:
    current_user = get_current_user_from_cookie(request, session)
    application = await _require_application_for_documents(session, current_user, application_id, request)
    if application.portal_status not in UPLOAD_ALLOWED_STATUSES:
        raise auth_error(status.HTTP_403_FORBIDDEN, "DOCUMENT_APPLICATION_STATUS_NOT_ALLOWED", request)
    if document_type not in APPLICATION_DOCUMENT_TYPES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "DOCUMENT_TYPE_INVALID", request)

    existing_count = session.execute(
        select(func.count()).select_from(document_transfer_logs).where(
            document_transfer_logs.c.application_id == application.id,
            document_transfer_logs.c.transfer_status.not_in(("deleted", "expired")),
        )
    ).scalar_one()
    if existing_count >= MAX_DOCUMENTS_PER_APPLICATION:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "DOCUMENT_LIMIT_EXCEEDED", request)

    extension = _file_extension(file)
    content_type = file.content_type or "application/octet-stream"
    if extension not in ALLOWED_EXTENSIONS:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "DOCUMENT_EXTENSION_NOT_ALLOWED", request)
    if not _mime_allowed(content_type):
        raise auth_error(status.HTTP_400_BAD_REQUEST, "DOCUMENT_MIME_NOT_ALLOWED", request)

    content = await file.read()
    if len(content) > MAX_DOCUMENT_BYTES:
        raise auth_error(status.HTTP_400_BAD_REQUEST, "DOCUMENT_TOO_LARGE", request)

    storage_key = f"app-{application.id}/{uuid4().hex}{extension}"
    target = storage_path(storage_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    now = now_utc()

    document_id = session.execute(
        insert(document_transfer_logs)
        .values(
            application_id=application.id,
            bitrix_company_id=application.bitrix_company_id,
            uploaded_by_user_id=current_user.id,
            created_by_user_id=current_user.id,
            document_type=document_type,
            original_filename=(file.filename or "")[:512] or None,
            mime_type=content_type,
            size_bytes=len(content),
            file_size=len(content),
            storage_provider="portal_temp",
            storage_key=storage_key,
            temporary_storage_path=str(target),
            transfer_status="uploaded",
            bitrix_deal_id=application.bitrix_deal_id,
            uploaded_at=now,
            expires_at=now + timedelta(hours=get_settings().document_temp_retention_hours),
        )
        .returning(document_transfer_logs.c.id)
    ).scalar_one()
    audit_event(
        session,
        action="document_uploaded",
        object_type="document",
        object_id=str(document_id),
        request=request,
        actor_user_id=current_user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application.id,
        metadata={"document_id": document_id, "document_type": document_type},
    )
    session.commit()
    row = (
        session.execute(select(document_transfer_logs).where(document_transfer_logs.c.id == document_id))
        .mappings()
        .one()
    )
    return {"status": "ok", "document": document_payload(row)}


@router.get("/applications/{application_id}/documents")
async def list_application_documents(
    application_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict:
    current_user = get_current_user_from_cookie(request, session)
    application = await _require_application_for_documents(
        session,
        current_user,
        application_id,
        request,
        action="read",
    )
    rows = (
        session.execute(
            select(document_transfer_logs)
            .where(document_transfer_logs.c.application_id == application.id)
            .order_by(document_transfer_logs.c.created_at.desc(), document_transfer_logs.c.id.desc())
        )
        .mappings()
        .all()
    )
    return {"items": [document_payload(row) for row in rows]}


@router.delete("/applications/{application_id}/documents/{document_id}")
async def delete_application_document(
    application_id: str,
    document_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict:
    current_user = get_current_user_from_cookie(request, session)
    application = await _require_application_for_documents(session, current_user, application_id, request)
    parsed_document_id = parse_document_id(document_id)
    if parsed_document_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request)
    if application.portal_status not in DELETE_ALLOWED_STATUSES:
        raise auth_error(status.HTTP_403_FORBIDDEN, "DOCUMENT_DELETE_NOT_ALLOWED", request)

    document_row = (
        session.execute(
            select(document_transfer_logs).where(
                document_transfer_logs.c.id == parsed_document_id,
                document_transfer_logs.c.application_id == application.id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if document_row is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request)
    try:
        await policies.require_document_access(session, current_user, parsed_document_id, "upload", request=request)
    except PolicyError as exc:
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request) from exc

    if document_row.transfer_status == "sent":
        audit_event(
            session,
            action="document_delete_denied",
            object_type="document",
            object_id=str(parsed_document_id),
            request=request,
            actor_user_id=current_user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=application.id,
            bitrix_deal_id=document_row.bitrix_deal_id,
            metadata={"document_id": parsed_document_id, "error_code": "DOCUMENT_ALREADY_SENT"},
        )
        session.commit()
        raise auth_error(status.HTTP_400_BAD_REQUEST, "DOCUMENT_ALREADY_SENT", request)

    safe_unlink_storage_key(document_row.storage_key)
    session.execute(
        update(document_transfer_logs)
        .where(document_transfer_logs.c.id == parsed_document_id)
        .values(transfer_status="deleted", local_deleted_at=now_utc(), updated_at=func.now())
    )
    audit_event(
        session,
        action="document_deleted",
        object_type="document",
        object_id=str(parsed_document_id),
        request=request,
        actor_user_id=current_user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application.id,
        metadata={"document_id": parsed_document_id},
    )
    session.commit()
    return {"status": "ok"}


def audit_download_denied(
    session: Session,
    *,
    request: Request,
    user,
    document_id: int | None,
    reason_code: str,
    document_row=None,
) -> None:
    audit_event(
        session,
        action="document_download_denied",
        object_type="document",
        object_id=str(document_id) if document_id else None,
        request=request,
        actor_user_id=user.id if user else None,
        bitrix_company_id=getattr(document_row, "bitrix_company_id", None),
        application_id=getattr(document_row, "application_id", None),
        metadata={"reason_code": reason_code, "document_id": document_id, "status": "denied"},
    )


@router.get("/applications/{application_id}/documents/{document_id}/download")
async def download_application_document(
    application_id: str,
    document_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> FileResponse:
    current_user = get_current_user_from_cookie(request, session)
    application = await _require_application_for_documents(
        session,
        current_user,
        application_id,
        request,
        action="read",
    )
    parsed_document_id = parse_document_id(document_id)
    if parsed_document_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request)
    document_row = (
        session.execute(
            select(document_transfer_logs).where(
                document_transfer_logs.c.id == parsed_document_id,
                document_transfer_logs.c.application_id == application.id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if document_row is None:
        audit_download_denied(
            session,
            request=request,
            user=current_user,
            document_id=parsed_document_id,
            reason_code="DOCUMENT_NOT_FOUND",
        )
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request)
    try:
        await policies.require_document_access(
            session,
            current_user,
            parsed_document_id,
            "download",
            request=request,
        )
    except PolicyError as exc:
        audit_download_denied(
            session,
            request=request,
            user=current_user,
            document_id=parsed_document_id,
            reason_code=exc.error_code,
            document_row=document_row,
        )
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request) from exc
    if not document_row.storage_key or document_row.local_deleted_at is not None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_DOWNLOAD_NOT_AVAILABLE", request)
    path = storage_path(document_row.storage_key)
    if not path.exists() or not path.is_file():
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_DOWNLOAD_NOT_AVAILABLE", request)
    audit_event(
        session,
        action="document_downloaded",
        object_type="document",
        object_id=str(parsed_document_id),
        request=request,
        actor_user_id=current_user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=application.id,
        bitrix_deal_id=document_row.bitrix_deal_id,
        metadata={"document_id": parsed_document_id, "transfer_status": document_row.transfer_status},
    )
    session.commit()
    extension = path.suffix.lower() or ".bin"
    return FileResponse(
        path,
        media_type=document_row.mime_type or "application/octet-stream",
        filename=f"ibb-document-{parsed_document_id}{extension}",
    )


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> StreamingResponse:
    current_user = get_current_user_from_cookie(request, session)
    parsed_document_id = parse_document_id(document_id)
    if parsed_document_id is None:
        audit_download_denied(
            session,
            request=request,
            user=current_user,
            document_id=None,
            reason_code="DOCUMENT_NOT_FOUND",
        )
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request)

    document_row = (
        session.execute(select(document_transfer_logs).where(document_transfer_logs.c.id == parsed_document_id))
        .mappings()
        .one_or_none()
    )
    if document_row is None:
        audit_download_denied(
            session,
            request=request,
            user=current_user,
            document_id=parsed_document_id,
            reason_code="DOCUMENT_NOT_FOUND",
        )
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request)

    if not document_row.is_policy_file:
        audit_download_denied(
            session,
            request=request,
            user=current_user,
            document_id=parsed_document_id,
            reason_code="DOCUMENT_NOT_FOUND",
            document_row=document_row,
        )
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request)

    try:
        await policies.require_document_access(
            session,
            current_user,
            parsed_document_id,
            "download",
            request=request,
        )
        if document_row.is_policy_file:
            policy_row = (
                session.execute(
                    select(portal_policies.c.application_id).where(
                        portal_policies.c.document_transfer_log_id == parsed_document_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if policy_row is None:
                raise PolicyError(
                    "POLICY_NOT_FOUND",
                    status.HTTP_404_NOT_FOUND,
                    "policy",
                    "download",
                    str(parsed_document_id),
                )
            await policies.require_policy_access(
                session,
                current_user,
                policy_row.application_id,
                "download",
                request=request,
            )
    except PolicyError as exc:
        audit_download_denied(
            session,
            request=request,
            user=current_user,
            document_id=parsed_document_id,
            reason_code=exc.error_code,
            document_row=document_row,
        )
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", request) from exc

    audit_event(
        session,
        action="document_downloaded",
        object_type="document",
        object_id=str(parsed_document_id),
        request=request,
        actor_user_id=current_user.id,
        application_id=document_row.application_id,
        metadata={"document_id": parsed_document_id, "status": "allowed"},
    )
    session.commit()
    headers = {"Content-Disposition": f'attachment; filename="ibb-document-{parsed_document_id}.bin"'}
    return StreamingResponse(
        generic_document_stream(parsed_document_id),
        media_type="application/octet-stream",
        headers=headers,
    )
