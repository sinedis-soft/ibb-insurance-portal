# ruff: noqa: E501,F401
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import timedelta
from email.message import EmailMessage
from html import escape
from typing import Any

from sqlalchemy import insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import audit_event, ensure_aware_utc, hash_with_secret, now_utc, sanitize_audit_metadata
from app.config import Settings, get_settings
from app.email import EmailDeliveryError, html_shell, send_message
from app.i18n import DEFAULT_LOCALE, normalize_locale
from app.models import auth_tokens, email_messages, integration_errors, portal_users

EMAIL_STATUSES = {"pending", "processing", "sent", "retry_scheduled", "failed", "cancelled", "delivered", "bounced", "rejected"}
RETRYABLE_ERROR_CODES = {"EMAIL_DELIVERY_FAILED", "SMTP_TEMPORARY_FAILURE", "SMTP_TIMEOUT", "EMAIL_NOT_CONFIGURED"}
TOKEN_TEMPLATE_CODES = {"user_invite", "password_reset"}
_ALLOWED_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@dataclass(frozen=True)
class EmailTemplate:
    code: str
    version: int
    category: str
    mandatory: bool
    active: bool
    required_variables: frozenset[str]
    optional_variables: frozenset[str] = frozenset()

    @property
    def allowed_variables(self) -> frozenset[str]:
        return self.required_variables | self.optional_variables


EMAIL_TEMPLATES: dict[str, EmailTemplate] = {
    "user_invite": EmailTemplate("user_invite", 1, "authentication", True, True, frozenset({"action_url", "expires_at", "support_contact"})),
    "password_reset": EmailTemplate("password_reset", 1, "authentication", True, True, frozenset({"action_url", "expires_at", "support_contact"})),
    "password_changed": EmailTemplate("password_changed", 1, "authentication", False, True, frozenset({"portal_url", "event_date"})),
    "application_submitted": EmailTemplate("application_submitted", 1, "application", True, True, frozenset({"portal_application_number", "client_status", "portal_url", "event_date"})),
    "application_approval_required": EmailTemplate("application_approval_required", 1, "application", True, True, frozenset({"portal_application_number", "client_status", "portal_url", "event_date"}), frozenset({"company_name"})),
    "application_approved": EmailTemplate("application_approved", 1, "application", False, True, frozenset({"portal_application_number", "client_status", "portal_url", "event_date"})),
    "application_returned": EmailTemplate("application_returned", 1, "application", False, True, frozenset({"portal_application_number", "client_status", "portal_url", "event_date"})),
    "application_document_required": EmailTemplate("application_document_required", 1, "document", True, True, frozenset({"portal_application_number", "client_status", "portal_url", "event_date"})),
    "application_payment_document_required": EmailTemplate("application_payment_document_required", 1, "document", True, True, frozenset({"portal_application_number", "client_status", "portal_url", "event_date"})),
    "partner_client_review_pending": EmailTemplate("partner_client_review_pending", 1, "partner", True, True, frozenset({"client_status", "portal_url", "event_date"})),
    "partner_client_clarification_required": EmailTemplate("partner_client_clarification_required", 1, "partner", True, True, frozenset({"client_status", "portal_url", "event_date"})),
    "partner_client_approved": EmailTemplate("partner_client_approved", 1, "partner", True, True, frozenset({"client_status", "portal_url", "event_date"})),
    "partner_client_rejected": EmailTemplate("partner_client_rejected", 1, "partner", True, True, frozenset({"client_status", "portal_url", "event_date"})),
    "partner_application_received": EmailTemplate("partner_application_received", 1, "partner", True, True, frozenset({"portal_application_number", "client_status", "portal_url", "event_date"})),
    "partner_action_required": EmailTemplate("partner_action_required", 1, "partner", True, True, frozenset({"portal_application_number", "client_status", "portal_url", "event_date"})),
    "bitrix_application_transfer_failed": EmailTemplate("bitrix_application_transfer_failed", 1, "technical", True, True, frozenset({"target_id", "safe_error_code", "correlation_id", "portal_url", "event_date"})),
    "bitrix_document_transfer_failed": EmailTemplate("bitrix_document_transfer_failed", 1, "technical", True, True, frozenset({"target_id", "safe_error_code", "correlation_id", "portal_url", "event_date"})),
}

COPY: dict[str, dict[str, dict[str, str]]] = {
    "ru": {
        "user_invite": {"subject": "Приглашение в IBB Insurance Portal", "preheader": "Для вас создан доступ к порталу.", "title": "Доступ к IBB Insurance Portal", "body": "Для вас создан доступ к IBB Insurance Portal. Используйте одноразовую ссылку для установки пароля.", "button": "Установить пароль", "security": "Если вы не ожидали приглашение, не переходите по ссылке и свяжитесь с поддержкой."},
        "password_reset": {"subject": "Восстановление пароля IBB Insurance Portal", "preheader": "Ссылка для восстановления действует ограниченное время.", "title": "Восстановление пароля", "body": "Мы получили запрос на восстановление пароля. Используйте одноразовую ссылку для установки нового пароля.", "button": "Задать новый пароль", "security": "Если вы не запрашивали восстановление, просто проигнорируйте письмо. Не пересылайте ссылку другим людям."},
        "generic": {"subject": "Событие в IBB Insurance Portal", "preheader": "Обновление по портальному событию.", "title": "Обновление в портале", "body": "В IBB Insurance Portal появилось обновление по событию.", "button": "Открыть портал", "security": "Письмо содержит только минимальные сведения. Документы и персональные данные доступны только в портале."},
        "technical": {"subject": "Техническое событие IBB Portal", "preheader": "Требуется проверка интеграции.", "title": "Требуется проверка интеграции", "body": "Зафиксирована техническая ошибка передачи. Подробности доступны суперадминистратору в портале.", "button": "Открыть портал", "security": "Письмо не содержит payload, секреты, стек ошибок или персональные данные."},
    },
    "ka": {
        "user_invite": {"subject": "მოწვევა IBB Insurance Portal-ში", "preheader": "თქვენთვის შეიქმნა პორტალზე წვდომა.", "title": "IBB Insurance Portal-ზე წვდომა", "body": "თქვენთვის შეიქმნა წვდომა IBB Insurance Portal-ში. პაროლის დასაყენებლად გამოიყენეთ ერთჯერადი ბმული.", "button": "პაროლის დაყენება", "security": "თუ მოწვევას არ ელოდით, ბმულზე ნუ გადახვალთ და დაუკავშირდით მხარდაჭერას."},
        "password_reset": {"subject": "IBB Insurance Portal პაროლის აღდგენა", "preheader": "აღდგენის ბმული მოქმედებს შეზღუდული დროით.", "title": "პაროლის აღდგენა", "body": "მივიღეთ პაროლის აღდგენის მოთხოვნა. ახალი პაროლის დასაყენებლად გამოიყენეთ ერთჯერადი ბმული.", "button": "ახალი პაროლის დაყენება", "security": "თუ აღდგენა არ მოგითხოვიათ, უგულებელყავით წერილი. ბმული სხვებს არ გაუზიაროთ."},
        "generic": {"subject": "IBB Insurance Portal-ის მოვლენა", "preheader": "პორტალში არის განახლება.", "title": "პორტალის განახლება", "body": "IBB Insurance Portal-ში დაფიქსირდა მოვლენის განახლება.", "button": "პორტალის გახსნა", "security": "წერილი შეიცავს მხოლოდ მინიმალურ ინფორმაციას. დოკუმენტები და პერსონალური მონაცემები ხელმისაწვდომია მხოლოდ პორტალში."},
        "technical": {"subject": "IBB Portal ტექნიკური მოვლენა", "preheader": "საჭიროა ინტეგრაციის შემოწმება.", "title": "საჭიროა ინტეგრაციის შემოწმება", "body": "დაფიქსირდა გადაცემის ტექნიკური შეცდომა. დეტალები ხელმისაწვდომია სუპერადმინისტრატორის პორტალში.", "button": "პორტალის გახსნა", "security": "წერილი არ შეიცავს payload-ს, საიდუმლოებს, stack trace-ს ან პერსონალურ მონაცემებს."},
    },
}

SENSITIVE_VARIABLE_KEYS = {"email", "phone", "name", "vin", "plate", "registration_number", "passport", "comment", "payload", "token", "secret", "password", "document", "bitrix_deal_id", "route", "cargo", "premium"}


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}" if domain else "recipient"


def recipient_ref(email: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    digest = hmac.new(resolved.cookie_secret.encode(), email.lower().encode(), hashlib.sha256).hexdigest()[:16]
    return f"email:{digest}:{mask_email(email)}"


def sanitize_variables(template_code: str, variables: dict[str, Any]) -> dict[str, Any]:
    template = EMAIL_TEMPLATES.get(template_code)
    if template is None or not template.active:
        raise EmailDeliveryError("EMAIL_TEMPLATE_NOT_FOUND")
    keys = set(variables)
    if not template.required_variables.issubset(keys):
        raise EmailDeliveryError("EMAIL_TEMPLATE_REQUIRED_VARIABLE_MISSING")
    if keys - template.allowed_variables:
        raise EmailDeliveryError("EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED")
    for key in keys:
        lowered = key.lower()
        if any(part in lowered for part in SENSITIVE_VARIABLE_KEYS) and key not in template.allowed_variables:
            raise EmailDeliveryError("EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED")
    safe = {}
    for key, value in variables.items():
        if value is None or isinstance(value, str | int | float | bool):
            safe[key] = value
        else:
            raise EmailDeliveryError("EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED")
    for url_key in {"action_url", "portal_url"} & set(safe):
        if not isinstance(safe[url_key], str) or not _ALLOWED_URL_RE.match(safe[url_key]):
            raise EmailDeliveryError("EMAIL_TEMPLATE_ABSOLUTE_URL_REQUIRED")
    return safe


def _copy(locale: str, template_code: str, category: str) -> dict[str, str]:
    language = normalize_locale(locale)
    language = language if language in COPY else DEFAULT_LOCALE
    if template_code in COPY[language]:
        return COPY[language][template_code]
    return COPY[language]["technical" if category == "technical" else "generic"]


def render_email(template_code: str, locale: str, variables: dict[str, Any], *, to_email: str, from_email: str) -> EmailMessage:
    template = EMAIL_TEMPLATES[template_code]
    safe_variables = sanitize_variables(template_code, variables)
    copy = _copy(locale, template_code, template.category)
    action_url = str(safe_variables.get("action_url") or safe_variables.get("portal_url") or "")
    escaped_url = escape(action_url, quote=True)
    details = []
    for key in ("portal_application_number", "client_status", "target_id", "safe_error_code", "correlation_id", "event_date", "expires_at", "support_contact"):
        if safe_variables.get(key):
            details.append(f"<li><strong>{escape(key)}:</strong> {escape(str(safe_variables[key]))}</li>")
    details_html = f"<ul>{''.join(details)}</ul>" if details else ""
    body = f"""
                <p style="margin:0 0 18px;font-size:16px;line-height:1.6;color:#1f3f70;">{escape(copy['body'])}</p>
                {details_html}
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 28px;"><tr><td style="border-radius:8px;background:#0057a8;"><a href="{escaped_url}" style="display:inline-block;padding:14px 28px;font-size:15px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">{escape(copy['button'])}</a></td></tr></table>
                <p style="margin:0 0 8px;font-size:13px;line-height:1.6;color:#526987;">{escape(copy['preheader'])}</p>
                <p style="margin:0 0 26px;font-size:13px;line-height:1.6;word-break:break-all;color:#0057a8;">{escaped_url}</p>
"""
    message = EmailMessage()
    message["Subject"] = copy["subject"]
    message["From"] = from_email
    message["To"] = to_email
    text_lines = ["IBB Insurance Portal", "", copy["body"], ""]
    text_lines.extend(f"{key}: {safe_variables[key]}" for key in sorted(safe_variables) if key not in {"action_url", "portal_url"})
    text_lines.extend(["", action_url, "", copy["security"]])
    message.set_content("\n".join(text_lines))
    message.add_alternative(html_shell(language=normalize_locale(locale), logo_src="", title=copy["title"], body=body, security=copy["security"]), subtype="html")
    return message


def enqueue_email(session: Session, *, template_code: str, locale: str, to_email: str, recipient_user_id: int | None, event_type: str, target_type: str | None, target_id: str | None, variables: dict[str, Any], idempotency_key: str, correlation_id: str | None = None, max_attempts: int = 3, request=None, actor_user_id: int | None = None) -> int:
    template = EMAIL_TEMPLATES.get(template_code)
    if template is None:
        raise EmailDeliveryError("EMAIL_TEMPLATE_NOT_FOUND")
    safe_variables = sanitize_variables(template_code, variables)
    values = dict(template_code=template_code, template_version=template.version, locale=normalize_locale(locale), recipient_user_id=recipient_user_id, recipient_ref=recipient_ref(to_email), event_type=event_type, target_type=target_type, target_id=target_id, template_variables=safe_variables, idempotency_key=idempotency_key, correlation_id=correlation_id, max_attempts=max_attempts)
    try:
        result = session.execute(insert(email_messages).values(**values))
        email_id = int(result.inserted_primary_key[0])
    except IntegrityError:
        session.rollback()
        row = session.execute(select(email_messages.c.id).where(email_messages.c.idempotency_key == idempotency_key)).mappings().one()
        email_id = int(row.id)
    audit_event(session, action="email_queued", object_type="email_message", request=request, actor_user_id=actor_user_id, target_user_id=recipient_user_id, object_id=str(email_id), metadata={"template_code": template_code, "event_type": event_type, "target_type": target_type, "target_id": target_id, "correlation_id": correlation_id})
    return email_id


def _recipient_email(session: Session, row) -> str | None:
    if row.recipient_user_id:
        user = session.execute(select(portal_users.c.email).where(portal_users.c.id == row.recipient_user_id)).mappings().one_or_none()
        if user:
            return user.email
    return None


def _token_is_expired(session: Session, row) -> bool:
    if row.template_code not in TOKEN_TEMPLATE_CODES or not row.recipient_user_id:
        return False
    token_type = "first_login" if row.template_code == "user_invite" else "password_reset"
    token = session.execute(select(auth_tokens).where(auth_tokens.c.user_id == row.recipient_user_id, auth_tokens.c.token_type == token_type).order_by(auth_tokens.c.created_at.desc())).mappings().first()
    return bool(token and (token.used_at is not None or ensure_aware_utc(token.expires_at) <= now_utc()))


def process_email_queue(session: Session, *, limit: int = 20, settings: Settings | None = None) -> int:
    resolved = settings or get_settings()
    due = session.execute(select(email_messages).where(email_messages.c.status.in_(["pending", "retry_scheduled"]), email_messages.c.scheduled_at <= now_utc()).order_by(email_messages.c.scheduled_at.asc()).limit(limit)).mappings().all()
    processed = 0
    for row in due:
        locked = session.execute(update(email_messages).where(email_messages.c.id == row.id, email_messages.c.status == row.status).values(status="processing", last_attempt_at=now_utc(), attempt_count=row.attempt_count + 1).returning(email_messages.c.id)).first()
        if not locked:
            continue
        session.commit()
        try:
            if _token_is_expired(session, row):
                raise EmailDeliveryError("EMAIL_TOKEN_EXPIRED")
            to_email = _recipient_email(session, row)
            if not to_email:
                raise EmailDeliveryError("EMAIL_RECIPIENT_NOT_FOUND")
            if not resolved.email_enabled:
                raise EmailDeliveryError("EMAIL_NOT_CONFIGURED")
            message = render_email(row.template_code, row.locale, row.template_variables or {}, to_email=to_email, from_email=resolved.resolved_smtp_from_email or "")
            send_message(message, resolved)
            session.execute(update(email_messages).where(email_messages.c.id == row.id).values(status="sent", sent_at=now_utc(), safe_error_code=None))
            audit_event(session, action="email_sent", object_type="email_message", request=None, target_user_id=row.recipient_user_id, object_id=str(row.id), metadata={"template_code": row.template_code, "event_type": row.event_type, "attempt_number": row.attempt_count + 1, "correlation_id": row.correlation_id})
        except EmailDeliveryError as exc:
            code = str(exc) or "EMAIL_DELIVERY_FAILED"
            attempt = row.attempt_count + 1
            retryable = code in RETRYABLE_ERROR_CODES and attempt < row.max_attempts
            if retryable:
                delay = timedelta(minutes=2 * attempt)
                session.execute(update(email_messages).where(email_messages.c.id == row.id).values(status="retry_scheduled", safe_error_code=code, next_retry_at=now_utc() + delay, scheduled_at=now_utc() + delay))
                action = "email_retry_scheduled"
            else:
                session.execute(update(email_messages).where(email_messages.c.id == row.id).values(status="failed", safe_error_code=code, failed_at=now_utc()))
                action = "email_failed"
                if row.template_code.startswith("bitrix_"):
                    session.execute(insert(integration_errors).values(object_type="bitrix", object_id=row.target_id, operation="sync", status="failed", error_code=code, safe_message="Email delivery failure", retry_count=attempt, last_attempt_at=now_utc()))
            audit_event(session, action=action, object_type="email_message", request=None, target_user_id=row.recipient_user_id, object_id=str(row.id), metadata={"template_code": row.template_code, "event_type": row.event_type, "safe_error_code": code, "attempt_number": attempt, "correlation_id": row.correlation_id})
        session.commit()
        processed += 1
    return processed


def manual_retry_email(session: Session, *, email_id: int, actor_user_id: int, request=None) -> None:
    row = session.execute(select(email_messages).where(email_messages.c.id == email_id)).mappings().one_or_none()
    if row is None:
        raise EmailDeliveryError("EMAIL_MESSAGE_NOT_FOUND")
    if row.status == "sent":
        raise EmailDeliveryError("EMAIL_ALREADY_SENT")
    if row.status != "failed":
        raise EmailDeliveryError("EMAIL_RETRY_NOT_ALLOWED")
    if _token_is_expired(session, row):
        raise EmailDeliveryError("EMAIL_TOKEN_EXPIRED")
    session.execute(update(email_messages).where(email_messages.c.id == email_id, email_messages.c.status == "failed").values(status="pending", scheduled_at=now_utc(), next_retry_at=None, safe_error_code=None))
    audit_event(session, action="email_manual_retry", object_type="email_message", request=request, actor_user_id=actor_user_id, target_user_id=row.recipient_user_id, object_id=str(email_id), metadata={"template_code": row.template_code, "event_type": row.event_type, "correlation_id": row.correlation_id})
