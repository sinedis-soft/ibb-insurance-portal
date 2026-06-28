from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import hash_invite_token
from app.bitrix import contact_language_from_contact
from app.models import audit_logs, invite_tokens, portal_users


def create_client(
    monkeypatch,
    migrated_database: str,
    contact_payload: dict | None = None,
    email_calls: list | None = None,
):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app
    from app.routers import bitrix_webhooks

    async def fake_get_contact(contact_id, _settings=None):
        assert contact_id == 777
        return contact_payload or {
            "ID": "777",
            "UF_CRM_1753957395750": "3941",
            "EMAIL": [
                {"ID": "10", "VALUE": "old@example.com", "TYPE_ID": "EMAIL"},
                {"ID": "15", "VALUE": "latest@example.com", "TYPE_ID": "EMAIL"},
            ],
        }

    def fake_send_invite_email(**kwargs):
        if email_calls is not None:
            email_calls.append(kwargs)

    monkeypatch.setattr(bitrix_webhooks, "get_contact", fake_get_contact)
    monkeypatch.setattr(bitrix_webhooks, "send_invite_email", fake_send_invite_email)
    get_settings.cache_clear()
    return TestClient(create_app())


def test_create_client_user_from_bitrix_contact(monkeypatch, migrated_database: str) -> None:
    email_calls: list[dict] = []
    client = create_client(monkeypatch, migrated_database, email_calls=email_calls)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/create-user"
        "?account_type=client&role=client_executor&bitrix_contact_id=777"
    )

    assert response.status_code == 200
    assert response.json() == {"status": "created", "user_id": "usr_1"}
    assert len(email_calls) == 1
    assert email_calls[0]["to_email"] == "latest@example.com"
    assert email_calls[0]["invite_link"].startswith("http://localhost:3000/invite?token=")
    assert email_calls[0]["temporary_password"]
    assert email_calls[0]["language"] == "ka"

    from sqlalchemy import create_engine

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            user = session.execute(select(portal_users)).mappings().one()
            assert user.email == "latest@example.com"
            assert user.user_type == "client"
            assert user.role_code == "client_executor"
            assert user.language == "ka"
            assert user.bitrix_contact_id == 777
            assert email_calls[0]["temporary_password"] not in user.password_hash

            invite = session.execute(select(invite_tokens)).mappings().one()
            invite_token = email_calls[0]["invite_link"].split("token=", 1)[1]
            assert invite.token_hash == hash_invite_token(invite_token)
            assert invite.token_hash != invite_token

            audit = session.execute(select(audit_logs)).mappings().one()
            assert audit.action == "user_created_from_bitrix_contact"
            assert audit.metadata_json["language"] == "ka"
            assert "latest@example.com" not in str(audit.metadata_json)
            assert email_calls[0]["temporary_password"] not in str(audit.metadata_json)
            assert invite_token not in str(audit.metadata_json)
    finally:
        engine.dispose()


def test_create_partner_user_requires_no_role(monkeypatch, migrated_database: str) -> None:
    email_calls: list[dict] = []
    client = create_client(monkeypatch, migrated_database, email_calls=email_calls)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/create-user?account_type=partner&bitrix_contact_id=777"
    )

    assert response.status_code == 200
    from sqlalchemy import create_engine

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            user = session.execute(select(portal_users)).mappings().one()
            assert user.user_type == "partner"
            assert user.role_code is None
    finally:
        engine.dispose()


def test_partner_role_is_rejected(monkeypatch, migrated_database: str) -> None:
    client = create_client(monkeypatch, migrated_database)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/create-user"
        "?account_type=partner&role=client_executor&bitrix_contact_id=777"
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "PARTNER_ROLE_FORBIDDEN"


def test_invalid_secret_does_not_call_bitrix(monkeypatch, migrated_database: str) -> None:
    called = False
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app
    from app.routers import bitrix_webhooks

    async def fake_get_contact(_contact_id, _settings=None):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(bitrix_webhooks, "get_contact", fake_get_contact)
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.post(
        "/bitrix/outbound/wrong_secret/1/create-user?account_type=client&role=client_executor&bitrix_contact_id=777"
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "WEBHOOK_FORBIDDEN"
    assert called is False


def test_duplicate_contact_does_not_create_second_user(monkeypatch, migrated_database: str) -> None:
    email_calls: list[dict] = []
    client = create_client(monkeypatch, migrated_database, email_calls=email_calls)
    url = (
        "/bitrix/outbound/test_outbound_secret/1/create-user"
        "?account_type=client&role=client_executor&bitrix_contact_id=777"
    )

    first = client.post(url)
    second = client.post(url)

    assert first.json()["status"] == "created"
    assert second.json()["status"] == "reinvited"
    assert len(email_calls) == 2
    assert email_calls[0]["temporary_password"] != email_calls[1]["temporary_password"]
    assert email_calls[0]["invite_link"] != email_calls[1]["invite_link"]

    from sqlalchemy import create_engine, func

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            assert session.execute(select(func.count()).select_from(portal_users)).scalar_one() == 1
            invites = session.execute(select(invite_tokens).order_by(invite_tokens.c.id)).mappings().all()
            assert len(invites) == 2
            assert invites[0].used_at is not None
            assert invites[1].used_at is None
            audit_actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert audit_actions == [
                "user_created_from_bitrix_contact",
                "bitrix_user_reinvited_before_first_login",
            ]
    finally:
        engine.dispose()


def test_duplicate_contact_after_login_does_not_reinvite(monkeypatch, migrated_database: str) -> None:
    email_calls: list[dict] = []
    client = create_client(monkeypatch, migrated_database, email_calls=email_calls)
    url = (
        "/bitrix/outbound/test_outbound_secret/1/create-user"
        "?account_type=client&role=client_executor&bitrix_contact_id=777"
    )

    first = client.post(url)

    assert first.json()["status"] == "created"

    from sqlalchemy import create_engine

    from app.auth import now_utc

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(update(portal_users).values(last_login_at=now_utc()))
            session.commit()
    finally:
        engine.dispose()

    second = client.post(url)

    assert second.json()["status"] == "exists"
    assert len(email_calls) == 1


def test_contact_language_defaults_to_russian_for_empty_or_unknown_value() -> None:
    assert contact_language_from_contact({}) == "ru"
    assert contact_language_from_contact({"UF_CRM_1753957395750": ""}) == "ru"
    assert contact_language_from_contact({"UF_CRM_1753957395750": "999999"}) == "ru"


def test_contact_language_maps_bitrix_enum_id_to_portal_language() -> None:
    assert contact_language_from_contact({"UF_CRM_1753957395750": "3937"}) == "ru"
    assert contact_language_from_contact({"UF_CRM_1753957395750": 3953}) == "en"
    assert contact_language_from_contact({"UF_CRM_1753957395750": {"ID": "4775"}}) == "he"
    assert contact_language_from_contact({"UF_CRM_1753957395750": ["4761"]}) == "ar"
