from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.bitrix import BitrixError
from app.models import audit_logs, partner_client_links, portal_users, user_company_roles


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, _ttl: int) -> None:
        self.values.setdefault(key, 0)

    async def get(self, key: str) -> str | None:
        value = self.values.get(key)
        return str(value) if value is not None else None

    async def aclose(self) -> None:
        return None


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def create_client(monkeypatch, migrated_database: str) -> TestClient:
    from app.config import get_settings
    from app.main import create_app

    async def redis_factory() -> FakeRedis:
        return FakeRedis()

    import app.auth as auth_module

    monkeypatch.setattr(auth_module, "get_redis_client", redis_factory)
    get_settings.cache_clear()
    return TestClient(create_app())


def create_user(
    database_url: str,
    *,
    email: str,
    password: str = "StrongPass123!",
    status: str = "active",
    role_code: str | None = "client_executor",
    user_type: str = "client",
) -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user_id = session.execute(
                insert(portal_users)
                .values(
                    email=email,
                    password_hash=hash_password(password),
                    status=status,
                    user_type=user_type,
                    role_code=role_code,
                    language="ru",
                    bitrix_contact_id=12345,
                )
                .returning(portal_users.c.id)
            ).scalar_one()
            session.commit()
            return user_id
    finally:
        engine.dispose()


def login(client: TestClient, email: str, password: str = "StrongPass123!") -> None:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def test_superadmin_assigns_lists_and_user_sees_only_active_company(monkeypatch, migrated_database: str) -> None:
    admin_id = create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com")

    import app.routers.company_access as access_router

    async def fake_get_company(company_id: int, _settings):
        assert company_id == 123
        return {
            "TITLE": "Acme Hidden From Logs",
            "ADDRESS_COUNTRY_CODE": "GE",
            "DATE_MODIFY": "2026-06-28T10:00:00+03:00",
        }

    monkeypatch.setattr(access_router, "get_company", fake_get_company)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    assign = client.post(
        f"/admin/users/usr_{client_id}/company-roles",
        json={"bitrix_company_id": "123", "role_code": "client_admin"},
    )
    listing = client.get(f"/admin/users/usr_{client_id}/company-roles")

    assert assign.status_code == 201
    assert assign.json()["company_role"]["access_status"] == "active"
    assert assign.json()["company_role"]["bitrix_link_status"] == "confirmed"
    assert listing.status_code == 200
    assert listing.json()["company_roles"][0]["role_code"] == "client_admin"

    client.post("/auth/logout")
    login(client, "client@example.com")
    mine = client.get("/me/companies")

    assert mine.status_code == 200
    assert mine.json()["items"] == [assign.json()["company_role"]]

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(user_company_roles)).mappings().one()
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert row.created_by_user_id == admin_id
            assert row.confirmed_by_user_id == admin_id
            assert "company_role_assigned" in actions
    finally:
        engine.dispose()


def test_non_superadmin_cannot_assign_or_revoke(monkeypatch, migrated_database: str) -> None:
    client_id = create_user(migrated_database, email="client@example.com")
    create_user(migrated_database, email="target@example.com")
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    assign = client.post(
        f"/admin/users/usr_{client_id}/company-roles",
        json={"bitrix_company_id": "123", "role_code": "client_admin"},
    )
    revoke = client.post("/admin/company-roles/1/revoke")

    assert assign.status_code == 403
    assert assign.json()["error_code"] == "SUPERADMIN_REQUIRED"
    assert revoke.status_code == 403


def test_revoked_company_role_is_not_returned_and_audit_is_written(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com")

    import app.routers.company_access as access_router

    async def fake_get_company(_company_id: int, _settings):
        return {"TITLE": "Company", "ADDRESS_COUNTRY_CODE": "PL"}

    monkeypatch.setattr(access_router, "get_company", fake_get_company)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")
    assigned = client.post(
        f"/admin/users/{client_id}/company-roles",
        json={"bitrix_company_id": 456, "role_code": "client_executor"},
    )
    role_id = int(assigned.json()["company_role"]["id"].removeprefix("ucr_"))

    revoked = client.post(f"/admin/company-roles/{role_id}/revoke")

    assert revoked.status_code == 200
    client.post("/auth/logout")
    login(client, "client@example.com")
    assert client.get("/me/companies").json() == {"items": []}

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            status_value = session.execute(select(user_company_roles.c.access_status)).scalar_one()
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert status_value == "revoked"
            assert "company_role_revoked" in actions
    finally:
        engine.dispose()


def test_pending_duplicate_invalid_role_and_partner_assignment_are_rejected(
    monkeypatch,
    migrated_database: str,
) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com")
    partner_id = create_user(migrated_database, email="partner@example.com", role_code=None, user_type="partner")

    import app.routers.company_access as access_router

    async def unavailable_company(_company_id: int, _settings):
        raise BitrixError("BITRIX_TRANSPORT_ERROR")

    monkeypatch.setattr(access_router, "get_company", unavailable_company)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    pending = client.post(
        f"/admin/users/usr_{client_id}/company-roles",
        json={"bitrix_company_id": "789", "role_code": "client_viewer"},
    )
    duplicate = client.post(
        f"/admin/users/usr_{client_id}/company-roles",
        json={"bitrix_company_id": "789", "role_code": "client_viewer"},
    )
    invalid_role = client.post(
        f"/admin/users/usr_{client_id}/company-roles",
        json={"bitrix_company_id": "790", "role_code": "partner"},
    )
    partner_assign = client.post(
        f"/admin/users/usr_{partner_id}/company-roles",
        json={"bitrix_company_id": "790", "role_code": "client_viewer"},
    )

    assert pending.status_code == 201
    assert pending.json()["company_role"]["access_status"] == "pending"
    assert pending.json()["company_role"]["bitrix_link_status"] == "bitrix_unavailable"
    assert duplicate.status_code == 409
    assert duplicate.json()["error_code"] == "COMPANY_ROLE_ALREADY_EXISTS"
    assert invalid_role.status_code == 400
    assert invalid_role.json()["error_code"] == "ROLE_NOT_ALLOWED"
    assert partner_assign.status_code == 400
    assert partner_assign.json()["error_code"] == "ROLE_NOT_ALLOWED"

    client.post("/auth/logout")
    login(client, "client@example.com")
    assert client.get("/me/companies").json() == {"items": []}


def test_blocked_user_cannot_be_assigned_and_bitrix_not_found_is_safe(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    blocked_id = create_user(migrated_database, email="blocked@example.com", status="blocked")
    client_id = create_user(migrated_database, email="client@example.com")

    import app.routers.company_access as access_router

    async def not_found_company(_company_id: int, _settings):
        raise BitrixError("BITRIX_NOT_FOUND")

    monkeypatch.setattr(access_router, "get_company", not_found_company)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    blocked = client.post(
        f"/admin/users/usr_{blocked_id}/company-roles",
        json={"bitrix_company_id": "321", "role_code": "client_executor"},
    )
    not_found = client.post(
        f"/admin/users/usr_{client_id}/company-roles",
        json={"bitrix_company_id": "321", "role_code": "client_executor"},
    )

    assert blocked.status_code == 403
    assert blocked.json()["error_code"] == "USER_BLOCKED"
    assert not_found.status_code == 404
    assert not_found.json()["error_code"] == "BITRIX_COMPANY_NOT_FOUND"


def test_company_access_logs_do_not_include_request_body(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com")

    import app.routers.company_access as access_router

    async def fake_get_company(_company_id: int, _settings):
        return {"TITLE": "Sensitive Company Title", "ADDRESS_COUNTRY_CODE": "GE"}

    monkeypatch.setattr(access_router, "get_company", fake_get_company)
    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    try:
        response = client.post(
            f"/admin/users/usr_{client_id}/company-roles",
            json={"bitrix_company_id": "654", "role_code": "client_admin"},
        )
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 201
    log_text = "\n".join(handler.messages)
    assert "request_completed" in log_text
    assert "Sensitive Company Title" not in log_text
    assert "client_admin" not in log_text


def test_superadmin_manages_partner_client_links_and_partner_scope(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    partner_id = create_user(
        migrated_database,
        email="partner@example.com",
        role_code=None,
        user_type="partner",
    )
    client_id = create_user(migrated_database, email="client@example.com")
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    created = client.post(
        f"/admin/partners/usr_{partner_id}/client-links",
        json={"bitrix_company_id": "777", "client_user_id": f"usr_{client_id}", "status": "active"},
    )
    duplicate = client.post(
        f"/admin/partners/usr_{partner_id}/client-links",
        json={"bitrix_company_id": "777", "client_user_id": f"usr_{client_id}", "status": "active"},
    )
    listed = client.get(f"/admin/partners/usr_{partner_id}/client-links")

    assert created.status_code == 201
    assert created.json()["partner_client_link"]["status"] == "active"
    assert duplicate.status_code == 409
    assert duplicate.json()["error_code"] == "PARTNER_CLIENT_LINK_ALREADY_EXISTS"
    assert listed.status_code == 200
    assert listed.json()["partner_client_links"][0]["bitrix_company_id"] == "777"

    client.post("/auth/logout")
    login(client, "partner@example.com")
    assert client.get("/me/companies").json() == {"items": []}
    partner_companies = client.get("/partner/companies")
    assert partner_companies.status_code == 200
    assert partner_companies.json()["items"][0]["bitrix_company_id"] == "777"

    client.post("/auth/logout")
    login(client, "admin@example.com")
    link_id = int(created.json()["partner_client_link"]["id"].removeprefix("pcl_"))
    revoked = client.post(f"/admin/partner-client-links/{link_id}/revoke")

    assert revoked.status_code == 200
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(partner_client_links)).mappings().one()
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert row.status == "revoked"
            assert row.access_status == "revoked"
            assert "partner_client_link_created" in actions
            assert "partner_client_link_revoked" in actions
    finally:
        engine.dispose()


def test_partner_link_rejects_non_partner_invalid_status_and_non_superadmin(
    monkeypatch,
    migrated_database: str,
) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com")
    partner_id = create_user(migrated_database, email="partner@example.com", role_code=None, user_type="partner")
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    forbidden = client.post(
        f"/admin/partners/usr_{partner_id}/client-links",
        json={"bitrix_company_id": "888", "status": "active"},
    )

    client.post("/auth/logout")
    login(client, "admin@example.com")
    non_partner = client.post(
        f"/admin/partners/usr_{client_id}/client-links",
        json={"bitrix_company_id": "888", "status": "active"},
    )
    invalid_status = client.post(
        f"/admin/partners/usr_{partner_id}/client-links",
        json={"bitrix_company_id": "888", "status": "revoked"},
    )
    valid_other = client.post(
        f"/admin/partners/usr_{partner_id}/client-links",
        json={"bitrix_company_id": "889", "status": "another_partner"},
    )

    assert forbidden.status_code == 403
    assert non_partner.status_code == 400
    assert non_partner.json()["error_code"] == "PARTNER_ROLE_REQUIRED"
    assert invalid_status.status_code == 400
    assert invalid_status.json()["error_code"] == "PARTNER_LINK_STATUS_NOT_ALLOWED"
    assert valid_other.status_code == 201
    assert valid_other.json()["partner_client_link"]["is_other_partner_client"] is True
