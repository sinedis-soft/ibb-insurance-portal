from __future__ import annotations

import logging
from datetime import date

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


def create_user(session: Session, *, email: str, role_code: str = "client_executor") -> int:
    return session.execute(
        insert(portal_users)
        .values(
            email=email,
            password_hash=hash_password("StrongPass123!"),
            status="active",
            user_type="client",
            role_code=role_code,
            language="ru",
            bitrix_contact_id=7500,
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
    company_country_code: str = "PL",
) -> None:
    session.execute(
        insert(user_company_roles).values(
            user_id=user_id,
            bitrix_company_id=bitrix_company_id,
            role_code=role_code,
            access_status=access_status,
            bitrix_link_status="confirmed",
            company_title_cache="Auto Company",
            company_country_code_cache=company_country_code,
        )
    )


def login(client: TestClient, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200


def auto_payload(*, company_id: str = "100", product_code: str = "border_oc") -> dict:
    return {
        "company_id": company_id,
        "product_code": product_code,
        "vehicle_registration_country_code": "GE",
        "coverage_country_code": "PL",
        "coverage_zone_code": "EU",
        "vehicle": {
            "plate_number": "TEST-123",
            "vin": "VINSHOULDNOTLOG123",
            "vehicle_type": "passenger_car",
            "brand_model": "Toyota Corolla",
            "production_year": 2020,
            "engine_volume": 1800,
            "power_kw": 100,
        },
        "period": {"start_date": date.today().isoformat(), "duration_days": 30},
    }


def seed_users(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            executor = create_user(session, email="executor@example.com")
            add_company_role(session, user_id=executor, bitrix_company_id=100)
            admin = create_user(session, email="admin@example.com", role_code="client_admin")
            add_company_role(session, user_id=admin, bitrix_company_id=101, role_code="client_admin")
            viewer = create_user(session, email="viewer@example.com", role_code="client_viewer")
            add_company_role(session, user_id=viewer, bitrix_company_id=102, role_code="client_viewer")
            revoked = create_user(session, email="revoked@example.com")
            add_company_role(session, user_id=revoked, bitrix_company_id=100, access_status="revoked")
            session.commit()
    finally:
        engine.dispose()


def test_available_products_follow_role_and_country_rules(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")

    response = client.get(
        "/auto/products/available"
        "?company_id=100&vehicle_registration_country_code=GE&coverage_country_code=PL&coverage_zone_code=EU"
    )
    invalid_combo = client.get(
        "/auto/products/available"
        "?company_id=100&vehicle_registration_country_code=PL&coverage_country_code=PL&coverage_zone_code=EU"
    )

    client.post("/auth/logout")
    login(client, "viewer@example.com")
    viewer = client.get(
        "/auto/products/available"
        "?company_id=102&vehicle_registration_country_code=GE&coverage_country_code=PL&coverage_zone_code=EU"
    )

    assert response.status_code == 200
    assert "border_oc" in {item["code"] for item in response.json()["items"]}
    assert "border_oc" not in {item["code"] for item in invalid_combo.json()["items"]}
    assert viewer.status_code == 200
    assert viewer.json()["items"] == []


def test_validate_rejects_unavailable_product_and_foreign_company(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")

    unavailable_payload = auto_payload(product_code="pl_oc")
    unavailable = client.post("/auto/applications/validate", json=unavailable_payload)
    foreign = client.post("/auto/applications/validate", json=auto_payload(company_id="101"))

    assert unavailable.status_code == 200
    assert unavailable.json()["status"] == "invalid"
    assert unavailable.json()["errors"][0]["error_code"] == "AUTO_PRODUCT_NOT_AVAILABLE"
    assert foreign.status_code == 403
    assert foreign.json()["error_code"] == "COMPANY_ACCESS_DENIED"


def test_save_and_update_auto_draft(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")

    saved = client.post("/auto/applications/draft", json=auto_payload())
    app_id = saved.json()["id"]
    updated_payload = auto_payload(product_code="osago_rf")
    updated_payload["coverage_country_code"] = "RU"
    updated_payload["coverage_zone_code"] = None
    updated = client.patch(f"/auto/applications/{app_id}/draft", json=updated_payload)

    assert saved.status_code == 200
    assert saved.json()["status"] == "ok"
    assert updated.status_code == 200
    assert updated.json()["status"] == "ok"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(portal_applications)).mappings().one()
            assert row.portal_status == "draft"
            assert row.application_type == "auto"
            assert row.bitrix_deal_id is None
            assert row.product_type_code == "osago_rf"
            assert row.draft_data_json["vehicle"]["plate_number"] == "TEST-123"
    finally:
        engine.dispose()


def test_viewer_revoked_and_foreign_draft_updates_are_blocked(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")
    saved = client.post("/auto/applications/draft", json=auto_payload())
    app_id = saved.json()["id"]

    client.post("/auth/logout")
    login(client, "viewer@example.com")
    viewer_save = client.post("/auto/applications/draft", json=auto_payload(company_id="102"))

    client.post("/auth/logout")
    login(client, "revoked@example.com")
    revoked_save = client.post("/auto/applications/draft", json=auto_payload())

    client.post("/auth/logout")
    login(client, "admin@example.com")
    foreign_update = client.patch(f"/auto/applications/{app_id}/draft", json=auto_payload(company_id="101"))

    assert viewer_save.status_code == 403
    assert revoked_save.status_code == 403
    assert foreign_update.status_code == 404


def test_auto_draft_safe_logging_and_audit_do_not_store_payload(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")

    try:
        response = client.post("/auto/applications/draft", json=auto_payload(product_code="pl_oc"))
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    log_text = "\n".join(handler.messages)
    assert "TEST-123" not in log_text
    assert "VINSHOULDNOTLOG123" not in log_text
    assert "Toyota Corolla" not in log_text

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            audit_row = session.execute(
                select(audit_logs).where(audit_logs.c.action == "auto_application_validation_failed")
            ).mappings().one()
            assert audit_row.metadata_json["product_code"] == "pl_oc"
            assert "TEST-123" not in str(audit_row.metadata_json)
            assert "VINSHOULDNOTLOG123" not in str(audit_row.metadata_json)
    finally:
        engine.dispose()
