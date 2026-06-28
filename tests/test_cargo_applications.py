from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import audit_logs, portal_applications, portal_users, user_company_roles


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


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
) -> None:
    session.execute(
        insert(user_company_roles).values(
            user_id=user_id,
            bitrix_company_id=bitrix_company_id,
            role_code=role_code,
            access_status=access_status,
            bitrix_link_status="confirmed",
            company_title_cache="Cargo Company",
            company_country_code_cache="PL",
            portal_applications_allowed_cache=True,
            cargo_dionis_allowed_cache=True,
            cargo_deda_allowed_cache=True,
            cargo_russian_insurers_allowed_cache=True,
            cargo_belarusian_insurers_allowed_cache=True,
            cargo_polish_insurers_allowed_cache=True,
        )
    )


def login(client: TestClient, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200


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
            pending = create_user(session, email="pending@example.com")
            add_company_role(session, user_id=pending, bitrix_company_id=103, access_status="pending")
            create_user(session, email="partner@example.com", role_code="partner", user_type="partner")
            session.commit()
    finally:
        engine.dispose()


def cargo_payload(
    *,
    company_id: str = "100",
    cargo_application_type: str = "single_shipment",
) -> dict:
    return {
        "company_id": company_id,
        "cargo_application_type": cargo_application_type,
        "route": {
            "country_from": "PL",
            "country_to": "GE",
            "route_description": "Sensitive route description",
        },
        "cargo": {
            "cargo_type": "general_cargo",
            "cargo_description": "Sensitive cargo details",
            "cargo_value": "12500.50",
            "currency": "EUR",
        },
        "transport": {
            "transport_type": "road",
            "carrier_name": "Sensitive Carrier",
            "vehicle_plate": "CARGO-SECRET",
            "departure_date": "2026-09-08",
        },
        "contract": {
            "bitrix_contract_deal_id": None,
            "contract_number": None,
            "is_active_contract": False,
        },
        "certificate": {"is_certificate_requested": False},
        "documents": {"has_supporting_document": True},
        "comment": "Sensitive comment",
    }


def contract_payload(**kwargs) -> dict:
    payload = cargo_payload(cargo_application_type="contract_coverage", **kwargs)
    payload["contract"] = {
        "bitrix_contract_deal_id": 7001,
        "contract_number": "CONTRACT-1",
        "is_active_contract": True,
    }
    return payload


def certificate_payload(**kwargs) -> dict:
    payload = cargo_payload(cargo_application_type="certificate", **kwargs)
    payload["contract"] = {
        "bitrix_contract_deal_id": 7001,
        "contract_number": "CONTRACT-1",
        "is_active_contract": True,
    }
    payload["certificate"] = {"is_certificate_requested": True}
    return payload


def test_reference_data_returns_three_cargo_application_types(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")

    response = client.get("/cargo/reference-data")

    assert response.status_code == 200
    assert {item["code"] for item in response.json()["application_types"]} == {
        "single_shipment",
        "contract_coverage",
        "certificate",
    }


def test_validation_rejects_invalid_type_and_required_fields(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")
    invalid_type = cargo_payload(cargo_application_type="bad_type")
    missing = cargo_payload()
    missing["route"]["country_from"] = ""
    missing["cargo"]["cargo_value"] = ""
    missing["cargo"]["currency"] = ""
    missing["transport"]["transport_type"] = ""

    invalid_response = client.post("/cargo/applications/validate", json=invalid_type)
    missing_response = client.post("/cargo/applications/validate", json=missing)

    assert invalid_response.status_code == 200
    assert invalid_response.json()["errors"][0]["error_code"] == "CARGO_APPLICATION_TYPE_INVALID"
    assert missing_response.status_code == 200
    assert {
        "CARGO_COUNTRY_FROM_REQUIRED",
        "CARGO_VALUE_REQUIRED",
        "CARGO_CURRENCY_REQUIRED",
        "CARGO_TRANSPORT_TYPE_REQUIRED",
    }.issubset({error["error_code"] for error in missing_response.json()["errors"]})


def test_contract_and_certificate_require_active_contract(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")
    contract = contract_payload()
    contract["contract"]["is_active_contract"] = False
    certificate = certificate_payload()
    certificate["contract"]["contract_number"] = ""
    certificate["contract"]["bitrix_contract_deal_id"] = None
    certificate["certificate"]["is_certificate_requested"] = False

    contract_response = client.post("/cargo/applications/validate", json=contract)
    certificate_response = client.post("/cargo/applications/validate", json=certificate)

    assert contract_response.status_code == 200
    assert contract_response.json()["errors"][0]["error_code"] == "CARGO_ACTIVE_CONTRACT_REQUIRED"
    assert certificate_response.status_code == 200
    assert "CARGO_CERTIFICATE_CONTRACT_REQUIRED" in {
        error["error_code"] for error in certificate_response.json()["errors"]
    }


def test_save_restore_and_update_cargo_draft(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")

    saved = client.post("/cargo/applications/draft", json=cargo_payload())
    app_id = saved.json()["id"]
    restored = client.get(f"/cargo/applications/{app_id}/draft")
    updated = client.patch(f"/cargo/applications/{app_id}/draft", json=certificate_payload())

    assert saved.status_code == 200
    assert saved.json()["status"] == "ok"
    assert restored.status_code == 200
    assert restored.json()["draft_data"]["cargo_application_type"] == "single_shipment"
    assert updated.status_code == 200
    assert updated.json()["status"] == "ok"

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(portal_applications)).mappings().one()
            assert row.application_type == "cargo"
            assert row.portal_status == "draft"
            assert row.bitrix_category_id == 19
            assert row.bitrix_deal_id is None
            assert row.product_type_code == "cargo_document_request"
            assert row.draft_data_json["certificate"]["is_certificate_requested"] is True
    finally:
        engine.dispose()


def test_access_blocks_viewer_foreign_pending_revoked_and_partner(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")
    saved = client.post("/cargo/applications/draft", json=cargo_payload())
    app_id = saved.json()["id"]

    client.post("/auth/logout")
    login(client, "viewer@example.com")
    viewer_save = client.post("/cargo/applications/draft", json=cargo_payload(company_id="102"))

    client.post("/auth/logout")
    login(client, "revoked@example.com")
    revoked_save = client.post("/cargo/applications/draft", json=cargo_payload())

    client.post("/auth/logout")
    login(client, "pending@example.com")
    pending_save = client.post("/cargo/applications/draft", json=cargo_payload(company_id="103"))

    client.post("/auth/logout")
    login(client, "partner@example.com")
    partner_save = client.post("/cargo/applications/draft", json=cargo_payload(company_id="104"))

    client.post("/auth/logout")
    login(client, "admin@example.com")
    foreign_restore = client.get(f"/cargo/applications/{app_id}/draft")
    foreign_update = client.patch(f"/cargo/applications/{app_id}/draft", json=cargo_payload(company_id="101"))

    assert viewer_save.status_code == 403
    assert revoked_save.status_code == 403
    assert pending_save.status_code == 403
    assert partner_save.status_code == 403
    assert foreign_restore.status_code == 404
    assert foreign_update.status_code == 404


def test_invalid_value_currency_and_non_editable_status(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")
    invalid_value = cargo_payload()
    invalid_value["cargo"]["cargo_value"] = "-1"
    invalid_value["cargo"]["currency"] = ""

    invalid_response = client.post("/cargo/applications/validate", json=invalid_value)
    saved = client.post("/cargo/applications/draft", json=cargo_payload())
    app_id = saved.json()["id"]

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            parsed_id = int(app_id.removeprefix("app_"))
            session.execute(
                update(portal_applications)
                .where(portal_applications.c.id == parsed_id)
                .values(portal_status="received")
            )
            session.commit()
    finally:
        engine.dispose()

    non_editable = client.patch(f"/cargo/applications/{app_id}/draft", json=cargo_payload())

    assert invalid_response.status_code == 200
    assert {"CARGO_VALUE_INVALID", "CARGO_CURRENCY_REQUIRED"}.issubset(
        {error["error_code"] for error in invalid_response.json()["errors"]}
    )
    assert non_editable.status_code == 403
    assert non_editable.json()["error_code"] == "CARGO_DRAFT_NOT_EDITABLE"


def test_cargo_draft_safe_logging_and_audit_do_not_store_payload(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")
    payload = cargo_payload(cargo_application_type="bad_type")

    try:
        response = client.post("/cargo/applications/draft", json=payload)
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    log_text = "\n".join(handler.messages)
    assert "Sensitive route description" not in log_text
    assert "12500.50" not in log_text
    assert "Sensitive Carrier" not in log_text
    assert "CARGO-SECRET" not in log_text
    assert "Sensitive comment" not in log_text

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            audit_row = session.execute(
                select(audit_logs).where(audit_logs.c.action == "cargo_application_validation_failed")
            ).mappings().one()
            assert audit_row.metadata_json["reason_code"] == "CARGO_APPLICATION_TYPE_INVALID"
            assert "Sensitive route description" not in str(audit_row.metadata_json)
            assert "12500.50" not in str(audit_row.metadata_json)
            assert "Sensitive Carrier" not in str(audit_row.metadata_json)
            assert "CARGO-SECRET" not in str(audit_row.metadata_json)
    finally:
        engine.dispose()


def test_cargo_submit_requires_document_and_uses_cargo_category(monkeypatch, migrated_database: str) -> None:
    seed_users(migrated_database)
    created_payloads: list[dict] = []

    async def fake_create_deal(fields: dict) -> int:
        created_payloads.append(fields)
        return 91019

    from app.routers import cargo_applications

    monkeypatch.setattr(cargo_applications, "create_deal", fake_create_deal)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor@example.com")

    saved = client.post("/cargo/applications/draft", json=cargo_payload())
    app_id = saved.json()["id"]
    missing_docs = client.post(f"/cargo/applications/{app_id}/submit")
    upload = client.post(
        f"/applications/{app_id}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.pdf", b"%PDF-1.4 cargo", "application/pdf")},
    )
    submitted = client.post(f"/cargo/applications/{app_id}/submit")

    assert missing_docs.status_code == 200
    assert missing_docs.json()["status"] == "invalid"
    assert missing_docs.json()["errors"][0]["error_code"] == "DOCUMENT_REQUIRED"
    assert upload.status_code == 200
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "ok"
    assert submitted.json()["bitrix_deal_id"] == 91019
    assert created_payloads[0]["CATEGORY_ID"] == 19

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(portal_applications)).mappings().one()
            assert row.portal_status == "received"
            assert row.bitrix_category_id == 19
            assert row.bitrix_deal_id == 91019
    finally:
        engine.dispose()


def test_cargo_company_eligibility_fails_closed(monkeypatch, migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            user_id = create_user(session, email="blocked@example.com")
            session.execute(
                insert(user_company_roles).values(
                    user_id=user_id,
                    bitrix_company_id=555,
                    role_code="client_executor",
                    access_status="active",
                    bitrix_link_status="confirmed",
                    company_title_cache="Blocked Company",
                    company_country_code_cache="PL",
                )
            )
            session.commit()
    finally:
        engine.dispose()

    client = create_client(monkeypatch, migrated_database)
    login(client, "blocked@example.com")
    response = client.post("/cargo/applications/validate", json=cargo_payload(company_id="555"))

    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    assert response.json()["errors"][-1]["error_code"] == "PORTAL_APPLICATIONS_NOT_ALLOWED"
