from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.auth import audit_event
from app.bitrix import BITRIX_DEAL_FIELDS, BitrixError, create_deal
from app.company_access import normalize_company_id
from app.db import get_db
from app.i18n import t
from app.models import (
    auto_product_rules,
    auto_products,
    document_transfer_logs,
    portal_applications,
    user_company_roles,
)
from app.routers.auth import auth_error, get_current_user_from_cookie, request_locale
from app.security import policies
from app.security.company_eligibility import auto_allowed_reason, company_eligibility
from app.security.policies import PolicyError

router = APIRouter(prefix="/auto", tags=["auto-applications"])
DB_SESSION = Depends(get_db)
COUNTRY_CODES = {"PL", "KZ", "GE", "BY", "RU", "LV", "LT", "EU", "OTHER"}
DRAFT_EDITABLE_STATUSES = {"draft", "returned_for_revision"}


class VehiclePayload(BaseModel):
    plate_number: str | None = Field(default=None, max_length=64)
    vin: str | None = Field(default=None, max_length=64)
    vehicle_type: str | None = Field(default=None, max_length=64)
    brand_model: str | None = Field(default=None, max_length=128)
    production_year: int | None = Field(default=None, ge=1900, le=2100)
    engine_volume: int | None = Field(default=None, ge=0, le=20000)
    power_kw: int | None = Field(default=None, ge=0, le=2000)
    is_leased: bool = False


class PeriodPayload(BaseModel):
    start_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1, le=366)


class AutoApplicationPayload(BaseModel):
    company_id: str
    product_code: str
    vehicle_registration_country_code: str
    coverage_country_code: str | None = None
    coverage_zone_code: str | None = None
    vehicle: VehiclePayload = Field(default_factory=VehiclePayload)
    period: PeriodPayload = Field(default_factory=PeriodPayload)


def parse_application_id(value: str) -> int | None:
    raw_value = value.removeprefix("app_")
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def normalize_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized if normalized in COUNTRY_CODES else None


def normalize_payload(payload: AutoApplicationPayload) -> dict[str, Any]:
    return {
        "company_id": payload.company_id,
        "product_code": payload.product_code.strip(),
        "vehicle_registration_country_code": normalize_country_code(payload.vehicle_registration_country_code),
        "coverage_country_code": normalize_country_code(payload.coverage_country_code),
        "coverage_zone_code": normalize_country_code(payload.coverage_zone_code),
        "vehicle": payload.vehicle.model_dump(),
        "period": {
            "start_date": payload.period.start_date.isoformat() if payload.period.start_date else None,
            "duration_days": payload.period.duration_days,
        },
    }


def validation_error(locale: str, field: str, error_code: str) -> dict[str, str]:
    return {"field": field, "error_code": error_code, "message": t(locale, f"errors.{error_code}")}


def product_label(locale: str, product_code: str) -> str:
    return t(locale, f"autoProducts.{product_code}.label")


def product_description(locale: str, product_code: str) -> str:
    return t(locale, f"autoProducts.{product_code}.description")


def policy_error_response(session: Session, exc: PolicyError, request: Request):
    session.commit()
    raise auth_error(exc.status_code, exc.error_code, request) from exc


def company_country(session: Session, user, bitrix_company_id: int) -> str | None:
    row = (
        session.execute(
            select(user_company_roles.c.company_country_code_cache).where(
                user_company_roles.c.user_id == user.id,
                user_company_roles.c.bitrix_company_id == bitrix_company_id,
                user_company_roles.c.access_status == "active",
            )
        )
        .mappings()
        .first()
    )
    return normalize_country_code(row.company_country_code_cache) if row else None


async def require_company_create_access(session: Session, user, company_id: int, request: Request) -> None:
    try:
        await policies.require_company_access(session, user, company_id, "create_application", request=request)
    except PolicyError as exc:
        policy_error_response(session, exc, request)


async def require_company_read_access(session: Session, user, company_id: int, request: Request) -> None:
    try:
        await policies.require_company_access(session, user, company_id, "read", request=request)
    except PolicyError as exc:
        policy_error_response(session, exc, request)


def rule_matches(
    rule,
    *,
    user,
    company_country_code: str | None,
    vehicle_registration_country_code: str,
    coverage_country_code: str | None,
    coverage_zone_code: str | None,
) -> bool:
    allowed_user_types = rule.allowed_user_types or []
    allowed_role_codes = rule.allowed_role_codes or []
    if allowed_user_types and user.user_type not in allowed_user_types:
        return False
    if allowed_role_codes and user.role_code not in allowed_role_codes:
        return False
    if rule.company_country_code and rule.company_country_code != company_country_code:
        return False
    if (
        rule.vehicle_registration_country_code
        and rule.vehicle_registration_country_code != vehicle_registration_country_code
    ):
        return False
    if rule.coverage_country_code and rule.coverage_country_code != coverage_country_code:
        return False
    if rule.coverage_zone_code and rule.coverage_zone_code != coverage_zone_code:
        return False
    return True


def product_specific_allowed(
    product_code: str,
    *,
    vehicle_registration_country_code: str,
    coverage_country_code: str | None,
    coverage_zone_code: str | None,
) -> bool:
    if product_code == "border_oc":
        return vehicle_registration_country_code != "PL" and (
            coverage_zone_code == "EU" or coverage_country_code in {"PL", "LV", "LT"}
        )
    if product_code == "osago_rf":
        return vehicle_registration_country_code != "RU" and coverage_country_code == "RU"
    return True


def eligibility_reason(
    session: Session,
    user,
    company_id: int,
    normalized: dict[str, Any],
) -> str | None:
    return auto_allowed_reason(
        company_eligibility(session, user, company_id),
        normalized["product_code"],
        vehicle_registration_country_code=normalized["vehicle_registration_country_code"],
        coverage_country_code=normalized["coverage_country_code"],
        coverage_zone_code=normalized["coverage_zone_code"],
    )


def matching_rules(
    session: Session,
    *,
    user,
    company_country_code: str | None,
    vehicle_registration_country_code: str,
    coverage_country_code: str | None,
    coverage_zone_code: str | None,
) -> list[Any]:
    rows = (
        session.execute(
            select(auto_product_rules, auto_products.c.sort_order)
            .join(auto_products, auto_products.c.code == auto_product_rules.c.product_code)
            .where(auto_products.c.is_active.is_(True), auto_product_rules.c.is_active.is_(True))
            .order_by(auto_product_rules.c.priority.desc(), auto_products.c.sort_order.asc())
        )
        .mappings()
        .all()
    )
    return [
        row
        for row in rows
        if rule_matches(
            row,
            user=user,
            company_country_code=company_country_code,
            vehicle_registration_country_code=vehicle_registration_country_code,
            coverage_country_code=coverage_country_code,
            coverage_zone_code=coverage_zone_code,
        )
        and product_specific_allowed(
            row.product_code,
            vehicle_registration_country_code=vehicle_registration_country_code,
            coverage_country_code=coverage_country_code,
            coverage_zone_code=coverage_zone_code,
        )
    ]


async def available_product_rows(
    session: Session,
    user,
    request: Request,
    *,
    company_id: int,
    vehicle_registration_country_code: str,
    coverage_country_code: str | None,
    coverage_zone_code: str | None,
) -> list[Any]:
    await require_company_read_access(session, user, company_id, request)
    if not await policies.can_access_company(session, user, company_id, "create_application"):
        return []
    eligibility = company_eligibility(session, user, company_id)
    if not eligibility.portal_applications_allowed:
        return []
    return matching_rules(
        session,
        user=user,
        company_country_code=company_country(session, user, company_id),
        vehicle_registration_country_code=vehicle_registration_country_code,
        coverage_country_code=coverage_country_code,
        coverage_zone_code=coverage_zone_code,
    )


def public_product(row, *, locale: str) -> dict[str, Any]:
    return {
        "code": row.product_code,
        "label": product_label(locale, row.product_code),
        "description": product_description(locale, row.product_code),
        "can_create": True,
        "requires_manual_review": bool(row.requires_manual_review),
    }


async def validate_payload(
    session: Session,
    user,
    request: Request,
    payload: AutoApplicationPayload,
) -> tuple[str, list[dict[str, str]], dict[str, Any], int | None]:
    locale = request_locale(request)
    normalized = normalize_payload(payload)
    errors: list[dict[str, str]] = []
    company_id = normalize_company_id(payload.company_id)
    if company_id is None:
        errors.append(validation_error(locale, "company_id", "COMPANY_CONTEXT_REQUIRED"))
    if normalized["vehicle_registration_country_code"] is None:
        errors.append(
            validation_error(locale, "vehicle_registration_country_code", "AUTO_INVALID_COUNTRY_COMBINATION")
        )
    if normalized["coverage_country_code"] is None and normalized["coverage_zone_code"] is None:
        errors.append(validation_error(locale, "coverage_country_code", "AUTO_REQUIRED_FIELD_MISSING"))
    if not normalized["vehicle"].get("plate_number"):
        errors.append(validation_error(locale, "vehicle.plate_number", "AUTO_REQUIRED_FIELD_MISSING"))
    if normalized["period"].get("start_date") is None or normalized["period"].get("duration_days") is None:
        errors.append(validation_error(locale, "period", "AUTO_INVALID_PERIOD"))
    if errors or company_id is None or normalized["vehicle_registration_country_code"] is None:
        return "invalid", errors, normalized, company_id

    await require_company_create_access(session, user, company_id, request)
    rows = await available_product_rows(
        session,
        user,
        request,
        company_id=company_id,
        vehicle_registration_country_code=normalized["vehicle_registration_country_code"],
        coverage_country_code=normalized["coverage_country_code"],
        coverage_zone_code=normalized["coverage_zone_code"],
    )
    available_codes = {row.product_code for row in rows}
    if normalized["product_code"] not in available_codes:
        errors.append(validation_error(locale, "product_code", "AUTO_PRODUCT_NOT_AVAILABLE"))
    reason = eligibility_reason(session, user, company_id, normalized)
    if reason is not None:
        errors.append(validation_error(locale, "company_eligibility", reason))
    return ("ok" if not errors else "invalid"), errors, normalized, company_id


def has_required_auto_documents(session: Session, application_id: int, draft_data: dict[str, Any]) -> str | None:
    document_types = set(
        session.execute(
            select(document_transfer_logs.c.document_type).where(
                document_transfer_logs.c.application_id == application_id,
                document_transfer_logs.c.transfer_status.in_(("transfer_pending", "pending", "transferred", "synced")),
            )
        ).scalars()
    )
    if "vehicle_registration_certificate" not in document_types:
        return "DOCUMENT_REQUIRED"
    vehicle = draft_data.get("vehicle") or {}
    if vehicle.get("is_leased") and "lease_agreement" not in document_types:
        return "DOCUMENT_TYPE_REQUIRED"
    return None


def build_auto_deal_fields(application, user, draft_data: dict[str, Any]) -> dict[str, Any]:
    now_value = date.today().isoformat()
    fields: dict[str, Any] = {
        "TITLE": f"Portal auto application #{application.id}",
        "CATEGORY_ID": application.bitrix_category_id or 0,
        "COMPANY_ID": application.bitrix_company_id,
        "CONTACT_IDS": [user.bitrix_contact_id] if user.bitrix_contact_id else [],
        BITRIX_DEAL_FIELDS["portal_application_id"]: str(application.id),
        BITRIX_DEAL_FIELDS["portal_application_type"]: "auto",
        BITRIX_DEAL_FIELDS["portal_source"]: "ibb_portal",
        BITRIX_DEAL_FIELDS["portal_channel"]: "client_portal",
        BITRIX_DEAL_FIELDS["portal_sync_status"]: "pending",
        BITRIX_DEAL_FIELDS["portal_last_sync_at"]: now_value,
    }
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


async def submit_auto_application_common(
    application_id: str,
    request: Request,
    session: Session,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    parsed_application_id = parse_application_id(application_id)
    if parsed_application_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    try:
        application = await policies.require_application_access(
            session,
            user,
            "submit",
            application_id=parsed_application_id,
            request=request,
        )
    except PolicyError as exc:
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request) from exc
    if application.application_type != "auto":
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    if application.portal_status not in DRAFT_EDITABLE_STATUSES:
        raise auth_error(status.HTTP_403_FORBIDDEN, "AUTO_DRAFT_NOT_EDITABLE", request)
    draft_data = application.draft_data_json or {}
    payload = AutoApplicationPayload.model_validate(draft_data)
    validation_status, errors, normalized, company_id = await validate_payload(session, user, request, payload)
    document_error = has_required_auto_documents(session, parsed_application_id, normalized)
    if document_error is not None:
        errors.append(validation_error(request_locale(request), "documents", document_error))
    if validation_status != "ok" or errors or company_id is None:
        audit_event(
            session,
            action="auto_application_submit_denied",
            object_type="application",
            object_id=str(parsed_application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=parsed_application_id,
            metadata={"product_code": draft_data.get("product_code"), "reason_code": errors[0]["error_code"]},
        )
        session.commit()
        return {"status": "invalid", "errors": errors}
    try:
        deal_id = await create_deal(build_auto_deal_fields(application, user, normalized))
    except BitrixError as exc:
        session.execute(
            update(portal_applications)
            .where(portal_applications.c.id == parsed_application_id)
            .values(portal_status="draft", last_synced_at=func.now())
        )
        audit_event(
            session,
            action="bitrix_deal_create_failed",
            object_type="application",
            object_id=str(parsed_application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=parsed_application_id,
            metadata={"product_code": normalized["product_code"], "reason_code": exc.error_code},
        )
        session.commit()
        return {"status": "sync_error", "error_code": "BITRIX_DEAL_CREATE_FAILED"}

    session.execute(
        update(portal_applications)
        .where(portal_applications.c.id == parsed_application_id)
        .values(bitrix_deal_id=deal_id, portal_status="received", submitted_at=func.now(), last_synced_at=func.now())
    )
    session.execute(
        update(document_transfer_logs)
        .where(document_transfer_logs.c.application_id == parsed_application_id)
        .values(bitrix_deal_id=deal_id, transfer_status="transferred")
    )
    audit_event(
        session,
        action="auto_application_submitted",
        object_type="application",
        object_id=str(parsed_application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=parsed_application_id,
        bitrix_deal_id=deal_id,
        metadata={"product_code": normalized["product_code"]},
    )
    session.commit()
    return {
        "status": "ok",
        "id": f"app_{parsed_application_id}",
        "portal_status": "received",
        "bitrix_deal_id": deal_id,
    }


@router.get("/products/available")
async def list_available_auto_products(
    request: Request,
    company_id: str = Query(...),
    vehicle_registration_country_code: str = Query(...),
    coverage_country_code: str | None = Query(default=None),
    coverage_zone_code: str | None = Query(default=None),
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    parsed_company_id = normalize_company_id(company_id)
    vehicle_country = normalize_country_code(vehicle_registration_country_code)
    coverage_country = normalize_country_code(coverage_country_code)
    coverage_zone = normalize_country_code(coverage_zone_code)
    if parsed_company_id is None or vehicle_country is None:
        return {"items": []}
    rows = await available_product_rows(
        session,
        user,
        request,
        company_id=parsed_company_id,
        vehicle_registration_country_code=vehicle_country,
        coverage_country_code=coverage_country,
        coverage_zone_code=coverage_zone,
    )
    audit_event(
        session,
        action="auto_product_availability_checked",
        object_type="auto_product",
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=parsed_company_id,
        metadata={"product_count": len(rows)},
    )
    session.commit()
    locale = request_locale(request)
    return {"items": [public_product(row, locale=locale) for row in rows]}


@router.post("/applications/validate")
async def validate_auto_application(
    payload: AutoApplicationPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    validation_status, errors, normalized, company_id = await validate_payload(session, user, request, payload)
    if errors:
        audit_event(
            session,
            action="auto_application_validation_failed",
            object_type="auto_application",
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=company_id,
            metadata={"product_code": normalized["product_code"], "reason_code": errors[0]["error_code"]},
        )
        session.commit()
    return {"status": validation_status, "errors": errors}


@router.post("/applications/draft")
async def save_auto_application_draft(
    payload: AutoApplicationPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    validation_status, errors, normalized, company_id = await validate_payload(session, user, request, payload)
    if validation_status != "ok" or company_id is None:
        audit_event(
            session,
            action="auto_application_validation_failed",
            object_type="auto_application",
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=company_id,
            metadata={
                "product_code": normalized["product_code"],
                "reason_code": errors[0]["error_code"] if errors else None,
            },
        )
        session.commit()
        return {"status": "invalid", "errors": errors}

    application_id = session.execute(
        insert(portal_applications)
        .values(
            application_type="auto",
            bitrix_company_id=company_id,
            bitrix_contact_id=user.bitrix_contact_id,
            portal_status="draft",
            product_type_code=normalized["product_code"],
            title_cache="Auto application draft",
            draft_data_json=normalized,
            created_by_user_id=user.id,
        )
        .returning(portal_applications.c.id)
    ).scalar_one()
    audit_event(
        session,
        action="auto_application_draft_saved",
        object_type="application",
        object_id=str(application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=company_id,
        application_id=application_id,
        metadata={"product_code": normalized["product_code"]},
    )
    session.commit()
    return {"status": "ok", "id": f"app_{application_id}", "portal_status": "draft"}


@router.patch("/applications/{application_id}/draft")
async def update_auto_application_draft(
    application_id: str,
    payload: AutoApplicationPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    parsed_application_id = parse_application_id(application_id)
    if parsed_application_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    try:
        application = await policies.require_application_access(
            session,
            user,
            "edit_draft",
            application_id=parsed_application_id,
            request=request,
        )
    except PolicyError as exc:
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request) from exc
    if application.application_type != "auto" or application.portal_status not in DRAFT_EDITABLE_STATUSES:
        raise auth_error(status.HTTP_403_FORBIDDEN, "AUTO_DRAFT_NOT_EDITABLE", request)

    validation_status, errors, normalized, company_id = await validate_payload(session, user, request, payload)
    if validation_status != "ok" or company_id is None:
        audit_event(
            session,
            action="auto_application_validation_failed",
            object_type="application",
            object_id=str(parsed_application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=company_id,
            application_id=parsed_application_id,
            metadata={
                "product_code": normalized["product_code"],
                "reason_code": errors[0]["error_code"] if errors else None,
            },
        )
        session.commit()
        return {"status": "invalid", "errors": errors}

    session.execute(
        update(portal_applications)
        .where(portal_applications.c.id == parsed_application_id)
        .values(
            bitrix_company_id=company_id,
            product_type_code=normalized["product_code"],
            draft_data_json=normalized,
            title_cache="Auto application draft",
        )
    )
    audit_event(
        session,
        action="auto_application_draft_updated",
        object_type="application",
        object_id=str(parsed_application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=company_id,
        application_id=parsed_application_id,
        metadata={"product_code": normalized["product_code"]},
    )
    session.commit()
    return {"status": "ok", "id": f"app_{parsed_application_id}", "portal_status": "draft"}


@router.post("/applications/{application_id}/submit")
async def submit_auto_application(
    application_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    return await submit_auto_application_common(application_id, request, session)
