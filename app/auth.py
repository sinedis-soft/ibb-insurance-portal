from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import audit_logs

ACCESS_COOKIE_NAME = "ibb_access_token"
REFRESH_COOKIE_NAME = "ibb_refresh_token"
JWT_ALGORITHM = "HS256"

password_hasher = PasswordHasher()


def now_utc() -> datetime:
    return datetime.now(UTC)


def ensure_aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_with_secret(value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def generate_temporary_password() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(18))


def hash_refresh_token(refresh_token: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return hash_with_secret(refresh_token, resolved.cookie_secret)


def hash_invite_token(invite_token: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return hash_with_secret(invite_token, resolved.cookie_secret)


def hash_email_for_rate_limit(email: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return hash_with_secret(normalize_email(email), resolved.cookie_secret)


def create_access_token(user_id: int, role: str, session_id: int, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    expires_at = now_utc() + timedelta(minutes=resolved.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "role": role,
        "type": "access",
        "exp": expires_at,
        "iat": now_utc(),
    }
    return jwt.encode(payload, resolved.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    resolved = settings or get_settings()
    return jwt.decode(token, resolved.jwt_secret, algorithms=[JWT_ALGORITHM])


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    return value[:512] if value else None


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def audit_event(
    session: Session,
    *,
    action: str,
    object_type: str,
    request: Request,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    object_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    safe_metadata = {"request_id": request_id(request)}
    safe_metadata.update(metadata or {})
    session.execute(
        insert(audit_logs).values(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            metadata_json={key: value for key, value in safe_metadata.items() if value is not None},
        )
    )


async def get_redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def increment_counter(redis: Redis, key: str, ttl_seconds: int) -> int:
    value = await redis.incr(key)
    if value == 1:
        await redis.expire(key, ttl_seconds)
    return int(value)


async def is_login_rate_limited(email: str, ip_address: str | None) -> bool:
    settings = get_settings()
    redis = await get_redis_client()
    try:
        window_seconds = 15 * 60
        email_hash = hash_email_for_rate_limit(email, settings)
        ip_hash = hash_with_secret(ip_address or "unknown", settings.cookie_secret)
        email_attempts = int(await redis.get(f"auth:login:email:{email_hash}") or 0)
        ip_attempts = await increment_counter(redis, f"auth:login:ip:{ip_hash}", window_seconds)
        return email_attempts >= 5 or ip_attempts > 20
    finally:
        await redis.aclose()


async def record_failed_login(email: str) -> None:
    settings = get_settings()
    redis = await get_redis_client()
    try:
        await increment_counter(redis, f"auth:login:email:{hash_email_for_rate_limit(email, settings)}", 15 * 60)
    finally:
        await redis.aclose()
