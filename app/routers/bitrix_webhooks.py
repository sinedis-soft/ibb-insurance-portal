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
from app.bitrix import BitrixError, contact_language_from_contact, get_contact, latest_email_from_contact
from app.config import Settings, get_settings
from app.db import get_db
from app.email import EmailDeliveryError, send_invite_email
from app.models import invite_tokens, portal_users, roles
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

    existing_user = session.execute(
        select(portal_users).where(portal_users.c.bitrix_contact_id == contact_id)
    ).mappings().one_or_none()
    if existing_user is not None:
        return maybe_reinvite_existing_user(
            session,
            request=request,
            user=existing_user,
            contact_id=contact_id,
            settings=settings,
            found_by="bitrix_contact_id",
        )

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

    email = latest_email_from_contact(contact)
    if not email:
        raise webhook_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "CONTACT_EMAIL_NOT_FOUND")
    normalized_email = normalize_email(email)
    contact_language = contact_language_from_contact(contact)

    existing_by_email = session.execute(
        select(portal_users).where(portal_users.c.email == normalized_email)
    ).mappings().one_or_none()
    if existing_by_email is not None:
        return maybe_reinvite_existing_user(
            session,
            request=request,
            user=existing_by_email,
            contact_id=contact_id,
            settings=settings,
            found_by="email",
        )

    temporary_password = generate_temporary_password()
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
        )
        .returning(portal_users.c.id)
    ).scalar_one()

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
