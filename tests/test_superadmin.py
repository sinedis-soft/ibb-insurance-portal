from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import audit_logs, integration_errors, portal_users, user_company_roles


class FakeRedis:
    async def incr(self, _key: str) -> int:
        return 1

    async def expire(self, _key: str, _ttl: int) -> None:
        return None

    async def get(self, _key: str) -> None:
        return None

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
    database_url: str,
    *,
    email: str,
    role_code: str | None = "client_executor",
    user_type: str = "client",
    status: str = "active",
    bitrix_contact_id: int | None = None,
) -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user_id = session.execute(
                insert(portal_users)
                .values(
                    email=email,
                    password_hash=hash_password("StrongPass123!"),
                    status=status,
                    user_type=user_type,
                    role_code=role_code,
                    language="ru",
                    bitrix_contact_id=bitrix_contact_id,
                    display_name_cache="Portal User",
                )
                .returning(portal_users.c.id)
            ).scalar_one()
            session.commit()
            return user_id
    finally:
        engine.dispose()


def login(client: TestClient, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200


def add_company_link(database_url: str, *, user_id: int, company_id: int = 700) -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            link_id = session.execute(
                insert(user_company_roles)
                .values(
                    user_id=user_id,
                    bitrix_company_id=company_id,
                    role_code="client_executor",
                    access_status="active",
                    bitrix_link_status="confirmed",
                    company_title_cache="Linked Company",
                )
                .returning(user_company_roles.c.id)
            ).scalar_one()
            session.commit()
            return link_id
    finally:
        engine.dispose()


def add_integration_error(database_url: str, *, object_id: int, safe_message: str = "BITRIX24_ACCESS_DENIED") -> int:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            error_id = session.execute(
                insert(integration_errors)
                .values(
                    object_type="user",
                    object_id=str(object_id),
                    bitrix_entity_type="contact",
                    bitrix_entity_id=9001,
                    operation="sync",
                    status="failed",
                    error_code="BITRIX24_ACCESS_DENIED",
                    safe_message=safe_message,
                    retry_count=2,
                )
                .returning(integration_errors.c.id)
            ).scalar_one()
            session.commit()
            return error_id
    finally:
        engine.dispose()


def test_superadmin_can_list_and_filter_users(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com", role_code="client_executor")
    create_user(migrated_database, email="partner@example.com", role_code=None, user_type="partner")
    add_company_link(migrated_database, user_id=client_id, company_id=700)
    add_integration_error(migrated_database, object_id=client_id)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    all_users = client.get("/superadmin/users")
    role_filtered = client.get("/superadmin/users?role=client_executor")
    company_filtered = client.get("/superadmin/users?company_id=700")
    error_filtered = client.get("/superadmin/users?has_integration_errors=true")

    assert all_users.status_code == 200
    assert len(all_users.json()["items"]) == 3
    assert [item["email"] for item in role_filtered.json()["items"]] == ["client@example.com"]
    assert [item["id"] for item in company_filtered.json()["items"]] == [f"usr_{client_id}"]
    assert [item["id"] for item in error_filtered.json()["items"]] == [f"usr_{client_id}"]


def test_non_superadmin_cannot_open_superadmin_users(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="client@example.com", role_code="client_admin")
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    response = client.get("/superadmin/users")

    assert response.status_code == 403
    assert response.json()["error_code"] == "SUPERADMIN_REQUIRED"


def test_superadmin_can_open_user_card(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com", bitrix_contact_id=777)
    add_company_link(migrated_database, user_id=client_id)
    add_integration_error(migrated_database, object_id=client_id)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    response = client.get(f"/superadmin/users/usr_{client_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["bitrix_contact_id"] == 777
    assert payload["company_links"][0]["bitrix_company_id"] == "700"
    assert payload["integration_errors"][0]["error_code"] == "BITRIX24_ACCESS_DENIED"


def test_superadmin_assigns_and_revokes_role_with_audit(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com", role_code="client_executor")
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    assigned = client.patch(f"/superadmin/users/usr_{client_id}/roles", json={"role_code": "client_admin"})
    revoked = client.patch(f"/superadmin/users/usr_{client_id}/roles", json={"role_code": None})

    assert assigned.status_code == 200
    assert assigned.json()["user"]["role_code"] == "client_admin"
    assert revoked.status_code == 200
    assert revoked.json()["user"]["role_code"] is None

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = session.execute(select(audit_logs.c.action).order_by(audit_logs.c.id)).scalars().all()
            assert "user_role_changed" in actions
            assert "user_role_revoked" in actions
    finally:
        engine.dispose()


def test_superadmin_cannot_remove_last_superadmin(monkeypatch, migrated_database: str) -> None:
    admin_id = create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    response = client.patch(f"/superadmin/users/usr_{admin_id}/roles", json={"role_code": "client_admin"})

    assert response.status_code == 403
    assert response.json()["error_code"] == "LAST_SUPERADMIN_REQUIRED"


def test_superadmin_assigns_and_revokes_company_link(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com", role_code="client_executor")
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    assigned = client.post(
        f"/superadmin/users/usr_{client_id}/company-links",
        json={
            "bitrix_company_id": "701",
            "role_code": "client_executor",
            "company_title": "Safe Cache",
            "company_country_code": "GE",
        },
    )
    link_id = assigned.json()["company_link"]["id"]
    revoked = client.delete(f"/superadmin/users/usr_{client_id}/company-links/{link_id}")

    assert assigned.status_code == 201
    assert assigned.json()["company_link"]["access_status"] == "active"
    assert revoked.status_code == 200

    client.post("/auth/logout")
    login(client, "client@example.com")
    assert client.get("/me/companies").json() == {"items": []}

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = session.execute(select(user_company_roles)).mappings().one()
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert row.access_status == "revoked"
            assert "user_company_link_added" in actions
            assert "user_company_link_removed" in actions
    finally:
        engine.dispose()


def test_superadmin_updates_bitrix_contact_id_and_audits(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com", bitrix_contact_id=111)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin@example.com")

    response = client.patch(f"/superadmin/users/usr_{client_id}/bitrix-links", json={"bitrix_contact_id": 222})

    assert response.status_code == 200
    assert response.json()["user"]["bitrix_contact_id"] == 222
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            audit = (
                session.execute(select(audit_logs).where(audit_logs.c.action == "bitrix_contact_link_changed"))
                .mappings()
                .one()
            )
            assert audit.metadata_json["old_bitrix_contact_id"] == 111
            assert audit.metadata_json["new_bitrix_contact_id"] == 222
    finally:
        engine.dispose()


def test_non_superadmin_cannot_update_bitrix_links(monkeypatch, migrated_database: str) -> None:
    client_id = create_user(migrated_database, email="client@example.com", role_code="client_admin")
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")

    response = client.patch(f"/superadmin/users/usr_{client_id}/bitrix-links", json={"bitrix_contact_id": 222})

    assert response.status_code == 403


def test_integration_errors_are_superadmin_only_safe_and_resolvable(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client@example.com", role_code="client_admin")
    error_id = add_integration_error(
        migrated_database,
        object_id=client_id,
        safe_message="Token hidden. Raw payload removed.",
    )
    client = create_client(monkeypatch, migrated_database)
    login(client, "client@example.com")
    denied = client.get("/superadmin/integration-errors")

    client.post("/auth/logout")
    login(client, "admin@example.com")
    listed = client.get("/superadmin/integration-errors?status=failed&object_type=user")
    detail = client.get(f"/superadmin/integration-errors/err_{error_id}")
    resolved = client.post(f"/superadmin/integration-errors/err_{error_id}/mark-resolved")

    assert denied.status_code == 403
    assert listed.status_code == 200
    assert listed.json()["items"][0]["safe_message"] == "Token hidden. Raw payload removed."
    assert "raw_payload" not in str(listed.json()).lower()
    assert "secret" not in str(listed.json()).lower()
    assert detail.status_code == 200
    assert resolved.status_code == 200

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            error = session.execute(select(integration_errors)).mappings().one()
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert error.status == "resolved"
            assert "integration_error_status_changed" in actions
    finally:
        engine.dispose()


def add_application(database_url: str, *, user_id: int, company_id: int = 700, status: str = "in_work") -> int:
    from app.models import portal_applications

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            app_id = session.execute(
                insert(portal_applications)
                .values(
                    application_type="auto",
                    bitrix_company_id=company_id,
                    portal_status=status,
                    created_by_user_id=user_id,
                    assigned_to_user_id=user_id,
                    assignment_status="assigned",
                )
                .returning(portal_applications.c.id)
            ).scalar_one()
            session.commit()
            return app_id
    finally:
        engine.dispose()


def test_superadmin_creates_user_blocks_unblocks_and_revokes_sessions(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin2@example.com", role_code="superadmin")
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin2@example.com")

    created = client.post(
        "/superadmin/users",
        json={
            "email": "new-user@example.com",
            "display_name": "New User",
            "role_code": "client_executor",
            "company_links": [{"bitrix_company_id": 900, "role_code": "client_executor"}],
        },
    )
    user_id = created.json()["user"]["id"]
    block = client.post(f"/superadmin/users/{user_id}/block", json={"reason": "security offboarding"})
    unblock = client.post(f"/superadmin/users/{user_id}/unblock", json={"reason": "access restored"})

    assert created.status_code == 201
    assert block.status_code == 200
    assert unblock.status_code == 200
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert {"user_created", "user_blocked", "user_unblocked"}.issubset(actions)
    finally:
        engine.dispose()


def test_blocking_user_with_active_applications_requires_atomic_reassignment(
    monkeypatch, migrated_database: str
) -> None:
    create_user(migrated_database, email="admin3@example.com", role_code="superadmin")
    specialist_id = create_user(migrated_database, email="specialist@example.com", role_code="client_executor")
    assignee_id = create_user(migrated_database, email="assignee@example.com", role_code="client_executor")
    add_company_link(migrated_database, user_id=specialist_id, company_id=700)
    add_company_link(migrated_database, user_id=assignee_id, company_id=700)
    app_id = add_application(migrated_database, user_id=specialist_id, company_id=700)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin3@example.com")

    denied = client.post(f"/superadmin/users/usr_{specialist_id}/block", json={"reason": "left company"})
    assigned = client.post(
        f"/superadmin/users/usr_{specialist_id}/block",
        json={
            "reason": "left company",
            "reassignment_action": "assign_to_user",
            "new_responsible_user_id": f"usr_{assignee_id}",
            "reassignment_reason": "handover",
        },
    )

    assert denied.status_code == 400
    assert denied.json()["error_code"] == "REASSIGNMENT_REQUIRED"
    assert assigned.status_code == 200
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            from app.models import portal_applications

            app = (
                session.execute(select(portal_applications).where(portal_applications.c.id == app_id)).mappings().one()
            )
            user = session.execute(select(portal_users).where(portal_users.c.id == specialist_id)).mappings().one()
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert app.assigned_to_user_id == assignee_id
            assert app.reassigned_from_user_id == specialist_id
            assert user.status == "blocked"
            assert "active_applications_reassigned" in actions
    finally:
        engine.dispose()


def test_impersonation_requires_2fa_reason_and_audits(monkeypatch, migrated_database: str) -> None:
    admin_id = create_user(migrated_database, email="admin4@example.com", role_code="superadmin")
    target_id = create_user(migrated_database, email="target@example.com", role_code="client_executor")
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(update(portal_users).where(portal_users.c.id == admin_id).values(two_factor_enabled=True))
            session.commit()
    finally:
        engine.dispose()
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin4@example.com")

    started = client.post(
        f"/superadmin/users/usr_{target_id}/impersonation", json={"reason": "diagnose user access issue"}
    )
    ended = client.post(
        f"/superadmin/impersonation/{started.json()['impersonation_session_id']}/end", json={"end_reason": "manual"}
    )

    assert started.status_code == 200
    assert ended.status_code == 200
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert "superadmin_impersonation_started" in actions
            assert "superadmin_impersonation_ended" in actions
    finally:
        engine.dispose()


def test_audit_log_superadmin_only_and_integration_retry_idempotent(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin5@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client5@example.com", role_code="client_admin")
    err_id = add_integration_error(migrated_database, object_id=client_id)
    client = create_client(monkeypatch, migrated_database)
    login(client, "client5@example.com")
    denied = client.get("/superadmin/audit-log")
    client.post("/auth/logout")
    login(client, "admin5@example.com")
    retried = client.post(f"/superadmin/integration-errors/err_{err_id}/retry")
    audit = client.get("/superadmin/audit-log?action=integration_retry_requested")

    assert denied.status_code == 403
    assert retried.status_code == 200
    assert audit.status_code == 200
    assert len(audit.json()["items"]) == 1


def test_superadmin_user_list_pagination_search_sort_and_safe_card(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin6@example.com", role_code="superadmin")
    alpha_id = create_user(migrated_database, email="alpha@example.com", role_code="client_executor")
    beta_id = create_user(migrated_database, email="beta@example.com", role_code="client_viewer")
    add_company_link(migrated_database, user_id=alpha_id, company_id=910)
    add_company_link(migrated_database, user_id=beta_id, company_id=911)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin6@example.com")

    listed = client.get("/superadmin/users?email=alpha&page=1&page_size=1&sort_by=created_at&sort_dir=asc")
    card = client.get(f"/superadmin/users/usr_{alpha_id}")

    assert listed.status_code == 200
    assert listed.json()["pagination"]["total"] == 1
    assert listed.json()["items"][0]["email"] == "alpha@example.com"
    assert card.status_code == 200
    card_text = str(card.json()).lower()
    assert "password_hash" not in card_text
    assert "refresh_token" not in card_text
    assert "first-login" not in card_text


def test_bitrix_contact_and_company_links_verify_conflicts_and_audit(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin7@example.com", role_code="superadmin")
    user_id = create_user(migrated_database, email="linked@example.com", role_code="client_executor")
    other_id = create_user(
        migrated_database, email="other-linked@example.com", role_code="client_executor", bitrix_contact_id=777
    )
    link_id = add_company_link(migrated_database, user_id=user_id, company_id=920)
    add_company_link(migrated_database, user_id=other_id, company_id=921)
    import app.routers.superadmin as superadmin_module

    monkeypatch.setattr(superadmin_module, "verify_bitrix_link", lambda entity_type, entity_id: "linked")
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin7@example.com")

    conflict = client.patch(f"/superadmin/users/usr_{user_id}/bitrix-links", json={"bitrix_contact_id": 777})
    updated = client.patch(f"/superadmin/users/usr_{user_id}/bitrix-links", json={"bitrix_contact_id": 778})
    verified = client.post(f"/superadmin/users/usr_{user_id}/bitrix-links/verify-contact")
    company = client.patch(
        f"/superadmin/users/usr_{user_id}/company-links/ucr_{link_id}/bitrix-company",
        json={"bitrix_company_id": 922},
    )
    company_verify = client.post(f"/superadmin/users/usr_{user_id}/company-links/ucr_{link_id}/verify-bitrix-company")

    assert conflict.status_code == 409
    assert updated.status_code == 200
    assert updated.json()["user"]["bitrix_contact_link_status"] == "linked"
    assert verified.json()["verification_status"] == "linked"
    assert company.status_code == 200
    assert company.json()["company_link"]["bitrix_link_status"] == "linked"
    assert company_verify.json()["verification_status"] == "linked"
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            assert "bitrix_contact_link_created" in actions
            assert "bitrix_contact_link_verified" in actions
            assert "bitrix_company_link_changed" in actions
            assert "bitrix_company_link_verified" in actions
    finally:
        engine.dispose()


def test_integration_error_detail_retry_safety_and_filters(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="admin8@example.com", role_code="superadmin")
    client_id = create_user(migrated_database, email="client8@example.com", role_code="client_executor")
    err_id = add_integration_error(migrated_database, object_id=client_id)
    client = create_client(monkeypatch, migrated_database)
    login(client, "admin8@example.com")

    listed = client.get("/superadmin/integration-errors?status=requires_attention&object_type=user&page=1&page_size=1")
    detail = client.get(f"/superadmin/integration-errors/err_{err_id}")
    retried = client.post(f"/superadmin/integration-errors/err_{err_id}/retry")
    retried_again = client.post(f"/superadmin/integration-errors/err_{err_id}/retry")

    assert listed.status_code == 200
    assert listed.json()["pagination"]["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["error"]["retry_supported"] is True
    assert "secret" not in str(detail.json()).lower()
    assert retried.status_code == 200
    assert retried_again.status_code == 200
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            error = session.execute(select(integration_errors)).mappings().one()
            actions = list(session.execute(select(audit_logs.c.action)).scalars())
            assert error.retry_count == 3
            assert actions.count("integration_retry_requested") == 1
    finally:
        engine.dispose()
