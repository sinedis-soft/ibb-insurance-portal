from __future__ import annotations

from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.auth import (
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    audit_event,
    client_ip,
    create_access_token,
    decode_access_token,
    ensure_aware_utc,
    generate_auth_token,
    generate_refresh_token,
    hash_auth_token,
    hash_email_for_rate_limit,
    hash_password,
    hash_refresh_token,
    is_login_rate_limited,
    is_password_reset_rate_limited,
    is_token_confirm_rate_limited,
    normalize_email,
    now_utc,
    password_policy_error,
    record_failed_login,
    user_agent,
    verify_password,
)
from app.config import Settings, get_settings
from app.db import get_db
from app.email import EmailDeliveryError, send_first_login_email, send_password_reset_email
from app.models import auth_tokens, portal_users, user_sessions

router = APIRouter(prefix="/auth", tags=["auth"])
DB_SESSION = Depends(get_db)
APP_SETTINGS = Depends(get_settings)

INVALID_CREDENTIALS = {"error_code": "INVALID_CREDENTIALS", "message": "Неверный email или пароль"}
TOO_MANY_ATTEMPTS = {"error_code": "TOO_MANY_LOGIN_ATTEMPTS", "message": "Too many login attempts"}
SESSION_EXPIRED = {"error_code": "SESSION_EXPIRED", "message": "Session expired"}
USER_BLOCKED = {"error_code": "USER_BLOCKED", "message": "User is blocked"}
TOKEN_INVALID = {"error_code": "TOKEN_INVALID", "message": "Token is invalid"}
TOKEN_EXPIRED = {"error_code": "TOKEN_EXPIRED", "message": "Token has expired"}
TOKEN_ALREADY_USED = {"error_code": "TOKEN_ALREADY_USED", "message": "Token has already been used"}
PASSWORD_TOO_WEAK = {"error_code": "PASSWORD_TOO_WEAK", "message": "Password does not meet security requirements"}
TOO_MANY_REQUESTS = {"error_code": "TOO_MANY_REQUESTS", "message": "Too many requests"}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class InviteRequest(BaseModel):
    user_id: str


class TokenPasswordRequest(BaseModel):
    token: str
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AuthError(Exception):
    def __init__(self, status_code: int, payload: dict[str, str]) -> None:
        self.status_code = status_code
        self.payload = payload


def auth_error(status_code: int, payload: dict[str, str]) -> AuthError:
    return AuthError(status_code, payload)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, settings: Settings) -> None:
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/auth",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/", secure=settings.secure_cookies, httponly=True, samesite="lax")
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path="/auth",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )


def public_user(row) -> dict[str, object]:
    return {
        "id": f"usr_{row.id}",
        "role": row.role_code,
        "user_type": row.user_type,
        "language": row.language,
        "status": row.status,
    }


def parse_public_user_id(value: str) -> int | None:
    if not value.startswith("usr_"):
        return None
    try:
        return int(value.removeprefix("usr_"))
    except ValueError:
        return None


def get_active_session(session: Session, session_id: int):
    row = session.execute(select(user_sessions).where(user_sessions.c.id == session_id)).mappings().one_or_none()
    if row is None:
        return None
    expires_at = ensure_aware_utc(row.expires_at)
    if row.revoked_at is not None or expires_at <= now_utc():
        return None
    return row


def get_current_user_from_cookie(request: Request, session: Session):
    access_token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not access_token:
        raise auth_error(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED)
    try:
        payload = decode_access_token(access_token)
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise auth_error(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED) from None
    if get_active_session(session, session_id) is None:
        raise auth_error(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED)
    user = session.execute(select(portal_users).where(portal_users.c.id == user_id)).mappings().one_or_none()
    if user is None or user.status != "active":
        raise auth_error(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED)
    return user


def require_superadmin(request: Request, session: Session):
    current_user = get_current_user_from_cookie(request, session)
    if current_user.role_code != "superadmin":
        raise auth_error(status.HTTP_403_FORBIDDEN, {"error_code": "FORBIDDEN", "message": "Forbidden"})
    return current_user


def frontend_link(path: str, token: str, settings: Settings) -> str:
    return f"{settings.resolved_frontend_base_url.rstrip('/')}{path}?token={token}"


def create_auth_token(
    session: Session,
    *,
    user_id: int,
    token_type: str,
    expires_at,
    settings: Settings,
    created_by_user_id: int | None = None,
) -> str:
    plain_token = generate_auth_token()
    session.execute(
        insert(auth_tokens).values(
            user_id=user_id,
            token_hash=hash_auth_token(plain_token, settings),
            token_type=token_type,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
        )
    )
    return plain_token


def token_error_for_row(token_row) -> AuthError | None:
    if token_row is None:
        return auth_error(status.HTTP_400_BAD_REQUEST, TOKEN_INVALID)
    if token_row.used_at is not None:
        return auth_error(status.HTTP_400_BAD_REQUEST, TOKEN_ALREADY_USED)
    if ensure_aware_utc(token_row.expires_at) <= now_utc():
        return auth_error(status.HTTP_400_BAD_REQUEST, TOKEN_EXPIRED)
    return None


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, object]:
    email = normalize_email(payload.email)
    if await is_login_rate_limited(email, client_ip(request)):
        audit_event(
            session,
            action="login_rate_limited",
            object_type="portal_user",
            request=request,
            metadata={"hashed_email": hash_email_for_rate_limit(email, settings), "reason": "rate_limit"},
        )
        session.commit()
        raise auth_error(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_ATTEMPTS)

    user = session.execute(select(portal_users).where(portal_users.c.email == email)).mappings().one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        await record_failed_login(email)
        audit_event(
            session,
            action="login_failed",
            object_type="portal_user",
            request=request,
            target_user_id=user.id if user else None,
            metadata={"hashed_email": hash_email_for_rate_limit(email, settings), "reason": "invalid_credentials"},
        )
        session.commit()
        raise auth_error(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    if user.status == "blocked":
        await record_failed_login(email)
        audit_event(
            session,
            action="blocked_user_login_attempt",
            object_type="portal_user",
            request=request,
            target_user_id=user.id,
            metadata={"reason": "user_blocked"},
        )
        session.commit()
        raise auth_error(status.HTTP_403_FORBIDDEN, USER_BLOCKED)

    if user.status != "active":
        await record_failed_login(email)
        audit_event(
            session,
            action="login_failed",
            object_type="portal_user",
            request=request,
            target_user_id=user.id,
            metadata={"reason": "user_not_active"},
        )
        session.commit()
        raise auth_error(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    refresh_token = generate_refresh_token()
    expires_at = now_utc() + timedelta(days=settings.refresh_token_ttl_days)
    session_id = session.execute(
        insert(user_sessions)
        .values(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(refresh_token, settings),
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            expires_at=expires_at,
            last_used_at=now_utc(),
        )
        .returning(user_sessions.c.id)
    ).scalar_one()
    access_token = create_access_token(user.id, user.role_code or user.user_type, session_id, settings)
    set_auth_cookies(response, access_token, refresh_token, settings)
    session.execute(update(portal_users).where(portal_users.c.id == user.id).values(last_login_at=now_utc()))
    audit_event(
        session,
        action="login_success",
        object_type="portal_user",
        request=request,
        actor_user_id=user.id,
        target_user_id=user.id,
        object_id=str(user.id),
    )
    session.commit()
    return {"user": public_user(user)}


@router.post("/invites")
def create_invite(
    payload: InviteRequest,
    request: Request,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, str]:
    actor = require_superadmin(request, session)
    user_id = parse_public_user_id(payload.user_id)
    if user_id is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, {"error_code": "USER_NOT_FOUND", "message": "User not found"})
    user = session.execute(select(portal_users).where(portal_users.c.id == user_id)).mappings().one_or_none()
    if user is None:
        raise auth_error(status.HTTP_404_NOT_FOUND, {"error_code": "USER_NOT_FOUND", "message": "User not found"})
    if user.status == "blocked":
        raise auth_error(status.HTTP_403_FORBIDDEN, USER_BLOCKED)
    token = create_auth_token(
        session,
        user_id=user.id,
        token_type="first_login",
        expires_at=now_utc() + timedelta(hours=settings.first_login_token_ttl_hours),
        created_by_user_id=actor.id,
        settings=settings,
    )
    try:
        send_first_login_email(
            to_email=user.email,
            first_login_link=frontend_link("/first-login", token, settings),
            language=user.language,
            settings=settings,
        )
    except EmailDeliveryError as exc:
        session.rollback()
        audit_event(
            session,
            action="invite_email_failed",
            object_type="portal_user",
            request=request,
            actor_user_id=actor.id,
            target_user_id=user.id,
            metadata={"error_code": str(exc)},
        )
        session.commit()
        raise auth_error(
            status.HTTP_502_BAD_GATEWAY,
            {"error_code": str(exc), "message": "Email delivery failed"},
        ) from exc
    audit_event(
        session,
        action="invite_token_created",
        object_type="auth_token",
        request=request,
        actor_user_id=actor.id,
        target_user_id=user.id,
        metadata={"token_type": "first_login"},
    )
    audit_event(
        session,
        action="invite_email_sent",
        object_type="portal_user",
        request=request,
        actor_user_id=actor.id,
        target_user_id=user.id,
    )
    session.commit()
    return {"status": "ok"}


@router.post("/first-login")
async def first_login(
    payload: TokenPasswordRequest,
    request: Request,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, str]:
    token_hash = hash_auth_token(payload.token, settings)
    if await is_token_confirm_rate_limited(token_hash, client_ip(request), settings):
        raise auth_error(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_REQUESTS)
    token_row = session.execute(
        select(auth_tokens).where(auth_tokens.c.token_hash == token_hash, auth_tokens.c.token_type == "first_login")
    ).mappings().one_or_none()
    token_error = token_error_for_row(token_row)
    if token_error:
        audit_event(
            session,
            action="first_login_failed",
            object_type="auth_token",
            request=request,
            metadata={"reason": token_error.payload["error_code"]},
        )
        session.commit()
        raise token_error
    user = session.execute(select(portal_users).where(portal_users.c.id == token_row.user_id)).mappings().one_or_none()
    if user is None:
        raise auth_error(status.HTTP_400_BAD_REQUEST, TOKEN_INVALID)
    if user.status == "blocked":
        raise auth_error(status.HTTP_403_FORBIDDEN, USER_BLOCKED)
    if password_policy_error(payload.password, user.email):
        raise auth_error(status.HTTP_400_BAD_REQUEST, PASSWORD_TOO_WEAK)
    session.execute(
        update(portal_users)
        .where(portal_users.c.id == user.id)
        .values(password_hash=hash_password(payload.password), status="active")
    )
    session.execute(
        update(auth_tokens)
        .where(auth_tokens.c.id == token_row.id)
        .values(used_at=now_utc(), ip_address_used=client_ip(request), user_agent_used=user_agent(request))
    )
    audit_event(
        session,
        action="first_login_success",
        object_type="portal_user",
        request=request,
        target_user_id=user.id,
    )
    session.commit()
    return {"status": "ok"}


@router.post("/password-reset/request")
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, str]:
    email = normalize_email(payload.email)
    if await is_password_reset_rate_limited(email, client_ip(request), settings):
        raise auth_error(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_REQUESTS)
    user = session.execute(select(portal_users).where(portal_users.c.email == email)).mappings().one_or_none()
    if user is not None and user.status != "blocked":
        token = create_auth_token(
            session,
            user_id=user.id,
            token_type="password_reset",
            expires_at=now_utc() + timedelta(minutes=settings.password_reset_token_ttl_minutes),
            settings=settings,
        )
        try:
            send_password_reset_email(
                to_email=email,
                reset_link=frontend_link("/reset-password", token, settings),
                language=user.language,
                settings=settings,
            )
        except EmailDeliveryError:
            pass
        audit_event(
            session,
            action="password_reset_requested",
            object_type="portal_user",
            request=request,
            target_user_id=user.id,
            metadata={"hashed_email": hash_email_for_rate_limit(email, settings)},
        )
    else:
        audit_event(
            session,
            action="password_reset_requested",
            object_type="portal_user",
            request=request,
            metadata={"hashed_email": hash_email_for_rate_limit(email, settings), "user_found": False},
        )
    session.commit()
    return {"status": "ok"}


@router.post("/password-reset/confirm")
async def password_reset_confirm(
    payload: TokenPasswordRequest,
    request: Request,
    response: Response,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, str]:
    token_hash = hash_auth_token(payload.token, settings)
    if await is_token_confirm_rate_limited(token_hash, client_ip(request), settings):
        raise auth_error(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_REQUESTS)
    token_row = session.execute(
        select(auth_tokens).where(auth_tokens.c.token_hash == token_hash, auth_tokens.c.token_type == "password_reset")
    ).mappings().one_or_none()
    token_error = token_error_for_row(token_row)
    if token_error:
        audit_event(
            session,
            action="password_reset_failed",
            object_type="auth_token",
            request=request,
            metadata={"reason": token_error.payload["error_code"]},
        )
        session.commit()
        raise token_error
    user = session.execute(select(portal_users).where(portal_users.c.id == token_row.user_id)).mappings().one_or_none()
    if user is None:
        raise auth_error(status.HTTP_400_BAD_REQUEST, TOKEN_INVALID)
    if user.status == "blocked":
        raise auth_error(status.HTTP_403_FORBIDDEN, USER_BLOCKED)
    if password_policy_error(payload.password, user.email):
        raise auth_error(status.HTTP_400_BAD_REQUEST, PASSWORD_TOO_WEAK)
    session.execute(
        update(portal_users)
        .where(portal_users.c.id == user.id)
        .values(password_hash=hash_password(payload.password))
    )
    session.execute(
        update(auth_tokens)
        .where(auth_tokens.c.id == token_row.id)
        .values(used_at=now_utc(), ip_address_used=client_ip(request), user_agent_used=user_agent(request))
    )
    session.execute(
        update(user_sessions)
        .where(user_sessions.c.user_id == user.id, user_sessions.c.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )
    clear_auth_cookies(response, settings)
    audit_event(
        session,
        action="password_reset_success",
        object_type="portal_user",
        request=request,
        target_user_id=user.id,
    )
    audit_event(
        session,
        action="user_sessions_revoked_after_password_reset",
        object_type="user_session",
        request=request,
        target_user_id=user.id,
    )
    session.commit()
    return {"status": "ok"}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, str]:
    user = get_current_user_from_cookie(request, session)
    if not verify_password(payload.current_password, user.password_hash):
        audit_event(
            session,
            action="password_change_failed",
            object_type="portal_user",
            request=request,
            actor_user_id=user.id,
            target_user_id=user.id,
            metadata={"reason": "invalid_current_password"},
        )
        session.commit()
        raise auth_error(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)
    if password_policy_error(payload.new_password, user.email) or verify_password(
        payload.new_password, user.password_hash
    ):
        audit_event(
            session,
            action="password_change_failed",
            object_type="portal_user",
            request=request,
            actor_user_id=user.id,
            target_user_id=user.id,
            metadata={"reason": "password_policy"},
        )
        session.commit()
        raise auth_error(status.HTTP_400_BAD_REQUEST, PASSWORD_TOO_WEAK)
    session.execute(
        update(portal_users)
        .where(portal_users.c.id == user.id)
        .values(password_hash=hash_password(payload.new_password))
    )
    session.execute(
        update(user_sessions)
        .where(user_sessions.c.user_id == user.id, user_sessions.c.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )
    clear_auth_cookies(response, settings)
    audit_event(
        session,
        action="password_changed",
        object_type="portal_user",
        request=request,
        actor_user_id=user.id,
        target_user_id=user.id,
    )
    audit_event(
        session,
        action="user_sessions_revoked_after_password_change",
        object_type="user_session",
        request=request,
        actor_user_id=user.id,
        target_user_id=user.id,
    )
    session.commit()
    return {"status": "ok"}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, str]:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    actor_user_id = None
    if refresh_token:
        refresh_hash = hash_refresh_token(refresh_token, settings)
        row = session.execute(
            select(user_sessions).where(user_sessions.c.refresh_token_hash == refresh_hash)
        ).mappings().one_or_none()
        if row is not None and row.revoked_at is None:
            actor_user_id = row.user_id
            session.execute(update(user_sessions).where(user_sessions.c.id == row.id).values(revoked_at=now_utc()))
    clear_auth_cookies(response, settings)
    audit_event(
        session,
        action="logout",
        object_type="user_session",
        request=request,
        actor_user_id=actor_user_id,
    )
    session.commit()
    return {"status": "ok"}


@router.get("/me")
def me(request: Request, session: Session = DB_SESSION) -> dict[str, object]:
    return public_user(get_current_user_from_cookie(request, session))


@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    session: Session = DB_SESSION,
    settings: Settings = APP_SETTINGS,
) -> dict[str, str]:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise auth_error(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED)
    refresh_hash = hash_refresh_token(refresh_token, settings)
    session_row = session.execute(
        select(user_sessions).where(user_sessions.c.refresh_token_hash == refresh_hash)
    ).mappings().one_or_none()
    if session_row is None or get_active_session(session, session_row.id) is None:
        audit_event(
            session,
            action="refresh_failed",
            object_type="user_session",
            request=request,
            metadata={"reason": "session_expired"},
        )
        session.commit()
        raise auth_error(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED)
    user = session.execute(
        select(portal_users).where(portal_users.c.id == session_row.user_id)
    ).mappings().one_or_none()
    if user is None or user.status != "active":
        audit_event(
            session,
            action="refresh_failed",
            object_type="user_session",
            request=request,
            actor_user_id=session_row.user_id,
            metadata={"reason": "user_inactive"},
        )
        session.commit()
        raise auth_error(status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED)
    new_refresh_token = generate_refresh_token()
    session.execute(
        update(user_sessions)
        .where(user_sessions.c.id == session_row.id)
        .values(refresh_token_hash=hash_refresh_token(new_refresh_token, settings), last_used_at=now_utc())
    )
    set_auth_cookies(
        response,
        create_access_token(user.id, user.role_code or user.user_type, session_row.id, settings),
        new_refresh_token,
        settings,
    )
    session.commit()
    return {"status": "ok"}
