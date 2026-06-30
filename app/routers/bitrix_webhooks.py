from __future__ import annotations

import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.auth import (
    audit_event,
    generate_invite_token,
    generate_temporary_password,
    hash_invite_token,
    hash_password,
    normalize_email,
    now_utc,
)
from app.bitrix import (
    BitrixError,
    company_ids_from_contact_company_bindings,
    contact_company_id_from_contact,
    contact_display_name_from_contact,
    contact_language_from_contact,
    get_company,
    get_contact,
    get_contact_company_bindings,
    latest_email_from_contact,
)
from app.company_access import OPEN_ACCESS_STATUSES
from app.config import Settings, get_settings
from app.db import get_db
from app.email import EmailDeliveryError, send_invite_email
from app.models import invite_tokens, partner_client_requests, portal_users, roles, user_company_roles
from app.partner_client_requests import (
    PARTNER_CLIENT_LINKED_DECISION,
    PARTNER_CLIENT_STATUS_AUDIT_ACTIONS,
    ensure_partner_client_link,
    portal_status_from_bitrix_partner_client_check,
)
from app.routers.auth import AuthError

router = APIRouter(prefix="/bitrix/outbound", tags=["bitrix-webhooks"])
DB_SESSION = Depends(get_db)
APP_SETTINGS = Depends(get_settings)

CLIENT_ROLES = {"client_executor", "client_admin", "client_viewer"}


def webhook_error(status_code: int, error_code: str, message: str = "Webhook request failed") -> AuthError:
    return AuthError(status_code, {"error_code": error_code, "message": message})


def query_value(request: Request, *names: str) -> str | None:
    for name in names:
        value = request.query_params.get(name)
        if value:
            return value.strip()
    return None


def validate_secret(provided_secret: str, settings: Settings) -> None:
    if not settings.bitrix_outbound_webhook_secret or settings.bitrix_outbound_webhook_secret == "replace_me":
        raise webhook_error(status.HTTP_503_SERVICE_UNAVAILABLE, "WEBHOOK_NOT_CONFIGURED")
    if not hmac.compare_digest(provided_secret, settings.bitrix_outbound_webhook_secret):
        raise webhook_error(status.HTTP_403_FORBIDDEN, "WEBHOOK_FORBIDDEN")


def validate_request_params(request: Request) -> tuple[str, str | None, int]:
    account_type = query_value(request, "account_type", "client_or_partner", "type")
    role_code = query_value(request, "role", "role_code")
    contact_id_value = query_value(request, "bitrix_contact_id", "contact_id")

    if account_type not in {"client", "partner"}:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_ACCOUNT_TYPE")
    if account_type == "client" and role_code not in CLIENT_ROLES:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_ROLE")
    if account_type == "partner" and role_code:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "PARTNER_ROLE_FORBIDDEN")
    try:
        contact_id = int(contact_id_value or "")
    except ValueError:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_BITRIX_CONTACT_ID") from None
    if contact_id <= 0:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_BITRIX_CONTACT_ID")
    return account_type, role_code, contact_id


def parse_optional_positive_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def validate_partner_client_check_status_params(
    request: Request,
) -> tuple[int, str, str, int | None, str | None, int | None]:
    company_id_value = query_value(request, "bitrix_company_id", "company_id")
    raw_status = query_value(request, "status", "status_id", "check_status", "stage")
    linked_company_id = parse_optional_positive_int(
        query_value(request, "linked_bitrix_company_id", "linked_company_id")
    )
    reason = query_value(request, "reason")
    bitrix_user_id = parse_optional_positive_int(query_value(request, "bitrix_user_id", "user_id"))
    try:
        company_id = int(company_id_value or "")
    except ValueError:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_BITRIX_COMPANY_ID") from None
    if company_id <= 0:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_BITRIX_COMPANY_ID")
    portal_status = portal_status_from_bitrix_partner_client_check(raw_status)
    if portal_status == "duplicate_found" and linked_company_id is not None:
        portal_status = PARTNER_CLIENT_LINKED_DECISION
    if portal_status is None:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "PARTNER_CLIENT_STATUS_INVALID")
    if portal_status == PARTNER_CLIENT_LINKED_DECISION and linked_company_id is None:
        raise webhook_error(422, "LINKED_BITRIX_COMPANY_REQUIRED")
    return company_id, portal_status, str(raw_status or ""), linked_company_id, reason, bitrix_user_id


def build_invite_link(invite_token: str, settings: Settings) -> str:
    return f"{settings.portal_public_url.rstrip('/')}/invite?token={invite_token}"


def user_needs_reinvite(user) -> bool:
    return user.status != "blocked" and user.last_login_at is None


def create_invite_token(session: Session, *, user_id: int, settings: Settings) -> str:
    invite_token = generate_invite_token()
    now = now_utc()
    session.execute(
        update(invite_tokens)
        .where(invite_tokens.c.user_id == user_id, invite_tokens.c.used_at.is_(None))
        .values(used_at=now)
    )
    session.execute(
        insert(invite_tokens).values(
            user_id=user_id,
            token_hash=hash_invite_token(invite_token, settings),
            expires_at=now + timedelta(hours=settings.invite_token_ttl_hours),
        )
    )
    return invite_token


def issue_bitrix_invite(
    session: Session,
    *,
    user_id: int,
    email: str,
    language: str,
    settings: Settings,
) -> None:
    temporary_password = generate_temporary_password()
    session.execute(
        update(portal_users)
        .where(portal_users.c.id == user_id)
        .values(password_hash=hash_password(temporary_password), status="active")
    )
    invite_token = create_invite_token(session, user_id=user_id, settings=settings)
    send_invite_email(
        to_email=email,
        invite_link=build_invite_link(invite_token, settings),
        temporary_password=temporary_password,
        language=language,
        settings=settings,
    )


@router.post("/{secret}/1/partner-client-check-status")
async def update_partner_client_check_status_from_bitrix(
    secret: str,
    request: Request,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, object]:
    validate_secret(secret, settings)
    company_id, portal_status, raw_status, linked_company_id, reason, bitrix_user_id = (
        validate_partner_client_check_status_params(request)
    )
    row = (
        session.execute(
            select(partner_client_requests).where(
                partner_client_requests.c.bitrix_check_entity_type == "company",
                partner_client_requests.c.bitrix_check_entity_id == company_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        audit_event(
            session,
            action="partner_client_check_sync_failed",
            object_type="partner_client_request",
            request=request,
            bitrix_company_id=company_id,
            metadata={"error_code": "PARTNER_CLIENT_REQUEST_NOT_FOUND", "source": "bitrix_webhook"},
        )
        session.commit()
        raise webhook_error(status.HTTP_404_NOT_FOUND, "PARTNER_CLIENT_REQUEST_NOT_FOUND")

    now = now_utc()
    final_company_id = linked_company_id if portal_status == PARTNER_CLIENT_LINKED_DECISION else company_id
    stored_status = "confirmed" if portal_status == PARTNER_CLIENT_LINKED_DECISION else portal_status
    stored_check_status = "confirmed" if portal_status == PARTNER_CLIENT_LINKED_DECISION else portal_status
    is_repeat = (
        row.status == stored_status
        and row.bitrix_check_status == stored_check_status
        and (row.linked_bitrix_company_id or None) == (linked_company_id or None)
        and (row.confirmed_bitrix_company_id or None) == (final_company_id if stored_status == "confirmed" else None)
    )

    update_values: dict[str, object] = {
        "status": stored_status,
        "bitrix_check_status": stored_check_status,
        "bitrix_sync_status": "synced",
        "bitrix_sync_error_code": None,
        "bitrix_sync_error": None,
        "bitrix_synced_at": now,
        "decision_status": portal_status,
        "decision_reason": reason if portal_status == "rejected" else None,
        "decided_at": row.decided_at or now,
        "decided_by_bitrix_user_id": bitrix_user_id,
    }
    if row.original_bitrix_company_id is None:
        update_values["original_bitrix_company_id"] = company_id
    if stored_status == "confirmed":
        update_values["confirmed_company_id"] = final_company_id
        update_values["confirmed_bitrix_company_id"] = final_company_id
    if portal_status == PARTNER_CLIENT_LINKED_DECISION:
        update_values["linked_to_existing"] = True
        update_values["linked_bitrix_company_id"] = linked_company_id
    elif portal_status != "rejected":
        update_values["linked_to_existing"] = False
        update_values["linked_bitrix_company_id"] = None
    if portal_status == "rejected":
        update_values["rejection_reason"] = reason
    session.execute(
        update(partner_client_requests)
        .where(partner_client_requests.c.id == row.id)
        .values(**update_values)
    )
    if stored_status == "confirmed" and final_company_id is not None:
        ensure_partner_client_link(
            session,
            partner_user_id=row.partner_user_id,
            bitrix_company_id=final_company_id,
            created_by_user_id=None,
        )

    audit_event(
        session,
        action="partner_client_check_status_updated",
        object_type="partner_client_request",
        object_id=str(row.id),
        request=request,
        actor_user_id=None,
        bitrix_company_id=final_company_id,
        metadata={
            "old_status": row.status,
            "new_status": portal_status,
            "source": "bitrix_webhook",
            "bitrix_status": raw_status,
            "partner_id": row.partner_user_id,
            "partner_client_request_id": row.id,
            "original_bitrix_company_id": row.original_bitrix_company_id or company_id,
            "linked_bitrix_company_id": linked_company_id,
            "final_bitrix_company_id": final_company_id,
        },
    )
    if is_repeat:
        audit_event(
            session,
            action="partner_client_check_webhook_repeated",
            object_type="partner_client_request",
            object_id=str(row.id),
            request=request,
            actor_user_id=None,
            bitrix_company_id=final_company_id,
            metadata={"source": "bitrix_webhook", "new_status": portal_status},
        )
    specific_action = PARTNER_CLIENT_STATUS_AUDIT_ACTIONS.get(portal_status)
    if specific_action and not is_repeat:
        audit_event(
            session,
            action=specific_action,
            object_type="partner_client_request",
            object_id=str(row.id),
            request=request,
            actor_user_id=None,
            bitrix_company_id=final_company_id,
            metadata={
                "source": "bitrix_webhook",
                "old_status": row.status,
                "new_status": portal_status,
                "partner_id": row.partner_user_id,
                "original_bitrix_company_id": row.original_bitrix_company_id or company_id,
                "linked_bitrix_company_id": linked_company_id,
                "final_bitrix_company_id": final_company_id,
            },
        )
    session.commit()
    return {"status": "updated", "client_request_id": f"pcr_{row.id}", "portal_status": portal_status}


async def company_cache_from_bitrix(company_id: int, settings: Settings) -> tuple[str, str, dict[str, object]]:
    try:
        company = await get_company(company_id, settings)
    except BitrixError:
        return "pending", "bitrix_unavailable", {}
    return (
        "active",
        "confirmed",
        {
            "company_title_cache": company.get("TITLE"),
            "company_country_code_cache": company.get("ADDRESS_COUNTRY_CODE")
            or company.get("REG_ADDRESS_COUNTRY_CODE"),
            "bitrix_updated_at_cache": company.get("DATE_MODIFY"),
            "cache_refreshed_at": now_utc(),
        },
    )


async def company_ids_from_bitrix_contact(contact_id: int, contact: dict, settings: Settings) -> list[int]:
    try:
        bindings = await get_contact_company_bindings(contact_id, settings)
        company_ids = company_ids_from_contact_company_bindings(bindings)
    except BitrixError:
        fallback_company_id = contact_company_id_from_contact(contact)
        return [fallback_company_id] if fallback_company_id is not None else []

    if company_ids:
        return company_ids
    if bindings:
        return []
    fallback_company_id = contact_company_id_from_contact(contact)
    return [fallback_company_id] if fallback_company_id is not None else []


async def sync_user_contact_cache(
    session: Session,
    *,
    user_id: int,
    contact_id: int,
    contact: dict,
    account_type: str,
    role_code: str | None,
    request: Request,
    settings: Settings,
) -> None:
    display_name = contact_display_name_from_contact(contact)
    contact_language = contact_language_from_contact(contact)
    update_values: dict[str, object] = {
        "language": contact_language,
        "bitrix_contact_id": contact_id,
        "display_name_cache": display_name,
    }
    if account_type == "client" and role_code:
        update_values["role_code"] = role_code
    session.execute(update(portal_users).where(portal_users.c.id == user_id).values(**update_values))

    if account_type != "client" or not role_code:
        return

    company_ids = await company_ids_from_bitrix_contact(contact_id, contact, settings)
    if not company_ids:
        return

    for company_id in company_ids:
        existing_role_id = session.execute(
            select(user_company_roles.c.id).where(
                user_company_roles.c.user_id == user_id,
                user_company_roles.c.bitrix_company_id == company_id,
                user_company_roles.c.access_status.in_(OPEN_ACCESS_STATUSES),
            )
        ).scalar_one_or_none()
        if existing_role_id is not None:
            access_status, bitrix_link_status, company_cache = await company_cache_from_bitrix(company_id, settings)
            update_values: dict[str, object] = {"role_code": role_code, **company_cache}
            if access_status == "active":
                update_values["bitrix_link_status"] = bitrix_link_status
            session.execute(
                update(user_company_roles)
                .where(user_company_roles.c.id == existing_role_id)
                .values(**update_values)
            )
            continue

        access_status, bitrix_link_status, company_cache = await company_cache_from_bitrix(company_id, settings)
        role_link_id = session.execute(
            insert(user_company_roles)
            .values(
                user_id=user_id,
                bitrix_company_id=company_id,
                role_code=role_code,
                access_status=access_status,
                bitrix_link_status=bitrix_link_status,
                confirmed_at=now_utc() if access_status == "active" else None,
                **company_cache,
            )
            .returning(user_company_roles.c.id)
        ).scalar_one()
        audit_event(
            session,
            action="company_role_created_from_bitrix_contact",
            object_type="user_company_role",
            object_id=str(role_link_id),
            request=request,
            target_user_id=user_id,
            metadata={
                "bitrix_contact_id": contact_id,
                "bitrix_company_id": company_id,
                "role_code": role_code,
                "access_status": access_status,
                "bitrix_link_status": bitrix_link_status,
            },
        )


def maybe_reinvite_existing_user(
    session: Session,
    *,
    user,
    request: Request,
    contact_id: int,
    settings: Settings,
    found_by: str,
) -> dict[str, object]:
    if not user_needs_reinvite(user):
        audit_event(
            session,
            action="bitrix_user_invite_existing",
            object_type="portal_user",
            request=request,
            target_user_id=user.id,
            object_id=str(user.id),
            metadata={
                "bitrix_contact_id": contact_id,
                "user_type": user.user_type,
                "status": user.status,
                "found_by": found_by,
                "reinvite_sent": False,
            },
        )
        session.commit()
        return {"status": "exists", "user_id": f"usr_{user.id}"}

    try:
        issue_bitrix_invite(
            session,
            user_id=user.id,
            email=user.email,
            language=user.language,
            settings=settings,
        )
    except EmailDeliveryError as exc:
        session.rollback()
        audit_event(
            session,
            action="bitrix_user_reinvite_email_failed",
            object_type="portal_user",
            request=request,
            target_user_id=user.id,
            object_id=str(user.id),
            metadata={"bitrix_contact_id": contact_id, "error_code": str(exc), "found_by": found_by},
        )
        session.commit()
        raise webhook_error(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    audit_event(
        session,
        action="bitrix_user_reinvited_before_first_login",
        object_type="portal_user",
        request=request,
        target_user_id=user.id,
        object_id=str(user.id),
        metadata={
            "bitrix_contact_id": contact_id,
            "user_type": user.user_type,
            "status": user.status,
            "found_by": found_by,
            "reinvite_sent": True,
        },
    )
    session.commit()
    return {"status": "reinvited", "user_id": f"usr_{user.id}"}


@router.post("/{secret}/1/sync-contact-companies")
async def sync_contact_companies_from_bitrix(
    secret: str,
    request: Request,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, object]:
    validate_secret(secret, settings)

    contact_id_value = query_value(request, "bitrix_contact_id", "contact_id")
    try:
        contact_id = int(contact_id_value or "")
    except ValueError:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_BITRIX_CONTACT_ID") from None

    if contact_id <= 0:
        raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_BITRIX_CONTACT_ID")

    user = (
        session.execute(select(portal_users).where(portal_users.c.bitrix_contact_id == contact_id))
        .mappings()
        .one_or_none()
    )
    if user is None:
        raise webhook_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND")

    try:
        contact = await get_contact(contact_id, settings)
    except BitrixError as exc:
        audit_event(
            session,
            action="bitrix_contact_fetch_failed",
            object_type="bitrix_contact",
            object_id=str(contact_id),
            request=request,
            metadata={"bitrix_contact_id": contact_id, "error_code": exc.error_code},
        )
        session.commit()
        raise webhook_error(status.HTTP_502_BAD_GATEWAY, exc.error_code) from exc

    await sync_user_contact_cache(
        session,
        user_id=user.id,
        contact_id=contact_id,
        contact=contact,
        account_type=user.user_type,
        role_code=user.role_code,
        request=request,
        settings=settings,
    )

    audit_event(
        session,
        action="contact_companies_synced_from_bitrix",
        object_type="portal_user",
        object_id=str(user.id),
        request=request,
        target_user_id=user.id,
        metadata={"bitrix_contact_id": contact_id},
    )

    session.commit()
    return {"status": "ok", "user_id": f"usr_{user.id}"}


@router.post("/{secret}/1/create-user")
async def create_user_from_bitrix(
    secret: str,
    request: Request,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, object]:
    validate_secret(secret, settings)
    account_type, role_code, contact_id = validate_request_params(request)

    if role_code:
        role_exists = session.execute(
            select(roles.c.id).where(roles.c.code == role_code, roles.c.is_active.is_(True))
        ).scalar_one_or_none()
        if role_exists is None:
            raise webhook_error(status.HTTP_400_BAD_REQUEST, "INVALID_ROLE")

    try:
        contact = await get_contact(contact_id, settings)
    except BitrixError as exc:
        audit_event(
            session,
            action="bitrix_contact_fetch_failed",
            object_type="bitrix_contact",
            object_id=str(contact_id),
            request=request,
            metadata={"bitrix_contact_id": contact_id, "error_code": exc.error_code},
        )
        session.commit()
        raise webhook_error(status.HTTP_502_BAD_GATEWAY, exc.error_code) from exc

    existing_user = (
        session.execute(select(portal_users).where(portal_users.c.bitrix_contact_id == contact_id))
        .mappings()
        .one_or_none()
    )
    if existing_user is not None:
        await sync_user_contact_cache(
            session,
            user_id=existing_user.id,
            contact_id=contact_id,
            contact=contact,
            account_type=account_type,
            role_code=role_code,
            request=request,
            settings=settings,
        )
        return maybe_reinvite_existing_user(
            session,
            request=request,
            user=existing_user,
            contact_id=contact_id,
            settings=settings,
            found_by="bitrix_contact_id",
        )

    email = latest_email_from_contact(contact)
    if not email:
        raise webhook_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "CONTACT_EMAIL_NOT_FOUND")
    normalized_email = normalize_email(email)
    contact_language = contact_language_from_contact(contact)

    existing_by_email = session.execute(
        select(portal_users).where(portal_users.c.email == normalized_email)
    ).mappings().one_or_none()
    if existing_by_email is not None:
        await sync_user_contact_cache(
            session,
            user_id=existing_by_email.id,
            contact_id=contact_id,
            contact=contact,
            account_type=account_type,
            role_code=role_code,
            request=request,
            settings=settings,
        )
        return maybe_reinvite_existing_user(
            session,
            request=request,
            user=existing_by_email,
            contact_id=contact_id,
            settings=settings,
            found_by="email",
        )

    temporary_password = generate_temporary_password()
    display_name = contact_display_name_from_contact(contact)
    user_id = session.execute(
        insert(portal_users)
        .values(
            email=normalized_email,
            password_hash=hash_password(temporary_password),
            status="active",
            user_type=account_type,
            role_code=role_code if account_type == "client" else None,
            language=contact_language,
            bitrix_contact_id=contact_id,
            display_name_cache=display_name,
        )
        .returning(portal_users.c.id)
    ).scalar_one()
    await sync_user_contact_cache(
        session,
        user_id=user_id,
        contact_id=contact_id,
        contact=contact,
        account_type=account_type,
        role_code=role_code,
        request=request,
        settings=settings,
    )

    try:
        invite_token = create_invite_token(session, user_id=user_id, settings=settings)
        send_invite_email(
            to_email=normalized_email,
            invite_link=build_invite_link(invite_token, settings),
            temporary_password=temporary_password,
            language=contact_language,
            settings=settings,
        )
    except EmailDeliveryError as exc:
        session.rollback()
        audit_event(
            session,
            action="bitrix_user_invite_email_failed",
            object_type="portal_user",
            request=request,
            metadata={"bitrix_contact_id": contact_id, "error_code": str(exc)},
        )
        session.commit()
        raise webhook_error(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    audit_event(
        session,
        action="user_created_from_bitrix_contact",
        object_type="portal_user",
        object_id=str(user_id),
        request=request,
        target_user_id=user_id,
        metadata={
            "bitrix_contact_id": contact_id,
            "user_type": account_type,
            "role_code": role_code,
            "language": contact_language,
        },
    )
    session.commit()
    return {"status": "created", "user_id": f"usr_{user_id}"}
