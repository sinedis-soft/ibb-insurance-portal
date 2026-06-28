from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.integrations.bitrix.errors import Bitrix24PermissionError, Bitrix24RateLimitError
from app.models import (
    audit_logs,
    document_transfer_logs,
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


class FakeBitrixClient:
    def __init__(self, deals: dict[int, dict[str, Any]] | None = None, error: Exception | None = None) -> None:
        self.deals = deals or {}
        self.error = error
        self.calls: list[int] = []

    async def get_deal(self, deal_id: int) -> dict[str, Any]:
        self.calls.append(deal_id)
        if self.error:
            raise self.error
        return self.deals[deal_id]


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
    role_code: str = "client_executor",
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


def add_company_role(session: Session, *, user_id: int, bitrix_company_id: int) -> None:
    session.execute(
        insert(user_company_roles).values(
            user_id=user_id,
            bitrix_company_id=bitrix_company_id,
            role_code="client_executor",
            access_status="active",
            bitrix_link_status="confirmed",
            company_title_cache="Sync Company",
        )
    )


def add_application(
    session: Session,
    *,
    bitrix_deal_id: int = 90001,
    bitrix_company_id: int = 100,
    category_id: int = 0,
    portal_status: str = "received",
) -> int:
    return session.execute(
        insert(portal_applications)
        .values(
            application_type="auto",
            bitrix_deal_id=bitrix_deal_id,
            bitrix_company_id=bitrix_company_id,
            bitrix_contact_id=7500,
            portal_status=portal_status,
            bitrix_category_id=category_id,
            bitrix_stage_id="NEW" if category_id == 0 else "C19:NEW",
            product_type_code="auto",
            title_cache="Sync app",
            sync_status="synced",
        )
        .returning(portal_applications.c.id)
    ).scalar_one()


def seed_sync_scope(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            admin_id = create_user(session, email="admin@example.com", role_code="superadmin")
            client_id = create_user(session, email="client@example.com")
            add_company_role(session, user_id=client_id, bitrix_company_id=100)
            app_id = add_application(session)
            session.commit()
            return {"admin_id": admin_id, "client_id": client_id, "app_id": app_id}
    finally:
        engine.dispose()


def login(client: TestClient, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200


def patch_policy_mapping(monkeypatch) -> None:
    from app.integrations.bitrix import sync as bitrix_sync

    mapping = bitrix_sync.BITRIX_POLICY_FIELDS
    monkeypatch.setitem(mapping, "policy_number", "POLICY_NUMBER")
    monkeypatch.setitem(mapping, "policy_start_date", "POLICY_START")
    monkeypatch.setitem(mapping, "policy_end_date", "POLICY_END")
    monkeypatch.setitem(mapping, "insurer", "INSURER")
    monkeypatch.setitem(mapping, "product", "PRODUCT")
    monkeypatch.setitem(mapping, "policy_document", "POLICY_FILE")


def test_admin_sync_maps_stage_and_client_detail_hides_raw_stage(monkeypatch, migrated_database: str) -> None:
    ids = seed_sync_scope(migrated_database)
    fake_client = FakeBitrixClient({90001: {"ID": "90001", "CATEGORY_ID": "0", "STAGE_ID": "PREPARATION"}})
    from app.integrations.bitrix import sync as bitrix_sync

    monkeypatch.setattr(bitrix_sync, "get_bitrix24_client", lambda: fake_client)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    response = client.post(f"/admin/integrations/bitrix/sync/applications/app_{ids['app_id']}")

    assert response.status_code == 200
    assert response.json()["portal_status"] == "in_work"
    client.post("/auth/logout")
    login(client, "client@example.com")
    detail = client.get(f"/applications/app_{ids['app_id']}")
    assert detail.status_code == 200
    assert detail.json()["portal_status"] == "in_work"
    assert "STAGE_ID" not in str(detail.json())
    assert "PREPARATION" not in str(detail.json())


def test_policy_issued_sync_updates_policy_cache_and_document_metadata(monkeypatch, migrated_database: str) -> None:
    ids = seed_sync_scope(migrated_database)
    patch_policy_mapping(monkeypatch)
    fake_client = FakeBitrixClient(
        {
            90001: {
                "ID": "90001",
                "CATEGORY_ID": "0",
                "STAGE_ID": "FINAL_INVOICE",
                "POLICY_NUMBER": "POL-SYNC-001",
                "POLICY_START": "2026-06-01",
                "POLICY_END": "2027-09-24",
                "OPPORTUNITY": "1200.50",
                "CURRENCY_ID": "USD",
                "INSURER": "Global Shield",
                "PRODUCT": "auto",
                "POLICY_FILE": {"ID": "B24-FILE-1"},
            }
        }
    )
    from app.integrations.bitrix import sync as bitrix_sync

    monkeypatch.setattr(bitrix_sync, "get_bitrix24_client", lambda: fake_client)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    response = client.post(f"/admin/integrations/bitrix/sync/applications/app_{ids['app_id']}")

    assert response.status_code == 200
    assert response.json()["portal_status"] == "policy_issued"
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            policy = session.execute(select(portal_policies)).mappings().one()
            document = session.execute(select(document_transfer_logs)).mappings().one()
            assert policy.policy_number == "POL-SYNC-001"
            assert policy.insurer_name == "Global Shield"
            assert policy.premium_amount == Decimal("1200.50")
            assert policy.document_transfer_log_id == document.id
            assert document.bitrix_file_id == "B24-FILE-1"
            assert document.storage_key is None
            assert document.temporary_storage_path is None
            audit_text = str(session.execute(select(audit_logs)).mappings().all())
            assert "POL-SYNC-001" not in audit_text
            assert "1200.50" not in audit_text
    finally:
        engine.dispose()

    client.post("/auth/logout")
    login(client, "client@example.com")
    policies = client.get("/policies")
    assert policies.status_code == 200
    item = policies.json()["items"][0]
    assert item["policy_number"] == "POL-SYNC-001"
    assert item["insurer_name"] == "Global Shield"
    assert "url" not in str(item).lower()


def test_policy_issued_with_incomplete_fields_stays_policy_issuing(monkeypatch, migrated_database: str) -> None:
    ids = seed_sync_scope(migrated_database)
    patch_policy_mapping(monkeypatch)
    fake_client = FakeBitrixClient({90001: {"ID": "90001", "CATEGORY_ID": "0", "STAGE_ID": "FINAL_INVOICE"}})
    from app.integrations.bitrix import sync as bitrix_sync

    monkeypatch.setattr(bitrix_sync, "get_bitrix24_client", lambda: fake_client)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    response = client.post(f"/admin/integrations/bitrix/sync/applications/app_{ids['app_id']}")

    assert response.status_code == 200
    assert response.json()["portal_status"] == "policy_issuing"
    assert response.json()["warning_code"] == "POLICY_DATA_INCOMPLETE"
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            assert session.execute(select(portal_policies)).mappings().all() == []
            app = session.execute(select(portal_applications)).mappings().one()
            assert app.last_sync_warning_code == "POLICY_DATA_INCOMPLETE"
            audit_row = session.execute(
                select(audit_logs).where(audit_logs.c.action == "policy_data_incomplete")
            ).mappings().one()
            assert audit_row.metadata_json["reason_code"] == "POLICY_DATA_INCOMPLETE"
    finally:
        engine.dispose()


def test_sync_errors_are_safe_and_superadmin_only(monkeypatch, migrated_database: str) -> None:
    ids = seed_sync_scope(migrated_database)
    fake_client = FakeBitrixClient(error=Bitrix24RateLimitError("QUERY_LIMIT_EXCEEDED"))
    from app.integrations.bitrix import sync as bitrix_sync

    monkeypatch.setattr(bitrix_sync, "get_bitrix24_client", lambda: fake_client)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")
    denied = client.get("/admin/integrations/bitrix/sync/errors")

    client.post("/auth/logout")
    login(client, "admin@example.com")
    synced = client.post(f"/admin/integrations/bitrix/sync/applications/app_{ids['app_id']}")
    errors = client.get("/admin/integrations/bitrix/sync/errors")

    assert denied.status_code == 403
    assert synced.status_code == 200
    assert synced.json()["status"] == "failed"
    assert synced.json()["error_code"] == "BITRIX24_QUERY_LIMIT_EXCEEDED"
    assert errors.status_code == 200
    assert errors.json()["items"] == [
        {
            "application_id": f"app_{ids['app_id']}",
            "bitrix_deal_id": 90001,
            "sync_status": "retry_required",
            "error_code": "BITRIX24_QUERY_LIMIT_EXCEEDED",
            "warning_code": None,
            "last_attempt_at": errors.json()["items"][0]["last_attempt_at"],
        }
    ]
    assert "QUERY_LIMIT_EXCEEDED" not in str(errors.json()["items"][0].get("payload", ""))


def test_access_denied_sync_error_is_not_retryable(monkeypatch, migrated_database: str) -> None:
    ids = seed_sync_scope(migrated_database)
    fake_client = FakeBitrixClient(error=Bitrix24PermissionError("Access denied"))
    from app.integrations.bitrix import sync as bitrix_sync

    monkeypatch.setattr(bitrix_sync, "get_bitrix24_client", lambda: fake_client)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    response = client.post(f"/admin/integrations/bitrix/sync/applications/app_{ids['app_id']}")

    assert response.status_code == 200
    assert response.json()["error_code"] == "BITRIX24_ACCESS_DENIED"
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            app = session.execute(select(portal_applications)).mappings().one()
            assert app.sync_status == "sync_error"
            assert app.last_sync_error_code == "BITRIX24_ACCESS_DENIED"
    finally:
        engine.dispose()
