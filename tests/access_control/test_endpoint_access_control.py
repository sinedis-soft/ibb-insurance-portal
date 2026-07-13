from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.models import audit_logs, document_transfer_logs, portal_applications, portal_policies, user_company_roles
from tests.access_control.helpers import (
    add_application,
    add_company_role,
    add_document,
    add_partner_client_request,
    add_partner_link,
    add_policy,
    create_client,
    create_user,
    login,
)


def auto_payload(*, company_id: str = "6100", product_code: str = "border_oc", extra: dict | None = None) -> dict:
    payload = {
        "company_id": company_id,
        "product_code": product_code,
        "vehicle_registration_country_code": "GE",
        "coverage_country_code": "PL",
        "coverage_zone_code": "EU",
        "vehicle": {
            "plate_number": "SAFE-TEST",
            "vin": "VINACCESSCONTROL123",
            "vehicle_type": "passenger_car",
            "brand_model": "Toyota Corolla",
            "production_year": 2020,
            "engine_volume": 1800,
            "power_kw": 100,
        },
        "period": {"start_date": date.today().isoformat(), "duration_days": 30},
    }
    if extra:
        payload.update(extra)
    return payload


def seed_http_scope(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            executor_a = create_user(session, email="executor-a@example.com", role_code="client_executor")
            executor_a2 = create_user(session, email="executor-a2@example.com", role_code="client_executor")
            executor_b = create_user(session, email="executor-b@example.com", role_code="client_executor")
            admin = create_user(session, email="admin@example.com", role_code="client_admin")
            viewer = create_user(session, email="viewer@example.com", role_code="client_viewer")
            mixed = create_user(session, email="mixed@example.com", role_code="client_admin")
            partner = create_user(session, email="partner@example.com", role_code=None, user_type="partner")
            other_partner = create_user(session, email="other-partner@example.com", role_code=None, user_type="partner")

            add_company_role(session, user_id=executor_a, bitrix_company_id=6100, role_code="client_executor")
            add_company_role(session, user_id=executor_a2, bitrix_company_id=6100, role_code="client_executor")
            add_company_role(session, user_id=executor_b, bitrix_company_id=6200, role_code="client_executor")
            add_company_role(session, user_id=admin, bitrix_company_id=6100, role_code="client_admin")
            add_company_role(session, user_id=viewer, bitrix_company_id=6100, role_code="client_viewer")
            add_company_role(session, user_id=mixed, bitrix_company_id=6100, role_code="client_admin")
            add_company_role(session, user_id=mixed, bitrix_company_id=6200, role_code="client_viewer")
            add_partner_link(session, partner_user_id=partner, bitrix_company_id=6300, status="active")
            add_partner_link(session, partner_user_id=partner, bitrix_company_id=6301, status="another_partner")
            add_partner_link(session, partner_user_id=other_partner, bitrix_company_id=6302, status="active")

            own_app = add_application(
                session, bitrix_company_id=6100, bitrix_deal_id=611000, created_by_user_id=executor_a
            )
            same_company_other_app = add_application(
                session, bitrix_company_id=6100, bitrix_deal_id=611001, created_by_user_id=executor_a2
            )
            foreign_app = add_application(
                session, bitrix_company_id=6200, bitrix_deal_id=621000, created_by_user_id=executor_b
            )
            partner_client_request = add_partner_client_request(
                session, partner_user_id=partner, status="confirmed", confirmed_bitrix_company_id=6300
            )
            partner_app = add_application(
                session,
                bitrix_company_id=6300,
                bitrix_deal_id=631000,
                partner_user_id=partner,
                partner_client_request_id=partner_client_request,
            )
            other_partner_app = add_application(
                session, bitrix_company_id=6302, bitrix_deal_id=631002, partner_user_id=other_partner
            )
            own_doc = add_document(session, application_id=own_app, bitrix_document_id="DOC-OWN")
            foreign_doc = add_document(session, application_id=foreign_app, bitrix_document_id="DOC-FOREIGN")
            policy_doc = add_document(
                session,
                application_id=partner_app,
                bitrix_document_id="POLICY-DOC",
                is_policy_file=True,
                transfer_status="sent",
            )
            own_policy = add_policy(
                session,
                application_id=own_app,
                bitrix_company_id=6100,
                bitrix_deal_id=611000,
                policy_number="POL-OWN-001",
            )
            foreign_policy = add_policy(
                session,
                application_id=foreign_app,
                bitrix_company_id=6200,
                bitrix_deal_id=621000,
                policy_number="POL-FOREIGN-002",
            )
            partner_policy = add_policy(
                session,
                application_id=partner_app,
                bitrix_company_id=6300,
                bitrix_deal_id=631000,
                policy_number="POL-PARTNER-003",
                document_transfer_log_id=policy_doc,
            )
            session.commit()
            return {
                "executor_a": executor_a,
                "own_app": own_app,
                "same_company_other_app": same_company_other_app,
                "foreign_app": foreign_app,
                "partner_app": partner_app,
                "other_partner_app": other_partner_app,
                "own_doc": own_doc,
                "foreign_doc": foreign_doc,
                "policy_doc": policy_doc,
                "own_policy": own_policy,
                "foreign_policy": foreign_policy,
                "partner_policy": partner_policy,
                "partner_client_request": partner_client_request,
            }
    finally:
        engine.dispose()


def ids(items: list[dict]) -> set[str]:
    return {item["id"] for item in items}


def test_company_and_application_http_lists_are_scoped_by_role_and_company(monkeypatch, migrated_database: str) -> None:
    data = seed_http_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)

    login(client, "executor-a@example.com")
    companies = client.get("/me/companies?company_id=6200&include=everything")
    apps_all = client.get("/applications?company_id=6100&include=documents&sort=-created_at&limit=50&offset=0")
    apps_foreign = client.get("/applications?company_id=6200")
    own_detail = client.get(f"/applications/app_{data['own_app']}")
    same_company_other_detail = client.get(f"/applications/app_{data['same_company_other_app']}")
    foreign_detail = client.get(f"/applications/app_{data['foreign_app']}")

    assert companies.status_code == 200
    assert [item["bitrix_company_id"] for item in companies.json()["items"]] == ["6100"]
    assert apps_all.status_code == 200
    assert ids(apps_all.json()["items"]) == {f"app_{data['own_app']}"}
    assert apps_foreign.status_code == 403
    assert own_detail.status_code == 200
    assert same_company_other_detail.status_code == 404
    assert foreign_detail.status_code == 404

    client.post("/auth/logout")
    login(client, "admin@example.com")
    admin_apps = client.get("/applications?company_id=6100&limit=50")
    admin_foreign = client.get("/applications?company_id=6200")
    assert admin_apps.status_code == 200
    assert ids(admin_apps.json()["items"]) == {f"app_{data['own_app']}", f"app_{data['same_company_other_app']}"}
    assert admin_foreign.status_code == 403

    client.post("/auth/logout")
    login(client, "mixed@example.com")
    mixed_admin_actions = client.get(f"/applications/app_{data['own_app']}").json()["available_actions"]
    mixed_viewer_actions = client.get(f"/applications/app_{data['foreign_app']}").json()["available_actions"]
    assert "upload_document" in mixed_admin_actions
    assert "approve" not in mixed_viewer_actions
    assert "submit" not in mixed_viewer_actions


def test_http_application_mutations_reject_mass_assignment_and_foreign_ids(monkeypatch, migrated_database: str) -> None:
    data = seed_http_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor-a@example.com")

    foreign_create = client.post("/auto/applications/draft", json=auto_payload(company_id="6200"))
    forged_create = client.post(
        "/auto/applications/draft",
        json=auto_payload(extra={"role_code": "client_admin", "created_by_user_id": 999, "partner_id": 999}),
    )
    forged_update = client.patch(
        f"/auto/applications/app_{data['own_app']}/draft",
        json=auto_payload(company_id="6200", extra={"application_id": data["foreign_app"], "owner_user_id": 999}),
    )
    upload_foreign = client.post(
        f"/applications/app_{data['foreign_app']}/documents",
        data={"document_type": "vehicle_registration_certificate"},
        files={"file": ("registration.pdf", b"%PDF-1.4 access", "application/pdf")},
    )

    assert foreign_create.status_code == 403
    assert foreign_create.json()["error_code"] == "COMPANY_ACCESS_DENIED"
    assert forged_create.status_code == 200
    assert forged_create.json()["status"] == "ok"
    assert forged_update.status_code == 403
    assert forged_update.json()["error_code"] == "COMPANY_ACCESS_DENIED"
    assert upload_foreign.status_code == 404

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            created = (
                session.execute(
                    select(portal_applications).where(
                        portal_applications.c.id == int(forged_create.json()["id"].removeprefix("app_"))
                    )
                )
                .mappings()
                .one()
            )
            assert created.created_by_user_id == data["executor_a"]
            assert created.bitrix_company_id == 6100
            assert created.partner_user_id is None
            assert created.partner_client_request_id is None
    finally:
        engine.dispose()


def test_policy_and_document_http_responses_do_not_leak_foreign_or_partner_policy_file_data(
    monkeypatch, migrated_database: str
) -> None:
    data = seed_http_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)

    login(client, "executor-a@example.com")
    policies_own = client.get("/policies?company_id=6100&q=POL&limit=50&offset=0&include=documents")
    policies_foreign_filter = client.get("/policies?company_id=6200&q=POL-FOREIGN-002")
    policy_detail_own = client.get(f"/policies/policy_{data['own_policy']}")
    policy_detail_foreign = client.get(f"/policies/policy_{data['foreign_policy']}")
    documents_own = client.get(f"/applications/app_{data['own_app']}/documents?application_id={data['foreign_app']}")
    documents_foreign = client.get(f"/applications/app_{data['foreign_app']}/documents")
    direct_foreign_doc = client.get(f"/documents/doc_{data['foreign_doc']}/download")

    assert policies_own.status_code == 200
    assert ids(policies_own.json()["items"]) == {f"policy_{data['own_policy']}"}
    assert policies_own.json()["items"][0]["premium_amount"] == "1200.50"
    assert policies_own.json()["items"][0]["premium_currency"] == "USD"
    assert policies_foreign_filter.status_code == 403
    assert policy_detail_own.status_code == 200
    assert policy_detail_own.json()["policy_number"] == "POL-OWN-001"
    assert policy_detail_own.json()["valid_to"] is not None
    assert policy_detail_foreign.status_code == 404
    assert documents_own.status_code == 200
    assert ids(documents_own.json()["items"]) == {f"doc_{data['own_doc']}"}
    assert all("storage_key" not in item and "bitrix_file_id" not in item for item in documents_own.json()["items"])
    assert documents_foreign.status_code == 404
    assert direct_foreign_doc.status_code == 404

    client.post("/auth/logout")
    login(client, "partner@example.com")
    partner_policy_file = client.get(f"/documents/doc_{data['policy_doc']}/download")
    partner_application_docs = client.get(f"/applications/app_{data['partner_app']}/documents")
    partner_client_list = client.get("/partner/clients?partner_id=999&partner_client_id=999&include=applications")
    partner_app_list = client.get("/applications?company_id=6300")
    partner_policy_list = client.get("/policies?company_id=6300")

    assert partner_policy_file.status_code == 404
    assert "B24-FILE-SECRET" not in partner_policy_file.text
    assert "storage_key" not in partner_policy_file.text
    assert partner_application_docs.status_code == 200
    assert partner_application_docs.json()["items"] == []
    assert partner_client_list.status_code == 200
    assert ids(partner_client_list.json()["items"]) == {f"pcr_{data['partner_client_request']}"}
    assert partner_app_list.json()["items"] == []
    assert partner_policy_list.json()["items"] == []


def test_security_sensitive_denials_are_audited_but_masked_reads_are_not(monkeypatch, migrated_database: str) -> None:
    data = seed_http_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor-a@example.com")

    masked_foreign_read = client.get(f"/applications/app_{data['foreign_app']}")
    denied_admin_action = client.post(
        f"/admin/users/usr_{data['executor_a']}/company-roles",
        json={"bitrix_company_id": 6100, "role_code": "client_admin"},
    )
    protected_document = client.get(f"/documents/doc_{data['foreign_doc']}/download")

    assert masked_foreign_read.status_code == 404
    assert denied_admin_action.status_code == 403
    assert protected_document.status_code == 404

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = list(session.execute(select(audit_logs.c.action)).scalars())
            assert "application_access_denied" not in actions
            assert "document_download_denied" in actions
            assert "company_access_denied" not in actions
    finally:
        engine.dispose()


def test_blocking_role_change_and_company_link_revocation_stop_http_access(monkeypatch, migrated_database: str) -> None:
    data = seed_http_scope(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "mixed@example.com")
    assert client.get(f"/applications/app_{data['own_app']}").status_code == 200
    before_role_change_actions = client.get(f"/applications/app_{data['foreign_app']}").json()["available_actions"]
    assert "upload_document" not in before_role_change_actions

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(
                update(user_company_roles)
                .where(user_company_roles.c.bitrix_company_id == 6100)
                .values(access_status="revoked")
            )
            session.commit()
    finally:
        engine.dispose()
    assert client.get(f"/applications/app_{data['own_app']}").status_code == 404

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(update(portal_applications).where(portal_applications.c.id == data["foreign_app"]).values())
            session.execute(
                update(user_company_roles)
                .where(user_company_roles.c.bitrix_company_id == 6200)
                .values(role_code="client_admin")
            )
            session.commit()
    finally:
        engine.dispose()
    assert "upload_document" in client.get(f"/applications/app_{data['foreign_app']}").json()["available_actions"]

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(update(portal_applications).where(portal_applications.c.id == data["foreign_app"]).values())
            from app.models import portal_users

            session.execute(
                update(portal_users).where(portal_users.c.email == "mixed@example.com").values(status="blocked")
            )
            session.commit()
    finally:
        engine.dispose()
    assert client.get("/me/companies").status_code == 401


def test_repeated_submit_is_idempotent_through_http(monkeypatch, migrated_database: str) -> None:
    seed_http_scope(migrated_database)
    created_payloads: list[dict] = []

    async def fake_create_deal(fields: dict) -> int:
        created_payloads.append(fields)
        return 99001

    from app.routers import auto_applications

    monkeypatch.setattr(auto_applications, "create_deal", fake_create_deal)
    client = create_client(monkeypatch, migrated_database)
    login(client, "executor-a@example.com")
    saved = client.post("/auto/applications/draft", json=auto_payload())
    assert saved.status_code == 200
    assert saved.json()["status"] == "ok"
    app_id = saved.json()["id"]
    upload = client.post(
        f"/applications/{app_id}/documents",
        data={"document_type": "vehicle_registration_certificate"},
        files={"file": ("registration.pdf", b"%PDF-1.4 access", "application/pdf")},
    )
    first_submit = client.post(f"/auto/applications/{app_id}/submit")
    second_submit = client.post(f"/auto/applications/{app_id}/submit")

    assert upload.status_code == 200
    assert first_submit.status_code == 200
    assert second_submit.status_code == 200
    assert first_submit.json()["bitrix_deal_id"] == 99001
    assert second_submit.json()["bitrix_deal_id"] == 99001
    assert len(created_payloads) == 1

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            deal_id = session.execute(
                select(portal_applications.c.bitrix_deal_id).where(
                    portal_applications.c.id == int(app_id.removeprefix("app_"))
                )
            ).scalar_one()
            assert deal_id == 99001
            assert len(session.execute(select(document_transfer_logs)).mappings().all()) >= 1
            assert len(session.execute(select(portal_policies)).mappings().all()) == 3
    finally:
        engine.dispose()
