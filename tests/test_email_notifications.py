from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.orm import Session

from app.auth import hash_password, now_utc
from app.email import EmailDeliveryError
from app.email_notifications import enqueue_email, process_email_queue, render_email, sanitize_variables
from app.models import auth_tokens, email_messages, portal_users


def create_user(database_url: str, *, email: str = "client@example.com", status: str = "active") -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user_id = session.execute(
                insert(portal_users)
                .values(
                    email=email,
                    password_hash=hash_password("StrongPass123!"),
                    status=status,
                    user_type="client",
                    role_code="client_executor",
                    language="ru",
                )
                .returning(portal_users.c.id)
            ).scalar_one()
            session.commit()
            return user_id
    finally:
        engine.dispose()


def test_templates_allowlist_and_render_ru_ka(migrated_database: str) -> None:
    variables = {
        "action_url": "http://localhost:3000/reset-password?token=secret",
        "expires_at": "2026-10-30T10:00:00+00:00",
        "support_contact": "support@ibb.expert",
    }
    assert sanitize_variables("password_reset", variables) == variables
    with pytest.raises(EmailDeliveryError, match="EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED"):
        sanitize_variables("password_reset", variables | {"vin": "ABC"})
    ru = render_email(
        "password_reset", "ru", variables, to_email="client@example.com", from_email="noreply@example.test"
    )
    ka = render_email(
        "password_reset", "ka", variables, to_email="client@example.com", from_email="noreply@example.test"
    )
    assert "Восстановление" in ru["Subject"]
    assert "აღდგენა" in ka["Subject"]
    assert "ABC" not in ru.as_string()


def test_enqueue_stores_masked_recipient_and_worker_sends(monkeypatch, migrated_database: str) -> None:
    user_id = create_user(migrated_database)
    sent = []

    def fake_send_message(message, settings):
        sent.append(message)

    monkeypatch.setattr("app.email_notifications.send_message", fake_send_message)
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            email_id = enqueue_email(
                session,
                template_code="application_submitted",
                locale="ru",
                to_email="client@example.com",
                recipient_user_id=user_id,
                event_type="application_submitted",
                target_type="application",
                target_id="42",
                variables={
                    "portal_application_number": "APP-42",
                    "client_status": "received",
                    "portal_url": "http://localhost:3000/applications/42",
                    "event_date": "2026-10-30",
                },
                idempotency_key="application_submitted:client:42:1",
            )
            session.commit()
            row = session.execute(select(email_messages).where(email_messages.c.id == email_id)).mappings().one()
            assert "client@example.com" not in row.recipient_ref
            assert row.status == "pending"
            assert process_email_queue(session) == 1
            sent_row = session.execute(select(email_messages).where(email_messages.c.id == email_id)).mappings().one()
            assert sent_row.status == "sent"
    finally:
        engine.dispose()
    assert len(sent) == 1


def test_worker_retries_temporary_error_and_blocks_expired_token(monkeypatch, migrated_database: str) -> None:
    user_id = create_user(migrated_database, status="pending")

    def fail_send_message(_message, _settings):
        raise EmailDeliveryError("EMAIL_DELIVERY_FAILED")

    monkeypatch.setattr("app.email_notifications.send_message", fail_send_message)
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(
                insert(auth_tokens).values(
                    user_id=user_id,
                    token_hash="hash",
                    token_type="first_login",
                    expires_at=now_utc() + timedelta(hours=1),
                )
            )
            email_id = enqueue_email(
                session,
                template_code="user_invite",
                locale="ru",
                to_email="client@example.com",
                recipient_user_id=user_id,
                event_type="user_invite",
                target_type="portal_user",
                target_id=str(user_id),
                variables={
                    "action_url": "http://localhost:3000/first-login?token=secret",
                    "expires_at": "2026-10-30T10:00:00+00:00",
                    "support_contact": "support@ibb.expert",
                },
                idempotency_key="invite:user:1",
                max_attempts=2,
            )
            session.commit()
            assert process_email_queue(session) == 1
            row = session.execute(select(email_messages).where(email_messages.c.id == email_id)).mappings().one()
            assert row.status == "retry_scheduled"
            session.execute(
                update(email_messages)
                .where(email_messages.c.id == email_id)
                .values(status="pending", scheduled_at=now_utc())
            )
            session.execute(
                update(auth_tokens)
                .where(auth_tokens.c.user_id == user_id)
                .values(expires_at=now_utc() - timedelta(minutes=1))
            )
            session.commit()
            assert process_email_queue(session) == 1
            row = session.execute(select(email_messages).where(email_messages.c.id == email_id)).mappings().one()
            assert row.status == "failed"
            assert row.safe_error_code == "EMAIL_TOKEN_EXPIRED"
    finally:
        engine.dispose()
