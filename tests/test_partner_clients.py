from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.bitrix import BitrixError
from app.integrations.bitrix.field_mapping import (
    BITRIX_COMPANY_FIELDS,
    PARTNER_CLIENT_CHECK_COMPANY_STATUS_IDS,
)
from app.models import audit_logs, partner_client_requests, portal_applications, portal_users


class FakeRedis:
    async def get(self, _key: str) -> None:
        return None

    async def incr(self, _key: str) -> int:
        return 1

    async def expire(self, _key: str, _ttl: int) -> None:
        return None

    async def aclose(self) -> None:
        return None


def create_client(monkeypatch, migrated_database: str, company_calls: list[dict] | None = None) -> TestClient:
    from app.config import get_settings
    from app.main import create_app
    from app.routers import partner_clients

    async def redis_factory() -> FakeRedis:
        return FakeRedis()

    async def fake_create_company(fields, _settings=None):
        if company_calls is not None:
            company_calls.append(fields)
        return 9001

    import app.auth as auth_module

    monkeypatch.setattr(auth_module, "get_redis_client", redis_factory)
    monkeypatch.setattr(partner_clients, "create_company", fake_create_company)
    get_settings.cache_clear()
    return TestClient(create_app())


def create_user(
    database_url: str,
    *,
    email: str,
    role_code: str,
    user_type: str,
    password: str = "StrongPass123!",
    bitrix_contact_id: int | None = None,
) -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user_id = session.execute(
                insert(portal_users)
                .values(
                    email=email,
                    password_hash=hash_password(password),
                    status="active",
                    user_type=user_type,
                    role_code=role_code,
                    language="ru",
                    bitrix_contact_id=bitrix_contact_id,
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


def create_partner_client_request(
    database_url: str,
    *,
    partner_user_id: int,
    status: str = "pending",
    company_id: int = 700,
    linked_to_existing: bool = False,
    linked_company_id: int | None = None,
) -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            request_id = session.execute(
                insert(partner_client_requests)
                .values(
                    partner_user_id=partner_user_id,
                    created_by_user_id=partner_user_id,
                    company_name="Pending Logistics",
                    country="PL",
                    contact_name="Client Contact",
                    contact_email="client@example.invalid",
                    status=status,
                    bitrix_sync_status="synced",
                    bitrix_check_entity_type="company",
                    bitrix_check_entity_id=9001,
                    bitrix_check_status="confirmed" if linked_to_existing else status,
                    decision_status="linked_to_existing" if linked_to_existing else status,
                    linked_to_existing=linked_to_existing,
                    linked_bitrix_company_id=linked_company_id,
                    original_bitrix_company_id=9001 if linked_to_existing else None,
                    confirmed_bitrix_company_id=company_id if status == "confirmed" else None,
                    confirmed_company_id=company_id if status == "confirmed" else None,
                )
                .returning(partner_client_requests.c.id)
            ).scalar_one()
            session.commit()
            return request_id
    finally:
        engine.dispose()


def test_partner_can_create_pending_client_request(monkeypatch, migrated_database: str) -> None:
    partner_id = create_user(
        migrated_database,
        email="partner@example.com",
        role_code="partner",
        user_type="partner",
        bitrix_contact_id=777,
    )
    company_calls: list[dict] = []
    client = create_client(monkeypatch, migrated_database, company_calls=company_calls)
    login(client, "partner@example.com")

    response = client.post(
        "/partner/clients",
        json={
            "company_name": "Oceanic Shipping",
            "country": "PL",
            "registration_number": "REG-123",
            "contact_name": "Client Contact",
            "contact_email": "client@example.invalid",
            "contact_phone": "+48123456789",
            "comment": "Needs verification",
        },
    )

    assert response.status_code == 201
    payload = response.json()["client"]
    assert payload["status"] == "pending"
    assert payload["bitrix_check_status"] == "pending"
    assert payload["bitrix_sync_status"] == "synced"
    assert payload["partner_user_id"] == f"usr_{partner_id}"
    assert payload["bitrix_check_entity_type"] == "company"
    assert payload["bitrix_check_entity_id"] == 9001
    assert len(company_calls) == 1
    assert company_calls[0]["TITLE"] == "Oceanic Shipping"
    assert (
        company_calls[0][BITRIX_COMPANY_FIELDS["partner_client_check_status"]]
        == PARTNER_CLIENT_CHECK_COMPANY_STATUS_IDS["pending"]
    )
    assert company_calls[0][BITRIX_COMPANY_FIELDS["portal_partner_bitrix_id"]] == 777
    assert company_calls[0]["EMAIL"] == [{"VALUE": "client@example.invalid", "VALUE_TYPE": "WORK"}]
    assert company_calls[0]["PHONE"] == [{"VALUE": "+48123456789", "VALUE_TYPE": "WORK"}]

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert "partner_client_created" in actions
            assert "partner_client_check_bitrix_create_attempt" in actions
            assert "partner_client_check_bitrix_created" in actions
    finally:
        engine.dispose()


def test_partner_client_request_survives_bitrix_company_create_error(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_user(
        migrated_database,
        email="partner@example.com",
        role_code="partner",
        user_type="partner",
        bitrix_contact_id=777,
    )
    client = create_client(monkeypatch, migrated_database)

    from app.routers import partner_clients

    async def fake_create_company(_fields, _settings=None):
        raise BitrixError("ACCESS_DENIED")

    monkeypatch.setattr(partner_clients, "create_company", fake_create_company)
    login(client, "partner@example.com")

    response = client.post(
        "/partner/clients",
        json={
            "company_name": "Oceanic Shipping",
            "country": "PL",
            "contact_name": "Client Contact",
            "contact_email": "client@example.invalid",
        },
    )

    assert response.status_code == 201
    payload = response.json()["client"]
    assert payload["partner_user_id"] == f"usr_{partner_id}"
    assert payload["status"] == "pending"
    assert payload["bitrix_check_entity_type"] is None
    assert payload["bitrix_check_entity_id"] is None
    assert payload["bitrix_check_status"] == "pending"
    assert payload["bitrix_sync_status"] == "failed"
    assert payload["bitrix_sync_error"] == "ACCESS_DENIED"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert "partner_client_check_bitrix_create_failed" in actions
    finally:
        engine.dispose()


def test_partner_sees_only_own_pending_clients_and_superadmin_sees_all(monkeypatch, migrated_database: str) -> None:
    partner_id = create_user(migrated_database, email="partner@example.com", role_code="partner", user_type="partner")
    other_partner_id = create_user(
        migrated_database,
        email="other-partner@example.com",
        role_code="partner",
        user_type="partner",
    )
    create_user(migrated_database, email="admin@example.com", role_code="superadmin", user_type="client")
    own_id = create_partner_client_request(migrated_database, partner_user_id=partner_id)
    other_id = create_partner_client_request(migrated_database, partner_user_id=other_partner_id)
    client = create_client(monkeypatch, migrated_database)

    login(client, "partner@example.com")
    own_list = client.get("/partner/clients")
    foreign = client.get(f"/partner/clients/pcr_{other_id}")
    client.post("/auth/logout")
    login(client, "admin@example.com")
    admin_list = client.get("/admin/partner-clients")

    assert own_list.status_code == 200
    assert [item["id"] for item in own_list.json()["items"]] == [f"pcr_{own_id}"]
    assert foreign.status_code == 404
    assert {item["id"] for item in admin_list.json()["items"]} == {f"pcr_{own_id}", f"pcr_{other_id}"}


def test_client_user_cannot_see_partner_pending_clients(monkeypatch, migrated_database: str) -> None:
    partner_id = create_user(migrated_database, email="partner@example.com", role_code="partner", user_type="partner")
    create_user(
        migrated_database,
        email="client@example.com",
        role_code="client_executor",
        user_type="client",
    )
    create_partner_client_request(migrated_database, partner_user_id=partner_id)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    response = client.get("/partner/clients")

    assert response.status_code == 403
    assert response.json()["error_code"] == "PARTNER_ROLE_REQUIRED"


def test_partner_cannot_create_auto_or_cargo_application_for_non_confirmed_client(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_user(migrated_database, email="partner@example.com", role_code="partner", user_type="partner")
    pending_id = create_partner_client_request(migrated_database, partner_user_id=partner_id, status="pending")
    client = create_client(monkeypatch, migrated_database)
    login(client, "partner@example.com")

    auto_response = client.post(
        "/auto/applications/draft",
        json={
            "company_id": "700",
            "partner_client_request_id": f"pcr_{pending_id}",
            "product_code": "border_oc",
            "vehicle_registration_country_code": "GE",
            "coverage_zone_code": "EU",
            "vehicle": {"plate_number": "ABC123"},
            "period": {"start_date": "2026-09-01", "duration_days": 30},
        },
    )
    cargo_response = client.post(
        "/cargo/applications/draft",
        json={
            "company_id": "700",
            "partner_client_request_id": f"pcr_{pending_id}",
            "cargo_application_type": "single_shipment",
            "route": {"country_from": "PL", "country_to": "GE"},
            "cargo": {"cargo_type": "general_cargo", "cargo_value": "1000", "currency": "EUR"},
            "transport": {"transport_type": "road"},
        },
    )

    assert auto_response.status_code == 403
    assert auto_response.json()["error_code"] == "PARTNER_CLIENT_NOT_CONFIRMED"
    assert cargo_response.status_code == 403
    assert cargo_response.json()["error_code"] == "PARTNER_CLIENT_NOT_CONFIRMED"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert actions.count("partner_client_application_create_denied") == 2
            assert session.execute(select(portal_applications.c.id)).all() == []
    finally:
        engine.dispose()


def test_partner_cannot_create_auto_or_cargo_application_for_rejected_client(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_user(migrated_database, email="partner@example.com", role_code="partner", user_type="partner")
    rejected_id = create_partner_client_request(
        migrated_database,
        partner_user_id=partner_id,
        status="rejected",
    )
    client = create_client(monkeypatch, migrated_database)
    login(client, "partner@example.com")

    auto_response = client.post(
        "/auto/applications/draft",
        json={
            "company_id": "700",
            "partner_client_request_id": f"pcr_{rejected_id}",
            "product_code": "border_oc",
            "vehicle_registration_country_code": "GE",
            "coverage_zone_code": "EU",
            "vehicle": {"plate_number": "ABC123"},
            "period": {"start_date": "2026-09-01", "duration_days": 30},
        },
    )
    cargo_response = client.post(
        "/cargo/applications/draft",
        json={
            "company_id": "700",
            "partner_client_request_id": f"pcr_{rejected_id}",
            "cargo_application_type": "single_shipment",
            "route": {"country_from": "PL", "country_to": "GE"},
            "cargo": {"cargo_type": "general_cargo", "cargo_value": "1000", "currency": "EUR"},
            "transport": {"transport_type": "road"},
        },
    )

    assert auto_response.status_code == 403
    assert auto_response.json()["error_code"] == "PARTNER_CLIENT_REJECTED"
    assert cargo_response.status_code == 403
    assert cargo_response.json()["error_code"] == "PARTNER_CLIENT_REJECTED"


def test_partner_cannot_create_application_for_unresolved_duplicate(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_user(migrated_database, email="partner@example.com", role_code="partner", user_type="partner")
    duplicate_id = create_partner_client_request(
        migrated_database,
        partner_user_id=partner_id,
        status="duplicate_found",
    )
    client = create_client(monkeypatch, migrated_database)
    login(client, "partner@example.com")

    response = client.post(
        "/auto/applications/draft",
        json={
            "company_id": "700",
            "partner_client_request_id": f"pcr_{duplicate_id}",
            "product_code": "border_oc",
            "vehicle_registration_country_code": "GE",
            "coverage_zone_code": "EU",
            "vehicle": {"plate_number": "ABC123"},
            "period": {"start_date": "2026-09-01", "duration_days": 30},
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "PARTNER_CLIENT_DUPLICATE_UNRESOLVED"


def test_partner_can_create_applications_for_confirmed_own_client(monkeypatch, migrated_database: str) -> None:
    partner_id = create_user(migrated_database, email="partner@example.com", role_code="partner", user_type="partner")
    confirmed_id = create_partner_client_request(
        migrated_database,
        partner_user_id=partner_id,
        status="confirmed",
        company_id=700,
    )
    client = create_client(monkeypatch, migrated_database)
    login(client, "partner@example.com")

    auto_response = client.post(
        "/auto/applications/draft",
        json={
            "company_id": "700",
            "partner_client_request_id": f"pcr_{confirmed_id}",
            "product_code": "border_oc",
            "vehicle_registration_country_code": "GE",
            "coverage_zone_code": "EU",
            "vehicle": {"plate_number": "ABC123"},
            "period": {"start_date": "2026-09-01", "duration_days": 30},
        },
    )
    cargo_response = client.post(
        "/cargo/applications/draft",
        json={
            "company_id": "700",
            "partner_client_request_id": f"pcr_{confirmed_id}",
            "cargo_application_type": "single_shipment",
            "route": {"country_from": "PL", "country_to": "GE"},
            "cargo": {"cargo_type": "general_cargo", "cargo_value": "1000", "currency": "EUR"},
            "transport": {"transport_type": "road"},
        },
    )

    assert auto_response.status_code == 200
    assert auto_response.json()["status"] == "ok"
    assert cargo_response.status_code == 200
    assert cargo_response.json()["status"] == "ok"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            rows = session.execute(select(portal_applications).order_by(portal_applications.c.id)).mappings().all()
            assert [row.application_type for row in rows] == ["auto", "cargo"]
            assert all(row.partner_user_id == partner_id for row in rows)
            assert all(row.partner_client_request_id == confirmed_id for row in rows)
    finally:
        engine.dispose()


def test_partner_can_create_application_for_linked_existing_client(monkeypatch, migrated_database: str) -> None:
    partner_id = create_user(migrated_database, email="partner@example.com", role_code="partner", user_type="partner")
    linked_id = create_partner_client_request(
        migrated_database,
        partner_user_id=partner_id,
        status="confirmed",
        company_id=8123,
        linked_to_existing=True,
        linked_company_id=8123,
    )
    client = create_client(monkeypatch, migrated_database)
    login(client, "partner@example.com")

    response = client.post(
        "/auto/applications/draft",
        json={
            "company_id": "8123",
            "partner_client_request_id": f"pcr_{linked_id}",
            "product_code": "border_oc",
            "vehicle_registration_country_code": "GE",
            "coverage_zone_code": "EU",
            "vehicle": {"plate_number": "ABC123"},
            "period": {"start_date": "2026-09-01", "duration_days": 30},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            application = session.execute(select(portal_applications)).mappings().one()
            assert application.bitrix_company_id == 8123
            assert application.partner_client_request_id == linked_id
    finally:
        engine.dispose()


def test_partner_cannot_create_application_for_confirmed_other_partner_client(
    monkeypatch,
    migrated_database: str,
) -> None:
    partner_id = create_user(migrated_database, email="partner@example.com", role_code="partner", user_type="partner")
    other_partner_id = create_user(
        migrated_database,
        email="other-partner@example.com",
        role_code="partner",
        user_type="partner",
    )
    confirmed_id = create_partner_client_request(
        migrated_database,
        partner_user_id=other_partner_id,
        status="confirmed",
        company_id=700,
    )
    client = create_client(monkeypatch, migrated_database)
    login(client, "partner@example.com")

    response = client.post(
        "/auto/applications/draft",
        json={
            "company_id": "700",
            "partner_client_request_id": f"pcr_{confirmed_id}",
            "product_code": "border_oc",
            "vehicle_registration_country_code": "GE",
            "coverage_zone_code": "EU",
            "vehicle": {"plate_number": "ABC123"},
            "period": {"start_date": "2026-09-01", "duration_days": 30},
        },
    )

    assert partner_id != other_partner_id
    assert response.status_code == 404
    assert response.json()["error_code"] == "PARTNER_CLIENT_REQUEST_NOT_FOUND"
