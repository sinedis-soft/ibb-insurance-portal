from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.integrations.bitrix.sync import sync_active_applications, sync_application_from_bitrix, sync_error_rows
from app.routers.applications import parse_application_id
from app.routers.auth import auth_error, require_superadmin

router = APIRouter(prefix="/admin/integrations/bitrix", tags=["admin-integrations"])
DB_SESSION = Depends(get_db)


@router.post("/sync/applications")
async def sync_bitrix_applications(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = DB_SESSION,
) -> dict[str, int | str]:
    actor = require_superadmin(request, session)
    summary = await sync_active_applications(
        session,
        request=request,
        actor_user_id=actor.id,
        limit=limit,
    )
    return {
        "status": summary.status,
        "processed": summary.processed,
        "updated": summary.updated,
        "failed": summary.failed,
        "skipped": summary.skipped,
    }


@router.post("/sync/applications/{application_id}")
async def sync_bitrix_application(
    application_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, str | int | bool | None]:
    actor = require_superadmin(request, session)
    parsed_application_id = parse_application_id(application_id)
    if parsed_application_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    result = await sync_application_from_bitrix(
        session,
        parsed_application_id,
        request=request,
        actor_user_id=actor.id,
    )
    if result.status == "skipped":
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    return {
        "status": result.status,
        "application_id": f"app_{result.application_id}",
        "bitrix_deal_id": result.bitrix_deal_id,
        "portal_status": result.portal_status,
        "updated": result.updated,
        "error_code": result.error_code,
        "warning_code": result.warning_code,
    }


@router.get("/sync/errors")
async def list_bitrix_sync_errors(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = DB_SESSION,
) -> dict[str, object]:
    require_superadmin(request, session)
    return {"items": sync_error_rows(session, limit=limit)}
