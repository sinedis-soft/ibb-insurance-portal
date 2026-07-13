from __future__ import annotations

import hashlib
import hmac
import re
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


def generate_auth_token() -> str:
    return secrets.token_urlsafe(48)


def generate_temporary_password() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(18))


def hash_refresh_token(refresh_token: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return hash_with_secret(refresh_token, resolved.cookie_secret)


def hash_invite_token(invite_token: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return hash_with_secret(invite_token, resolved.cookie_secret)


def hash_auth_token(auth_token: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return hash_with_secret(auth_token, resolved.cookie_secret)


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


SENSITIVE_AUDIT_KEY_PARTS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "secret",
        "client_secret",
        "webhook_secret",
        "email",
        "phone",
        "name",
        "first_name",
        "last_name",
        "comment",
        "description",
        "document_content",
        "file_content",
        "request_body",
        "response_body",
        "passport",
        "vin",
        "registration_number",
        "bank_account",
    }
)
_EMAIL_RE = re.compile(r"(?i)[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}")
_TOKENISH_RE = re.compile(r"(?i)\b(?:bearer|token|secret|password|cookie|authorization)\s*[:=]\s*[^\s,;]+")
_PHONE_RE = re.compile(r"(?<!\d)\+?\d[\d\s().-]{7,}\d(?!\d)")


def _is_sensitive_audit_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_AUDIT_KEY_PARTS)


def _sanitize_audit_string(value: str) -> str:
    sanitized = _EMAIL_RE.sub("[redacted-email]", value)
    sanitized = _TOKENISH_RE.sub("[redacted-secret]", sanitized)
    sanitized = _PHONE_RE.sub("[redacted-phone]", sanitized)
    if len(sanitized) > 1024:
        return sanitized[:1024] + "…"
    return sanitized


def sanitize_audit_metadata(value: Any) -> Any:
    """Recursively remove personal data and secrets from audit metadata."""
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            sanitized[key] = "[redacted]" if _is_sensitive_audit_key(key) else sanitize_audit_metadata(raw_value)
        return sanitized
    if isinstance(value, list | tuple | set):
        return [sanitize_audit_metadata(item) for item in value]
    if isinstance(value, str):
        return _sanitize_audit_string(value)
    return value


AUDIT_CATEGORIES = {
    "login": "authentication",
    "logout": "authentication",
    "refresh": "authentication",
    "session": "authentication",
    "all_user_sessions": "authentication",
    "two_factor": "authentication",
    "password": "authentication",
    "first_login": "authentication",
    "invite": "authentication",
    "access": "access_control",
    "company_access": "access_control",
    "role": "user_management",
    "user_": "user_management",
    "bitrix_contact": "user_management",
    "bitrix_company": "user_management",
    "application": "application",
    "auto_application": "application",
    "cargo_application": "application",
    "policy": "application",
    "document": "document",
    "delegation": "delegation",
    "delegated": "delegation",
    "superadmin_impersonation": "impersonation",
    "impersonation": "impersonation",
    "integration": "integration",
    "webhook": "integration",
}


def audit_category_for(action: str, object_type: str | None = None) -> str:
    for prefix, category in AUDIT_CATEGORIES.items():
        if action.startswith(prefix):
            return category
    if object_type == "integration_error":
        return "integration"
    if object_type in {"portal_user", "user_company_role"}:
        return "user_management"
    if object_type == "user_session":
        return "authentication"
    return "system"


def audit_result_for(action: str, metadata: dict[str, Any]) -> str:
    explicit = metadata.get("result") or metadata.get("status")
    if explicit in {"success", "denied", "failed", "cancelled"}:
        return str(explicit)
    if "denied" in action or action.endswith("_rejected"):
        return "denied"
    if "failed" in action or "error" in action:
        return "failed"
    if "cancelled" in action:
        return "cancelled"
    return "success"


def audit_event(
    session: Session,
    *,
    action: str,
    object_type: str,
    request: Request | None,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    company_group_id: int | None = None,
    bitrix_company_id: int | None = None,
    application_id: int | None = None,
    bitrix_deal_id: int | None = None,
    object_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    effective_user_id = getattr(request.state, "audit_effective_user_id", None) if request else None
    impersonation_session_id = getattr(request.state, "impersonation_session_id", None) if request else None
    impersonation_actor_user_id = getattr(request.state, "audit_actor_user_id", None) if request else None
    resolved_actor_user_id = impersonation_actor_user_id or actor_user_id
    safe_metadata = {
        "request_id": request_id(request) if request else None,
        "correlation_id": request_id(request) if request else None,
        "category": audit_category_for(action, object_type),
        "event_type": action,
    }
    safe_metadata.update(metadata or {})
    if effective_user_id is not None:
        safe_metadata.setdefault("effective_user_id", effective_user_id)
    if impersonation_session_id is not None:
        safe_metadata.setdefault("impersonation_session_id", f"imp_{impersonation_session_id}")
    safe_metadata["result"] = audit_result_for(action, safe_metadata)
    if "reason" in safe_metadata and "reason_code" not in safe_metadata:
        safe_metadata["reason_code"] = safe_metadata["reason"]
    safe_metadata = sanitize_audit_metadata({key: value for key, value in safe_metadata.items() if value is not None})
    session.execute(
        insert(audit_logs).values(
            actor_user_id=resolved_actor_user_id,
            target_user_id=target_user_id,
            company_group_id=company_group_id,
            bitrix_company_id=bitrix_company_id,
            application_id=application_id,
            bitrix_deal_id=bitrix_deal_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            ip_address=client_ip(request) if request else None,
            user_agent=user_agent(request) if request else None,
            metadata_json=safe_metadata,
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


COMMON_PASSWORDS = {"password", "12345678", "qwerty", "admin", "admin123"}


def password_policy_error(password: str, email: str | None = None) -> str | None:
    normalized_password = password.strip()
    if len(normalized_password) < 10:
        return "PASSWORD_TOO_WEAK"
    if not any(char.isalpha() for char in normalized_password):
        return "PASSWORD_TOO_WEAK"
    if not any(char.isdigit() for char in normalized_password):
        return "PASSWORD_TOO_WEAK"
    if normalized_password.lower() in COMMON_PASSWORDS:
        return "PASSWORD_TOO_WEAK"
    if email and normalized_password.lower() == normalize_email(email):
        return "PASSWORD_TOO_WEAK"
    return None


async def is_password_reset_rate_limited(email: str, ip_address: str | None, settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    redis = await get_redis_client()
    try:
        window_seconds = 60 * 60
        email_hash = hash_email_for_rate_limit(email, resolved)
        ip_hash = hash_with_secret(ip_address or "unknown", resolved.cookie_secret)
        email_attempts = await increment_counter(redis, f"auth:reset:email:{email_hash}", window_seconds)
        ip_attempts = await increment_counter(redis, f"auth:reset:ip:{ip_hash}", window_seconds)
        return email_attempts > 5 or ip_attempts > 20
    finally:
        await redis.aclose()


async def is_token_confirm_rate_limited(
    token_hash: str,
    ip_address: str | None,
    settings: Settings | None = None,
) -> bool:
    resolved = settings or get_settings()
    redis = await get_redis_client()
    try:
        window_seconds = 15 * 60
        ip_hash = hash_with_secret(ip_address or "unknown", resolved.cookie_secret)
        ip_attempts = await increment_counter(redis, f"auth:token-confirm:ip:{ip_hash}", window_seconds)
        token_attempts = await increment_counter(redis, f"auth:token-confirm:token:{token_hash[:16]}", window_seconds)
        return ip_attempts > 30 or token_attempts > 10
    finally:
        await redis.aclose()
