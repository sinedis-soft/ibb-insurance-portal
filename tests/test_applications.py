from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import audit_logs, portal_applications, portal_users, user_company_roles


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
    session: Session,
    *,
    email: str,
    role_code: str | None = "client_executor",
    user_type: str = "client",
    status: str = "active",
) -> int:
    return session.execute(
        insert(portal_users)
        .values(
            email=email,
            password_hash=hash_password("StrongPass123!"),
            status=status,
            user_type=user_type,
            role_code=role_code,
            language="ru",
        )
        .returning(portal_users.c.id)
    ).scalar_one()


def add_company_role(
    session: Session,
    *,
    user_id: int,
    bitrix_company_id: int,
    role_code: str = "client_executor",
    access_status: str = "active",
) -> None:
    session.execute(
        insert(user_company_roles).values(
            user_id=user_id,
            bitrix_company_id=bitrix_company_id,
            role_code=role_code,
            access_status=access_status,
            bitrix_link_status="confirmed",
        )
    )


def add_application(
    session: Session,
    *,
    bitrix_company_id: int,
    bitrix_deal_id: int,
    portal_status: str = "received",
    application_type: str = "auto",
    bitrix_category_id: int = 0,
    bitrix_stage_id: str = "NEW",
    title_cache: str = "Application",
    product_type_code: str = "green_card_ge",
) -> int:
    return session.execute(
        insert(portal_applications)
        .values(
            application_type=application_type,
            bitrix_deal_id=bitrix_deal_id,
            bitrix_company_id=bitrix_company_id,
            bitrix_contact_id=7500,
            portal_status=portal_status,
            bitrix_category_id=bitrix_category_id,
            bitrix_stage_id=bitrix_stage_id,
            product_type_code=product_type_code,
            title_cache=title_cache,
            client_reference_number="REF-001",
        )
        .returning(portal_applications.c.id)
    ).scalar_one()


def login(client: TestClient, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200


def seed_application_scope(database_url: str, *, role_code: str = "client_executor") -> tuple[int, int, int]:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user_id = create_user(session, email="client@example.com", role_code=role_code)
            add_company_role(session, user_id=user_id, bitrix_company_id=100, role_code=role_code)
            allowed_id = add_application(
                session,
                bitrix_company_id=100,
                bitrix_deal_id=70001,
                portal_status="draft",
                bitrix_stage_id="PREPAYMENT_INVOICE",
                title_cache="Border OC safe title",
            )
            denied_id = add_application(
                session,
                bitrix_company_id=101,
                bitrix_deal_id=70002,
                portal_status="received",
                bitrix_stage_id="NEW",
                title_cache="Other company title",
            )
            hidden_id = add_application(
                session,
                bitrix_company_id=100,
                bitrix_deal_id=70003,
                portal_status="in_work",
                bitrix_stage_id="UC_VEK6VN",
                title_cache="Hidden stage title",
            )
            session.commit()
            return allowed_id, denied_id, hidden_id
    finally:
        engine.dispose()


def test_application_list_returns_only_allowed_visible_applications(monkeypatch, migrated_database: str) -> None:
    allowed_id, _, hidden_id = seed_application_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    response = client.get("/applications?company_id=100")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert payload["items"][0]["id"] == f"app_{allowed_id}"
    assert payload["items"][0]["portal_status"] == "payment_expected"
    assert payload["items"][0]["status_label"] != "PREPAYMENT_INVOICE"
    assert "bitrix_stage_id" not in payload["items"][0]
    assert "bitrix_category_id" not in payload["items"][0]
    assert f"app_{hidden_id}" not in [item["id"] for item in payload["items"]]


def test_application_list_rejects_changed_company_id_and_inactive_access(
    monkeypatch,
    migrated_database: str,
) -> None:
    seed_application_scope(migrated_database)
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            pending_user_id = create_user(session, email="pending@example.com")
            add_company_role(
                session,
                user_id=pending_user_id,
                bitrix_company_id=100,
                access_status="pending",
            )
            revoked_user_id = create_user(session, email="revoked@example.com")
            add_company_role(
                session,
                user_id=revoked_user_id,
                bitrix_company_id=100,
                access_status="revoked",
            )
            session.commit()
    finally:
        engine.dispose()

    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")
    denied_company = client.get("/applications?company_id=101")

    client.post("/auth/logout")
    login(client, "pending@example.com")
    pending = client.get("/applications?company_id=100")

    client.post("/auth/logout")
    login(client, "revoked@example.com")
    revoked = client.get("/applications?company_id=100")

    assert denied_company.status_code == 403
    assert denied_company.json()["error_code"] == "COMPANY_ACCESS_DENIED"
    assert pending.status_code == 403
    assert revoked.status_code == 403


def test_application_detail_masks_foreign_and_hidden_applications(monkeypatch, migrated_database: str) -> None:
    allowed_id, denied_id, hidden_id = seed_application_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    allowed = client.get(f"/applications/app_{allowed_id}")
    foreign = client.get(f"/applications/app_{denied_id}")
    hidden = client.get(f"/applications/app_{hidden_id}")

    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["id"] == f"app_{allowed_id}"
    assert payload["document_requests"] == []
    assert payload["client_messages"] == []
    assert "upload_document" in payload["available_actions"]
    assert "request_change" in payload["available_actions"]
    assert "bitrix_stage_id" not in payload
    assert "comments" not in payload
    assert "document_url" not in payload
    assert foreign.status_code == 404
    assert hidden.status_code == 404


def test_application_actions_follow_client_role(monkeypatch, migrated_database: str) -> None:
    viewer_app_id, _, _ = seed_application_scope(migrated_database, role_code="client_viewer")
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            admin_id = create_user(session, email="admin@example.com", role_code="client_admin")
            add_company_role(session, user_id=admin_id, bitrix_company_id=200, role_code="client_admin")
            admin_app_id = add_application(
                session,
                bitrix_company_id=200,
                bitrix_deal_id=80001,
                title_cache="Admin app",
            )
            session.commit()
    finally:
        engine.dispose()

    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")
    viewer_detail = client.get(f"/applications/{viewer_app_id}")

    client.post("/auth/logout")
    login(client, "admin@example.com")
    admin_detail = client.get(f"/applications/{admin_app_id}")

    assert viewer_detail.status_code == 200
    assert viewer_detail.json()["available_actions"] == ["view_policy_status"]
    assert admin_detail.status_code == 200
    assert "upload_document" in admin_detail.json()["available_actions"]
    assert "request_policy_email" in admin_detail.json()["available_actions"]


def test_partner_and_blocked_user_do_not_receive_client_applications(monkeypatch, migrated_database: str) -> None:
    seed_application_scope(migrated_database)
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            create_user(session, email="partner@example.com", role_code=None, user_type="partner")
            create_user(session, email="blocked@example.com", status="blocked")
            session.commit()
    finally:
        engine.dispose()

    client = create_client(monkeypatch, migrated_database)
    login(client, "partner@example.com")
    partner_list = client.get("/applications")

    blocked_login = client.post("/auth/login", json={"email": "blocked@example.com", "password": "StrongPass123!"})

    assert partner_list.status_code == 200
    assert partner_list.json()["items"] == []
    assert blocked_login.status_code == 403


def test_application_access_denied_logging_is_sanitized(monkeypatch, migrated_database: str) -> None:
    _, denied_id, _ = seed_application_scope(migrated_database)
    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    try:
        response = client.get(f"/applications/{denied_id}")
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 404
    log_text = "\n".join(handler.messages)
    assert "access_denied" in log_text
    assert "Other company title" not in log_text
    assert "client@example.com" not in log_text
    assert "request body" not in log_text

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            audit_row = session.execute(
                select(audit_logs).where(audit_logs.c.action == "application_access_denied")
            ).mappings().one()
            assert audit_row.metadata_json["reason_code"] == "APPLICATION_ACCESS_DENIED"
            assert "Other company title" not in str(audit_row.metadata_json)
    finally:
        engine.dispose()
