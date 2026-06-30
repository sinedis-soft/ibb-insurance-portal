from __future__ import annotations

from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.orm import Session

from app.auth import hash_invite_token, hash_password
from app.bitrix import contact_language_from_contact
from app.models import (
    audit_logs,
    invite_tokens,
    partner_client_links,
    partner_client_requests,
    portal_users,
    user_company_roles,
)


def create_client(
    monkeypatch,
    migrated_database: str,
    contact_payload: dict | None = None,
    company_bindings: list[dict] | None = None,
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
            "NAME": "Ana",
            "LAST_NAME": "Customer",
            "COMPANY_ID": "123",
            "UF_CRM_1753957395750": "3941",
            "EMAIL": [
                {"ID": "10", "VALUE": "old@example.com", "TYPE_ID": "EMAIL"},
                {"ID": "15", "VALUE": "latest@example.com", "TYPE_ID": "EMAIL"},
            ],
        }

    def fake_send_invite_email(**kwargs):
        if email_calls is not None:
            email_calls.append(kwargs)

    async def fake_get_company(company_id, _settings=None):
        return {
            "ID": str(company_id),
            "TITLE": f"Company {company_id}",
            "ADDRESS_COUNTRY_CODE": "PL",
            "DATE_MODIFY": "2026-06-29T10:00:00+03:00",
        }

    async def fake_get_contact_company_bindings(contact_id, _settings=None):
        assert contact_id == 777
        return company_bindings if company_bindings is not None else [{"COMPANY_ID": "123", "IS_PRIMARY": "Y"}]

    monkeypatch.setattr(bitrix_webhooks, "get_contact", fake_get_contact)
    monkeypatch.setattr(bitrix_webhooks, "get_company", fake_get_company)
    monkeypatch.setattr(bitrix_webhooks, "get_contact_company_bindings", fake_get_contact_company_bindings)
    monkeypatch.setattr(bitrix_webhooks, "send_invite_email", fake_send_invite_email)
    get_settings.cache_clear()
    return TestClient(create_app())


def create_portal_user(
    database_url: str,
    *,
    email: str,
    user_type: str = "partner",
    role_code: str | None = "partner",
) -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user_id = session.execute(
                insert(portal_users)
                .values(
                    email=email,
                    password_hash=hash_password("StrongPass123!"),
                    status="active",
                    user_type=user_type,
                    role_code=role_code,
                    language="ru",
                )
                .returning(portal_users.c.id)
            ).scalar_one()
            session.commit()
            return user_id
    finally:
        engine.dispose()


def create_partner_client_check(database_url: str, *, partner_user_id: int, company_id: int = 9001) -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            request_id = session.execute(
                insert(partner_client_requests)
                .values(
                    partner_user_id=partner_user_id,
                    created_by_user_id=partner_user_id,
                    company_name="Oceanic Shipping",
                    country="PL",
                    contact_name="Client Contact",
                    contact_email="client@example.invalid",
                    status="pending",
                    bitrix_check_entity_type="company",
                    bitrix_check_entity_id=company_id,
                    bitrix_check_status="pending",
                    bitrix_sync_status="synced",
                )
                .returning(partner_client_requests.c.id)
            ).scalar_one()
            session.commit()
            return request_id
    finally:
        engine.dispose()


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
            assert user.display_name_cache == "Ana Customer"
            assert email_calls[0]["temporary_password"] not in user.password_hash

            company_role = session.execute(select(user_company_roles)).mappings().one()
            assert company_role.user_id == user.id
            assert company_role.bitrix_company_id == 123
            assert company_role.role_code == "client_executor"
            assert company_role.access_status == "active"
            assert company_role.bitrix_link_status == "confirmed"
            assert company_role.company_title_cache == "Company 123"

            invite = session.execute(select(invite_tokens)).mappings().one()
            invite_token = email_calls[0]["invite_link"].split("token=", 1)[1]
            assert invite.token_hash == hash_invite_token(invite_token)
            assert invite.token_hash != invite_token

            audits = session.execute(select(audit_logs).order_by(audit_logs.c.id)).mappings().all()
            assert [audit.action for audit in audits] == [
                "company_role_created_from_bitrix_contact",
                "user_created_from_bitrix_contact",
            ]
            assert audits[-1].metadata_json["language"] == "ka"
            assert "latest@example.com" not in str([audit.metadata_json for audit in audits])
            assert email_calls[0]["temporary_password"] not in str([audit.metadata_json for audit in audits])
            assert invite_token not in str([audit.metadata_json for audit in audits])
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


def test_system_bitrix_company_is_ignored(monkeypatch, migrated_database: str) -> None:
    email_calls: list[dict] = []
    client = create_client(
        monkeypatch,
        migrated_database,
        contact_payload={
            "ID": "777",
            "NAME": "System",
            "LAST_NAME": "Contact",
            "COMPANY_ID": "123",
            "UF_CRM_1753957395750": "3937",
            "EMAIL": [{"ID": "15", "VALUE": "system-contact@example.com", "TYPE_ID": "EMAIL"}],
        },
        company_bindings=[{"COMPANY_ID": "1817", "IS_PRIMARY": "Y"}],
        email_calls=email_calls,
    )

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/create-user"
        "?account_type=client&role=client_executor&bitrix_contact_id=777"
    )

    assert response.status_code == 200

    from sqlalchemy import create_engine, func

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            assert session.execute(select(func.count()).select_from(user_company_roles)).scalar_one() == 0
    finally:
        engine.dispose()


def test_multi_company_contact_creates_all_non_system_company_roles(monkeypatch, migrated_database: str) -> None:
    email_calls: list[dict] = []
    client = create_client(
        monkeypatch,
        migrated_database,
        company_bindings=[
            {"COMPANY_ID": "1817", "IS_PRIMARY": "N"},
            {"COMPANY_ID": "123", "IS_PRIMARY": "Y"},
            {"COMPANY_ID": "456", "IS_PRIMARY": "N"},
            {"COMPANY_ID": "123", "IS_PRIMARY": "N"},
        ],
        email_calls=email_calls,
    )

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/create-user"
        "?account_type=client&role=client_executor&bitrix_contact_id=777"
    )

    assert response.status_code == 200

    from sqlalchemy import create_engine

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            company_roles = session.execute(
                select(user_company_roles).order_by(user_company_roles.c.bitrix_company_id)
            ).mappings().all()
            assert [role.bitrix_company_id for role in company_roles] == [123, 456]
            assert {role.company_title_cache for role in company_roles} == {"Company 123", "Company 456"}
            audits = session.execute(
                select(audit_logs.c.action, audit_logs.c.metadata_json).order_by(audit_logs.c.id)
            ).mappings().all()
            role_audits = [
                audit.metadata_json["bitrix_company_id"]
                for audit in audits
                if audit.action == "company_role_created_from_bitrix_contact"
            ]
            assert role_audits == [123, 456]
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


def test_partner_client_check_status_webhook_confirms_company_and_creates_link(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_portal_user(migrated_database, email="partner@example.com")
    request_id = create_partner_client_check(migrated_database, partner_user_id=partner_id, company_id=9001)
    client = create_client(monkeypatch, migrated_database)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/partner-client-check-status"
        "?bitrix_company_id=9001&status_id=6483"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "updated",
        "client_request_id": f"pcr_{request_id}",
        "portal_status": "confirmed",
    }

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(partner_client_requests)).mappings().one()
            assert row.status == "confirmed"
            assert row.bitrix_check_status == "confirmed"
            assert row.bitrix_sync_status == "synced"
            assert row.confirmed_bitrix_company_id == 9001
            assert row.confirmed_company_id == 9001

            link = session.execute(select(partner_client_links)).mappings().one()
            assert link.partner_user_id == partner_id
            assert link.bitrix_company_id == 9001
            assert link.status == "active"
            assert link.access_status == "active"

            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert actions == [
                "partner_client_check_status_updated",
                "partner_client_check_confirmed",
            ]
    finally:
        engine.dispose()


def test_partner_client_check_status_webhook_is_idempotent_for_confirmed(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_portal_user(migrated_database, email="partner@example.com")
    create_partner_client_check(migrated_database, partner_user_id=partner_id, company_id=9001)
    client = create_client(monkeypatch, migrated_database)
    url = (
        "/bitrix/outbound/test_outbound_secret/1/partner-client-check-status"
        "?bitrix_company_id=9001&status_id=6483"
    )

    first = client.post(url)
    second = client.post(url)

    assert first.status_code == 200
    assert second.status_code == 200

    from sqlalchemy import func

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            assert session.execute(select(func.count()).select_from(partner_client_links)).scalar_one() == 1
            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert actions.count("partner_client_check_confirmed") == 1
            assert "partner_client_check_webhook_repeated" in actions
    finally:
        engine.dispose()


def test_partner_client_check_status_webhook_links_duplicate_to_existing_company(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_portal_user(migrated_database, email="partner@example.com")
    request_id = create_partner_client_check(migrated_database, partner_user_id=partner_id, company_id=9001)
    client = create_client(monkeypatch, migrated_database)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/partner-client-check-status"
        "?bitrix_company_id=9001&status=linked_to_existing&linked_bitrix_company_id=8123"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "updated",
        "client_request_id": f"pcr_{request_id}",
        "portal_status": "linked_to_existing",
    }

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(partner_client_requests)).mappings().one()
            assert row.status == "confirmed"
            assert row.bitrix_check_status == "confirmed"
            assert row.decision_status == "linked_to_existing"
            assert row.linked_to_existing is True
            assert row.original_bitrix_company_id == 9001
            assert row.linked_bitrix_company_id == 8123
            assert row.confirmed_bitrix_company_id == 8123

            link = session.execute(select(partner_client_links)).mappings().one()
            assert link.partner_user_id == partner_id
            assert link.bitrix_company_id == 8123
            assert link.status == "active"
            assert session.execute(
                select(partner_client_links).where(partner_client_links.c.bitrix_company_id == 9001)
            ).all() == []

            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert actions == [
                "partner_client_check_status_updated",
                "partner_client_check_linked_to_existing",
            ]
    finally:
        engine.dispose()


def test_partner_client_check_status_webhook_requires_linked_company_for_linked_status(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_portal_user(migrated_database, email="partner@example.com")
    create_partner_client_check(migrated_database, partner_user_id=partner_id, company_id=9001)
    client = create_client(monkeypatch, migrated_database)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/partner-client-check-status"
        "?bitrix_company_id=9001&status=linked_to_existing"
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "LINKED_BITRIX_COMPANY_REQUIRED"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(partner_client_requests)).mappings().one()
            assert row.status == "pending"
            assert session.execute(select(partner_client_links)).mappings().all() == []
    finally:
        engine.dispose()


def test_partner_client_check_status_webhook_accepts_russian_status_value(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_portal_user(migrated_database, email="partner@example.com")
    create_partner_client_check(migrated_database, partner_user_id=partner_id, company_id=9001)
    client = create_client(monkeypatch, migrated_database)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/partner-client-check-status"
        "?bitrix_company_id=9001&status=%D0%A2%D1%80%D0%B5%D0%B1%D1%83%D0%B5%D1%82%D1%81%D1%8F%20%D1%83%D1%82%D0%BE%D1%87%D0%BD%D0%B5%D0%BD%D0%B8%D0%B5"
    )

    assert response.status_code == 200
    assert response.json()["portal_status"] == "clarification_required"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(partner_client_requests)).mappings().one()
            assert row.status == "clarification_required"
            assert row.bitrix_check_status == "clarification_required"
            assert session.execute(select(partner_client_links)).mappings().all() == []
            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert actions == [
                "partner_client_check_status_updated",
                "partner_client_check_clarification_required",
            ]
    finally:
        engine.dispose()


def test_partner_client_check_status_webhook_rejects_company(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_portal_user(migrated_database, email="partner@example.com")
    create_partner_client_check(migrated_database, partner_user_id=partner_id, company_id=9001)
    client = create_client(monkeypatch, migrated_database)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/partner-client-check-status"
        "?bitrix_company_id=9001&status_id=6487"
    )

    assert response.status_code == 200
    assert response.json()["portal_status"] == "rejected"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(partner_client_requests)).mappings().one()
            assert row.status == "rejected"
            assert row.bitrix_check_status == "rejected"
            assert row.confirmed_bitrix_company_id is None
            assert session.execute(select(partner_client_links)).mappings().all() == []
            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert actions == [
                "partner_client_check_status_updated",
                "partner_client_check_rejected",
            ]
    finally:
        engine.dispose()


def test_partner_client_check_status_webhook_unknown_status_does_not_confirm_company(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_portal_user(migrated_database, email="partner@example.com")
    create_partner_client_check(migrated_database, partner_user_id=partner_id, company_id=9001)
    client = create_client(monkeypatch, migrated_database)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/partner-client-check-status"
        "?bitrix_company_id=9001&status_id=999999"
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "PARTNER_CLIENT_STATUS_INVALID"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(partner_client_requests)).mappings().one()
            assert row.status == "pending"
            assert row.bitrix_check_status == "pending"
            assert row.confirmed_bitrix_company_id is None
            assert session.execute(select(partner_client_links)).mappings().all() == []
    finally:
        engine.dispose()


def test_partner_client_check_status_webhook_returns_404_for_unknown_company(
    monkeypatch,
    migrated_database: str,
) -> None:
    client = create_client(monkeypatch, migrated_database)

    response = client.post(
        "/bitrix/outbound/test_outbound_secret/1/partner-client-check-status"
        "?bitrix_company_id=9999&status_id=6483"
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "PARTNER_CLIENT_REQUEST_NOT_FOUND"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert actions == ["partner_client_check_sync_failed"]
    finally:
        engine.dispose()


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
                "company_role_created_from_bitrix_contact",
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
