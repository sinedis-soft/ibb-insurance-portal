from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import (
    audit_logs,
    document_transfer_logs,
    partner_client_links,
    portal_applications,
    portal_policies,
    portal_users,
    user_company_roles,
)


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
) -> int:
    return session.execute(
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


def add_company_role(
    session: Session,
    *,
    user_id: int,
    bitrix_company_id: int,
    company_title_cache: str = "Allowed Logistics",
) -> None:
    session.execute(
        insert(user_company_roles).values(
            user_id=user_id,
            bitrix_company_id=bitrix_company_id,
            role_code="client_executor",
            access_status="active",
            bitrix_link_status="confirmed",
            company_title_cache=company_title_cache,
        )
    )


def add_application(session: Session, *, bitrix_company_id: int, bitrix_deal_id: int, title: str) -> int:
    return session.execute(
        insert(portal_applications)
        .values(
            application_type="auto",
            bitrix_deal_id=bitrix_deal_id,
            bitrix_company_id=bitrix_company_id,
            bitrix_contact_id=7500,
            portal_status="policy_issued",
            product_type_code="auto",
            title_cache=title,
        )
        .returning(portal_applications.c.id)
    ).scalar_one()


def add_document(session: Session, *, application_id: int, is_policy_file: bool = True) -> int:
    return session.execute(
        insert(document_transfer_logs)
        .values(
            application_id=application_id,
            bitrix_document_id="B24-DOC-1",
            document_type="policy_file" if is_policy_file else "client_document",
            is_policy_file=is_policy_file,
            transfer_status="sent",
        )
        .returning(document_transfer_logs.c.id)
    ).scalar_one()


def add_policy(
    session: Session,
    *,
    application_id: int,
    bitrix_company_id: int,
    bitrix_deal_id: int,
    policy_number: str,
    policy_status: str = "active",
    valid_to: date | None = None,
    document_transfer_log_id: int | None = None,
) -> int:
    return session.execute(
        insert(portal_policies)
        .values(
            application_id=application_id,
            bitrix_deal_id=bitrix_deal_id,
            bitrix_company_id=bitrix_company_id,
            policy_number=policy_number,
            product_type_code="auto",
            valid_from=date.today() - timedelta(days=10),
            valid_to=valid_to,
            premium_amount=Decimal("1200.50"),
            premium_currency="USD",
            policy_status=policy_status,
            document_transfer_log_id=document_transfer_log_id,
        )
        .returning(portal_policies.c.id)
    ).scalar_one()


def login(client: TestClient, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200


def seed_policy_scope(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user_id = create_user(session, email="client@example.com")
            add_company_role(session, user_id=user_id, bitrix_company_id=100)
            other_user_id = create_user(session, email="other@example.com")
            add_company_role(
                session,
                user_id=other_user_id,
                bitrix_company_id=200,
                company_title_cache="Foreign Logistics",
            )
            partner_id = create_user(session, email="partner@example.com", role_code=None, user_type="partner")
            allowed_app = add_application(session, bitrix_company_id=100, bitrix_deal_id=90001, title="Allowed app")
            other_app = add_application(session, bitrix_company_id=200, bitrix_deal_id=90002, title="Foreign app")
            session.execute(
                insert(partner_client_links).values(
                    partner_user_id=partner_id,
                    bitrix_company_id=100,
                    status="active",
                    access_status="active",
                )
            )
            document_id = add_document(session, application_id=allowed_app)
            active_id = add_policy(
                session,
                application_id=allowed_app,
                bitrix_company_id=100,
                bitrix_deal_id=90001,
                policy_number="POL-ACTIVE-001",
                valid_to=date.today() + timedelta(days=90),
                document_transfer_log_id=document_id,
            )
            soon_id = add_policy(
                session,
                application_id=allowed_app,
                bitrix_company_id=100,
                bitrix_deal_id=90001,
                policy_number="POL-SOON-002",
                valid_to=date.today() + timedelta(days=12),
            )
            expired_id = add_policy(
                session,
                application_id=allowed_app,
                bitrix_company_id=100,
                bitrix_deal_id=90001,
                policy_number="POL-ARCHIVE-003",
                policy_status="expired",
                valid_to=date.today() - timedelta(days=1),
            )
            foreign_id = add_policy(
                session,
                application_id=other_app,
                bitrix_company_id=200,
                bitrix_deal_id=90002,
                policy_number="POL-FOREIGN-004",
                valid_to=date.today() + timedelta(days=90),
            )
            session.commit()
            return {
                "active_id": active_id,
                "soon_id": soon_id,
                "expired_id": expired_id,
                "foreign_id": foreign_id,
            }
    finally:
        engine.dispose()


def test_policy_list_returns_only_visible_allowed_policies(monkeypatch, migrated_database: str) -> None:
    ids = seed_policy_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    response = client.get("/policies?company_id=100")

    assert response.status_code == 200
    payload = response.json()
    item_ids = {item["id"] for item in payload["items"]}
    assert item_ids == {f"policy_{ids['active_id']}", f"policy_{ids['soon_id']}"}
    assert f"policy_{ids['expired_id']}" not in item_ids
    assert f"policy_{ids['foreign_id']}" not in item_ids
    soon = next(item for item in payload["items"] if item["id"] == f"policy_{ids['soon_id']}")
    assert soon["policy_status"] == "expiring_soon"
    assert soon["status_label"] != "expiring_soon"


def test_policy_search_is_scoped_and_archive_is_not_returned(monkeypatch, migrated_database: str) -> None:
    seed_policy_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    foreign = client.get("/policies?q=FOREIGN")
    archived = client.get("/policies?q=ARCHIVE")
    visible = client.get("/policies?q=SOON")

    assert foreign.status_code == 200
    assert foreign.json()["items"] == []
    assert archived.status_code == 200
    assert archived.json()["items"] == []
    assert visible.status_code == 200
    assert [item["policy_number"] for item in visible.json()["items"]] == ["POL-SOON-002"]


def test_policy_company_scope_rejects_changed_company(monkeypatch, migrated_database: str) -> None:
    seed_policy_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    response = client.get("/policies?company_id=200")

    assert response.status_code == 403
    assert response.json()["error_code"] == "COMPANY_ACCESS_DENIED"


def test_policy_detail_masks_foreign_and_partner_access(monkeypatch, migrated_database: str) -> None:
    ids = seed_policy_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    allowed = client.get(f"/policies/policy_{ids['active_id']}")
    foreign = client.get(f"/policies/policy_{ids['foreign_id']}")

    client.post("/auth/logout")
    login(client, "partner@example.com")
    partner_list = client.get("/policies")
    partner_detail = client.get(f"/policies/policy_{ids['active_id']}")

    assert allowed.status_code == 200
    assert foreign.status_code == 404
    assert partner_list.status_code == 200
    assert partner_list.json()["items"] == []
    assert partner_detail.status_code == 404


def test_policy_document_metadata_is_safe(monkeypatch, migrated_database: str) -> None:
    ids = seed_policy_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    response = client.get(f"/policies/{ids['active_id']}")

    assert response.status_code == 200
    documents = response.json()["documents"]
    assert documents == [
        {
            "id": "doc_1",
            "document_type": "policy_file",
            "label": "policy_file",
            "is_policy_file": True,
            "transfer_status": "sent",
            "is_download_available": True,
        }
    ]
    assert "url" not in str(documents).lower()
    assert "path" not in str(documents).lower()
    assert "filename" not in str(documents).lower()


def test_policy_access_denied_logging_is_sanitized(monkeypatch, migrated_database: str) -> None:
    ids = seed_policy_scope(migrated_database)
    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    try:
        response = client.get(f"/policies/{ids['foreign_id']}")
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 404
    log_text = "\n".join(handler.messages)
    assert "access_denied" in log_text
    assert "POL-FOREIGN-004" not in log_text
    assert "client@example.com" not in log_text

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            audit_row = session.execute(
                select(audit_logs).where(audit_logs.c.action == "application_access_denied")
            ).mappings().one()
            assert audit_row.metadata_json["reason_code"] == "APPLICATION_ACCESS_DENIED"
            assert "POL-FOREIGN-004" not in str(audit_row.metadata_json)
    finally:
        engine.dispose()


def test_policy_search_by_company_title_stays_inside_scope(monkeypatch, migrated_database: str) -> None:
    seed_policy_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    visible = client.get("/policies?q=Allowed")
    foreign = client.get("/policies?q=Foreign")

    assert visible.status_code == 200
    assert {item["policy_number"] for item in visible.json()["items"]} == {"POL-ACTIVE-001", "POL-SOON-002"}
    assert foreign.status_code == 200
    assert foreign.json()["items"] == []


def test_allowed_document_download_is_streamed_and_audited(monkeypatch, migrated_database: str) -> None:
    seed_policy_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    response = client.get("/documents/doc_1/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert "ibb-document-1.bin" in response.headers["content-disposition"]
    assert b"doc_1" in response.content
    assert b"http" not in response.content.lower()
    assert b"storage" not in response.content.lower()

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            audit_row = session.execute(
                select(audit_logs).where(audit_logs.c.action == "document_downloaded")
            ).mappings().one()
            assert audit_row.object_id == "1"
            assert audit_row.metadata_json["status"] == "allowed"
    finally:
        engine.dispose()


def test_document_download_denies_foreign_guess_and_partner_policy_file(
    monkeypatch,
    migrated_database: str,
) -> None:
    seed_policy_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "other@example.com")

    foreign_guess = client.get("/documents/doc_1/download")

    client.post("/auth/logout")
    login(client, "partner@example.com")
    partner_download = client.get("/documents/doc_1/download")

    assert foreign_guess.status_code == 404
    assert foreign_guess.json()["error_code"] == "DOCUMENT_NOT_FOUND"
    assert partner_download.status_code == 404
    assert partner_download.json()["error_code"] == "DOCUMENT_NOT_FOUND"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            denied_rows = (
                session.execute(select(audit_logs).where(audit_logs.c.action == "document_download_denied"))
                .mappings()
                .all()
            )
            assert len(denied_rows) == 2
            assert "POL-ACTIVE-001" not in str([row.metadata_json for row in denied_rows])
    finally:
        engine.dispose()
