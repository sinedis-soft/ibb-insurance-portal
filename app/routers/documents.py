from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import audit_event
from app.db import get_db
from app.models import document_transfer_logs, portal_policies
from app.routers.auth import auth_error, get_current_user_from_cookie
from app.security import policies
from app.security.policies import PolicyError

router = APIRouter(tags=["documents"])
DB_SESSION = Depends(get_db)


def parse_document_id(value: str) -> int | None:
    raw_value = value.removeprefix("doc_")
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def generic_document_stream(document_id: int) -> Iterator[bytes]:
    yield f"IBB portal document export\nDocument: doc_{document_id}\n".encode()


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
        action="document_download_allowed",
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
