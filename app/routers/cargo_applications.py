from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.application_submit import SUBMIT_ALLOWED_STATUSES, submit_application_to_bitrix
from app.auth import audit_event
from app.bitrix import BITRIX_DEAL_FIELDS, create_deal, find_deal_by_portal_application_id
from app.company_access import normalize_company_id
from app.db import get_db
from app.document_transfer import REQUIRED_DOCUMENT_STATUSES
from app.i18n import t
from app.models import document_transfer_logs, portal_applications
from app.partner_client_requests import (
    parse_partner_client_request_id,
    require_confirmed_partner_client_request,
)
from app.routers.auth import auth_error, get_current_user_from_cookie, request_locale
from app.security import policies
from app.security.company_eligibility import cargo_allowed_reason, company_eligibility
from app.security.policies import PolicyError

router = APIRouter(prefix="/cargo", tags=["cargo-applications"])
DB_SESSION = Depends(get_db)

CARGO_BITRIX_CATEGORY_ID = 19
COUNTRY_CODES = {"PL", "KZ", "GE", "BY", "RU", "LV", "LT", "UZ", "EU", "OTHER"}
CURRENCIES = {"EUR", "USD", "PLN", "GEL", "KZT"}
CARGO_APPLICATION_TYPES = ("single_shipment", "contract_coverage", "certificate")
CARGO_TYPES = ("general_cargo", "perishable", "dangerous", "vehicle", "equipment", "other")
TRANSPORT_TYPES = ("road", "rail", "sea", "air", "multimodal")
DOCUMENT_TYPES = ("request_document", "invoice", "cmr", "contract", "certificate", "other")
DRAFT_EDITABLE_STATUSES = {"draft", "returned_for_revision"}
PRODUCT_TYPE_CODES = {
    "single_shipment": "cargo_single_shipment",
    "contract_coverage": "cargo_contract_cover",
    "certificate": "cargo_document_request",
}


class RoutePayload(BaseModel):
    country_from: str | None = Field(default=None, max_length=16)
    country_to: str | None = Field(default=None, max_length=16)
    route_description: str | None = Field(default=None, max_length=2000)


class CargoPayload(BaseModel):
    cargo_type: str | None = Field(default=None, max_length=64)
    cargo_description: str | None = Field(default=None, max_length=2000)
    cargo_value: Any = None
    currency: str | None = Field(default=None, max_length=16)


class TransportPayload(BaseModel):
    transport_type: str | None = Field(default=None, max_length=64)
    carrier_name: str | None = Field(default=None, max_length=255)
    vehicle_plate: str | None = Field(default=None, max_length=64)
    departure_date: date | None = None


class ContractPayload(BaseModel):
    bitrix_contract_deal_id: int | None = Field(default=None, ge=1)
    contract_number: str | None = Field(default=None, max_length=128)
    is_active_contract: bool = False


class CertificatePayload(BaseModel):
    is_certificate_requested: bool = False


class DocumentsPayload(BaseModel):
    has_supporting_document: bool = False


class CargoApplicationPayload(BaseModel):
    company_id: str
    partner_client_request_id: str | None = None
    cargo_application_type: str | None = Field(default=None, max_length=64)
    route: RoutePayload = Field(default_factory=RoutePayload)
    cargo: CargoPayload = Field(default_factory=CargoPayload)
    transport: TransportPayload = Field(default_factory=TransportPayload)
    contract: ContractPayload = Field(default_factory=ContractPayload)
    certificate: CertificatePayload = Field(default_factory=CertificatePayload)
    documents: DocumentsPayload = Field(default_factory=DocumentsPayload)
    comment: str | None = Field(default=None, max_length=4000)


def parse_application_id(value: str) -> int | None:
    raw_value = value.removeprefix("app_")
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def normalize_code(value: str | None, allowed: set[str] | tuple[str, ...]) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized in allowed else None


def normalize_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized if normalized in COUNTRY_CODES else None


def normalize_currency(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized if normalized in CURRENCIES else None


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def parse_positive_decimal(value: Any) -> tuple[str | None, bool]:
    if value in (None, ""):
        return None, False
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None, False
    if parsed <= 0:
        return None, False
    return format(parsed, "f"), True


def normalize_payload(payload: CargoApplicationPayload) -> dict[str, Any]:
    cargo_value, _is_valid_value = parse_positive_decimal(payload.cargo.cargo_value)
    return {
        "company_id": payload.company_id,
        "partner_client_request_id": payload.partner_client_request_id,
        "cargo_application_type": normalize_code(payload.cargo_application_type, CARGO_APPLICATION_TYPES),
        "route": {
            "country_from": normalize_country_code(payload.route.country_from),
            "country_to": normalize_country_code(payload.route.country_to),
            "route_description": normalize_text(payload.route.route_description),
        },
        "cargo": {
            "cargo_type": normalize_code(payload.cargo.cargo_type, CARGO_TYPES),
            "cargo_description": normalize_text(payload.cargo.cargo_description),
            "cargo_value": cargo_value,
            "currency": normalize_currency(payload.cargo.currency),
        },
        "transport": {
            "transport_type": normalize_code(payload.transport.transport_type, TRANSPORT_TYPES),
            "carrier_name": normalize_text(payload.transport.carrier_name),
            "vehicle_plate": normalize_text(payload.transport.vehicle_plate),
            "departure_date": (
                payload.transport.departure_date.isoformat() if payload.transport.departure_date else None
            ),
        },
        "contract": {
            "bitrix_contract_deal_id": payload.contract.bitrix_contract_deal_id,
            "contract_number": normalize_text(payload.contract.contract_number),
            "is_active_contract": payload.contract.is_active_contract,
        },
        "certificate": {"is_certificate_requested": payload.certificate.is_certificate_requested},
        "documents": {"has_supporting_document": payload.documents.has_supporting_document},
        "comment": normalize_text(payload.comment),
    }


def validation_error(locale: str, field: str, error_code: str) -> dict[str, str]:
    return {"field": field, "error_code": error_code, "message": t(locale, f"errors.{error_code}")}


def reference_item(locale: str, section: str, code: str) -> dict[str, str]:
    return {"code": code, "label": t(locale, f"{section}.{code}.label")}


def policy_error_response(session: Session, exc: PolicyError, request: Request):
    session.commit()
    raise auth_error(exc.status_code, exc.error_code, request) from exc


async def require_company_create_access(session: Session, user, company_id: int, request: Request) -> None:
    try:
        await policies.require_company_access(session, user, company_id, "create_application", request=request)
    except PolicyError as exc:
        policy_error_response(session, exc, request)


async def validate_payload(
    session: Session,
    user,
    request: Request,
    payload: CargoApplicationPayload,
) -> tuple[str, list[dict[str, str]], dict[str, Any], int | None]:
    locale = request_locale(request)
    normalized = normalize_payload(payload)
    errors: list[dict[str, str]] = []
    company_id = normalize_company_id(payload.company_id)
    raw_application_type = normalize_text(payload.cargo_application_type)

    if company_id is None:
        errors.append(validation_error(locale, "company_id", "COMPANY_CONTEXT_REQUIRED"))
    if raw_application_type is None:
        errors.append(validation_error(locale, "cargo_application_type", "CARGO_APPLICATION_TYPE_REQUIRED"))
    elif normalized["cargo_application_type"] is None:
        errors.append(validation_error(locale, "cargo_application_type", "CARGO_APPLICATION_TYPE_INVALID"))
    if payload.cargo.cargo_type and normalized["cargo"]["cargo_type"] is None:
        errors.append(validation_error(locale, "cargo.cargo_type", "CARGO_APPLICATION_TYPE_INVALID"))

    cargo_value = payload.cargo.cargo_value
    has_cargo_value = cargo_value not in (None, "")
    _normalized_value, is_valid_value = parse_positive_decimal(cargo_value)
    if has_cargo_value and not is_valid_value:
        errors.append(validation_error(locale, "cargo.cargo_value", "CARGO_VALUE_INVALID"))

    application_type = normalized["cargo_application_type"]
    if application_type == "single_shipment":
        require_route(locale, normalized, errors)
        require_cargo_value(locale, payload, normalized, errors)
        if normalized["transport"]["transport_type"] is None:
            errors.append(validation_error(locale, "transport.transport_type", "CARGO_TRANSPORT_TYPE_REQUIRED"))
        if normalized["cargo"]["cargo_type"] is None:
            errors.append(validation_error(locale, "cargo.cargo_type", "CARGO_APPLICATION_TYPE_REQUIRED"))
    elif application_type == "contract_coverage":
        require_active_contract(locale, normalized, errors, "CARGO_ACTIVE_CONTRACT_REQUIRED")
        if has_cargo_value and normalized["cargo"]["currency"] is None:
            errors.append(validation_error(locale, "cargo.currency", "CARGO_CURRENCY_REQUIRED"))
    elif application_type == "certificate":
        require_route(locale, normalized, errors)
        require_cargo_value(locale, payload, normalized, errors)
        require_active_contract(locale, normalized, errors, "CARGO_CERTIFICATE_CONTRACT_REQUIRED")
        if not normalized["certificate"]["is_certificate_requested"]:
            errors.append(
                validation_error(
                    locale,
                    "certificate.is_certificate_requested",
                    "CARGO_CERTIFICATE_CONTRACT_REQUIRED",
                )
            )
        if normalized["transport"]["transport_type"] is None:
            errors.append(validation_error(locale, "transport.transport_type", "CARGO_TRANSPORT_TYPE_REQUIRED"))

    if errors or company_id is None:
        return "invalid", errors, normalized, company_id

    if user.user_type == "partner":
        partner_client = require_confirmed_partner_client_request(
            session,
            user=user,
            request_id_value=payload.partner_client_request_id,
            bitrix_company_id=company_id,
            request=request,
        )
        normalized["partner_client_request_id"] = f"pcr_{partner_client.id}"
    else:
        await require_company_create_access(session, user, company_id, request)
        reason = cargo_allowed_reason(company_eligibility(session, user, company_id), normalized)
        if reason is not None:
            errors.append(validation_error(locale, "company_eligibility", reason))
            return "invalid", errors, normalized, company_id
    return "ok", [], normalized, company_id


def require_route(locale: str, normalized: dict[str, Any], errors: list[dict[str, str]]) -> None:
    if normalized["route"]["country_from"] is None and normalized["route"]["country_to"] is None:
        errors.append(validation_error(locale, "route", "CARGO_ROUTE_REQUIRED"))
        return
    if normalized["route"]["country_from"] is None:
        errors.append(validation_error(locale, "route.country_from", "CARGO_COUNTRY_FROM_REQUIRED"))
    if normalized["route"]["country_to"] is None:
        errors.append(validation_error(locale, "route.country_to", "CARGO_COUNTRY_TO_REQUIRED"))


def require_cargo_value(
    locale: str,
    payload: CargoApplicationPayload,
    normalized: dict[str, Any],
    errors: list[dict[str, str]],
) -> None:
    if payload.cargo.cargo_value in (None, ""):
        errors.append(validation_error(locale, "cargo.cargo_value", "CARGO_VALUE_REQUIRED"))
    elif normalized["cargo"]["cargo_value"] is None:
        errors.append(validation_error(locale, "cargo.cargo_value", "CARGO_VALUE_INVALID"))
    if normalized["cargo"]["currency"] is None:
        errors.append(validation_error(locale, "cargo.currency", "CARGO_CURRENCY_REQUIRED"))


def require_active_contract(
    locale: str,
    normalized: dict[str, Any],
    errors: list[dict[str, str]],
    error_code: str,
) -> None:
    contract = normalized["contract"]
    has_contract_ref = bool(contract["contract_number"] or contract["bitrix_contract_deal_id"])
    if not contract["is_active_contract"] or not has_contract_ref:
        errors.append(validation_error(locale, "contract", error_code))


@router.get("/reference-data")
async def cargo_reference_data(
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    locale = request_locale(request)
    audit_event(
        session,
        action="cargo_reference_data_viewed",
        object_type="cargo_reference_data",
        request=request,
        actor_user_id=user.id,
        metadata={"application_type_count": len(CARGO_APPLICATION_TYPES)},
    )
    session.commit()
    return {
        "application_types": [
            {
                **reference_item(locale, "cargoApplicationTypes", code),
                "product_type_code": PRODUCT_TYPE_CODES[code],
            }
            for code in CARGO_APPLICATION_TYPES
        ],
        "cargo_types": [reference_item(locale, "cargoTypes", code) for code in CARGO_TYPES],
        "transport_types": [reference_item(locale, "cargoTransportTypes", code) for code in TRANSPORT_TYPES],
        "document_types": [reference_item(locale, "cargoDocumentTypes", code) for code in DOCUMENT_TYPES],
        "currencies": [{"code": code, "label": code} for code in sorted(CURRENCIES)],
        "countries": [{"code": code, "label": t(locale, f"countries.{code}")} for code in sorted(COUNTRY_CODES)],
    }


@router.post("/applications/validate")
async def validate_cargo_application(
    payload: CargoApplicationPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    validation_status, errors, normalized, company_id = await validate_payload(session, user, request, payload)
    if errors:
        audit_event(
            session,
            action="cargo_application_validation_failed",
            object_type="cargo_application",
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=company_id,
            metadata={
                "cargo_application_type": normalized["cargo_application_type"],
                "reason_code": errors[0]["error_code"],
            },
        )
        session.commit()
    return {"status": validation_status, "errors": errors}


@router.post("/applications/draft")
async def save_cargo_application_draft(
    payload: CargoApplicationPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    validation_status, errors, normalized, company_id = await validate_payload(session, user, request, payload)
    if validation_status != "ok" or company_id is None:
        audit_event(
            session,
            action="cargo_application_validation_failed",
            object_type="cargo_application",
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=company_id,
            metadata={
                "cargo_application_type": normalized["cargo_application_type"],
                "reason_code": errors[0]["error_code"] if errors else None,
            },
        )
        session.commit()
        return {"status": "invalid", "errors": errors}

    application_type = normalized["cargo_application_type"]
    application_id = session.execute(
        insert(portal_applications)
        .values(
            application_type="cargo",
            bitrix_company_id=company_id,
            bitrix_contact_id=user.bitrix_contact_id,
            portal_status="draft",
            bitrix_category_id=CARGO_BITRIX_CATEGORY_ID,
            product_type_code=PRODUCT_TYPE_CODES[application_type],
            title_cache="Cargo application draft",
            draft_data_json=normalized,
            created_by_user_id=user.id,
            partner_user_id=user.id if user.user_type == "partner" else None,
            partner_client_request_id=parse_partner_client_request_id(normalized.get("partner_client_request_id")),
        )
        .returning(portal_applications.c.id)
    ).scalar_one()
    audit_event(
        session,
        action="cargo_application_draft_saved",
        object_type="application",
        object_id=str(application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=company_id,
        application_id=application_id,
        metadata={"cargo_application_type": application_type},
    )
    session.commit()
    return {"status": "ok", "id": f"app_{application_id}", "portal_status": "draft"}


@router.patch("/applications/{application_id}/draft")
async def update_cargo_application_draft(
    application_id: str,
    payload: CargoApplicationPayload,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    parsed_application_id = parse_application_id(application_id)
    if parsed_application_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    application = await editable_cargo_application(session, user, parsed_application_id, request)
    validation_status, errors, normalized, company_id = await validate_payload(session, user, request, payload)
    if validation_status != "ok" or company_id is None:
        audit_event(
            session,
            action="cargo_application_validation_failed",
            object_type="application",
            object_id=str(parsed_application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=company_id,
            application_id=parsed_application_id,
            metadata={
                "cargo_application_type": normalized["cargo_application_type"],
                "reason_code": errors[0]["error_code"] if errors else None,
            },
        )
        session.commit()
        return {"status": "invalid", "errors": errors}

    application_type = normalized["cargo_application_type"]
    session.execute(
        update(portal_applications)
        .where(portal_applications.c.id == application.id)
        .values(
            bitrix_company_id=company_id,
            bitrix_category_id=CARGO_BITRIX_CATEGORY_ID,
            product_type_code=PRODUCT_TYPE_CODES[application_type],
            draft_data_json=normalized,
            title_cache="Cargo application draft",
            partner_user_id=user.id if user.user_type == "partner" else application.partner_user_id,
            partner_client_request_id=parse_partner_client_request_id(normalized.get("partner_client_request_id")),
        )
    )
    audit_event(
        session,
        action="cargo_application_draft_updated",
        object_type="application",
        object_id=str(parsed_application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=company_id,
        application_id=parsed_application_id,
        metadata={"cargo_application_type": application_type},
    )
    session.commit()
    return {"status": "ok", "id": f"app_{parsed_application_id}", "portal_status": "draft"}


@router.get("/applications/{application_id}/draft")
async def get_cargo_application_draft(
    application_id: str,
    request: Request,
    session: Session = DB_SESSION,
) -> dict[str, Any]:
    user = get_current_user_from_cookie(request, session)
    parsed_application_id = parse_application_id(application_id)
    if parsed_application_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    application = await editable_cargo_application(session, user, parsed_application_id, request)
    audit_event(
        session,
        action="cargo_application_draft_viewed",
        object_type="application",
        object_id=str(parsed_application_id),
        request=request,
        actor_user_id=user.id,
        bitrix_company_id=application.bitrix_company_id,
        application_id=parsed_application_id,
        metadata={"cargo_application_type": (application.draft_data_json or {}).get("cargo_application_type")},
    )
    session.commit()
    return {
        "status": "ok",
        "id": f"app_{parsed_application_id}",
        "portal_status": application.portal_status,
        "company_id": str(application.bitrix_company_id),
        "draft_data": application.draft_data_json or {},
    }


async def editable_cargo_application(session: Session, user, application_id: int, request: Request):
    try:
        application = await policies.require_application_access(
            session,
            user,
            "edit_draft",
            application_id=application_id,
            request=request,
        )
    except PolicyError as exc:
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request) from exc
    if application.application_type != "cargo":
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    if application.portal_status not in DRAFT_EDITABLE_STATUSES:
        raise auth_error(status.HTTP_403_FORBIDDEN, "CARGO_DRAFT_NOT_EDITABLE", request)
    return application


def has_required_cargo_documents(session: Session, application_id: int, draft_data: dict[str, Any]) -> str | None:
    document_count = session.execute(
        select(func.count()).select_from(document_transfer_logs).where(
            document_transfer_logs.c.application_id == application_id,
            document_transfer_logs.c.transfer_status.in_(REQUIRED_DOCUMENT_STATUSES),
        )
    ).scalar_one()
    if document_count < 1:
        return "DOCUMENT_REQUIRED"
    application_type = draft_data.get("cargo_application_type")
    document_types = set(
        session.execute(
            select(document_transfer_logs.c.document_type).where(
                document_transfer_logs.c.application_id == application_id
            )
        ).scalars()
    )
    if application_type == "certificate" and not (
        {"certificate_basis", "invoice", "transport_document"} & document_types
    ):
        return "DOCUMENT_TYPE_REQUIRED"
    if application_type == "contract_coverage" and not (
        {"contract", "invoice", "transport_document", "other"} & document_types
    ):
        return "DOCUMENT_TYPE_REQUIRED"
    return None


def build_cargo_deal_fields(application, user, draft_data: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "TITLE": f"Portal cargo application #{application.id} / {draft_data.get('cargo_application_type') or 'cargo'}",
        "CATEGORY_ID": CARGO_BITRIX_CATEGORY_ID,
        "STAGE_ID": "C19:NEW",
        "COMPANY_ID": application.bitrix_company_id,
        "CONTACT_IDS": [user.bitrix_contact_id] if user.bitrix_contact_id else [],
        BITRIX_DEAL_FIELDS["portal_application_id"]: str(application.id),
        BITRIX_DEAL_FIELDS["portal_application_type"]: "cargo",
        BITRIX_DEAL_FIELDS["portal_source"]: "ibb_portal",
        BITRIX_DEAL_FIELDS["portal_channel"]: "partner_portal" if user.user_type == "partner" else "client_portal",
        BITRIX_DEAL_FIELDS["portal_sync_status"]: "pending",
        BITRIX_DEAL_FIELDS["portal_last_sync_at"]: date.today().isoformat(),
    }
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


@router.post("/applications/{application_id}/submit")
async def submit_cargo_application(
    application_id: str,
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
            "submit",
            application_id=parsed_application_id,
            request=request,
        )
    except PolicyError as exc:
        session.commit()
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request) from exc
    if application.application_type != "cargo":
        raise auth_error(status.HTTP_404_NOT_FOUND, "APPLICATION_NOT_FOUND", request)
    if application.portal_status not in SUBMIT_ALLOWED_STATUSES and not application.bitrix_deal_id:
        raise auth_error(status.HTTP_403_FORBIDDEN, "CARGO_DRAFT_NOT_EDITABLE", request)

    draft_data = application.draft_data_json or {}
    payload = CargoApplicationPayload.model_validate(draft_data)
    validation_status, errors, normalized, company_id = await validate_payload(session, user, request, payload)
    document_error = has_required_cargo_documents(session, parsed_application_id, normalized)
    if document_error is not None:
        errors.append(validation_error(request_locale(request), "documents", document_error))
    if validation_status != "ok" or errors or company_id is None:
        audit_event(
            session,
            action="cargo_application_submit_denied",
            object_type="application",
            object_id=str(parsed_application_id),
            request=request,
            actor_user_id=user.id,
            bitrix_company_id=application.bitrix_company_id,
            application_id=parsed_application_id,
            metadata={
                "cargo_application_type": draft_data.get("cargo_application_type"),
                "reason_code": errors[0]["error_code"],
            },
        )
        session.commit()
        return {"status": "invalid", "errors": errors}

    return await submit_application_to_bitrix(
        session=session,
        request=request,
        application_id=parsed_application_id,
        user=user,
        application_type="cargo",
        deal_fields=build_cargo_deal_fields(application, user, normalized),
        safe_metadata={"cargo_application_type": normalized["cargo_application_type"]},
        create_deal=create_deal,
        find_deal_by_portal_application_id=find_deal_by_portal_application_id,
        category_id=CARGO_BITRIX_CATEGORY_ID,
    )
