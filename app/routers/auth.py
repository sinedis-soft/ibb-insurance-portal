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
    generate_refresh_token,
    hash_email_for_rate_limit,
    hash_refresh_token,
    is_login_rate_limited,
    normalize_email,
    now_utc,
    record_failed_login,
    user_agent,
    verify_password,
)
from app.config import Settings, get_settings
from app.db import get_db
from app.models import portal_users, user_sessions

router = APIRouter(prefix="/auth", tags=["auth"])
DB_SESSION = Depends(get_db)
APP_SETTINGS = Depends(get_settings)

INVALID_CREDENTIALS = {
    "error_code": "INVALID_CREDENTIALS",
    "message": "Неверный email или пароль",
}
TOO_MANY_ATTEMPTS = {
    "error_code": "TOO_MANY_LOGIN_ATTEMPTS",
    "message": "Слишком много попыток входа. Попробуйте позже.",
}
SESSION_EXPIRED = {
    "error_code": "SESSION_EXPIRED",
    "message": "Сессия истекла",
}
USER_BLOCKED = {
    "error_code": "USER_BLOCKED",
    "message": "Пользователь заблокирован",
}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
