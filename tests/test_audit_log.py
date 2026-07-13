from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from app.auth import audit_event, hash_password, now_utc, sanitize_audit_metadata
from app.models import audit_logs, portal_users, user_company_roles


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
    import app.auth as auth_module
    from app.config import get_settings
    from app.main import create_app

    async def redis_factory() -> FakeRedis:
        return FakeRedis()

    monkeypatch.setattr(auth_module, "get_redis_client", redis_factory)
    get_settings.cache_clear()
    return TestClient(create_app())


def create_user(
    database_url: str,
    *,
    email: str,
    role_code: str | None = "client_executor",
    status: str = "active",
    two_factor_enabled: bool = False,
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
                    user_type="client",
                    role_code=role_code,
                    language="ru",
                    two_factor_enabled=two_factor_enabled,
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


def test_sanitizer_redacts_nested_personal_data_and_secrets() -> None:
    payload = {
        "Password": "StrongPass123!",
        "safe_count": 2,
        "nested": {"clientEmail": "client@example.com", "note": "Bearer abc.secret", "items": [{"VIN": "ABC123"}]},
        "message": "External error for test@example.com token=secret-token +995 555 123456",
    }

    sanitized = sanitize_audit_metadata(payload)
    rendered = str(sanitized)

    assert sanitized["Password"] == "[redacted]"
    assert sanitized["safe_count"] == 2
    assert "client@example.com" not in rendered
    assert "secret-token" not in rendered
    assert "StrongPass123" not in rendered
    assert "ABC123" not in rendered
    assert "555 123456" not in rendered


def test_login_logout_and_blocked_login_are_audited_safely(monkeypatch, migrated_database: str) -> None:
    active_id = create_user(migrated_database, email="active-audit@example.com")
    blocked_id = create_user(migrated_database, email="blocked-audit@example.com", status="blocked")
    client = create_client(monkeypatch, migrated_database)

    assert client.post("/auth/login", json={"email": "missing@example.com", "password": "wrong"}).status_code == 401
    login(client, "active-audit@example.com")
    assert client.post("/auth/logout").status_code == 200
    blocked_login = client.post(
        "/auth/login", json={"email": "blocked-audit@example.com", "password": "StrongPass123!"}
    )
    assert blocked_login.status_code == 403

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            rows = session.execute(select(audit_logs).order_by(audit_logs.c.id)).mappings().all()
            actions = [row.action for row in rows]
            assert "login_failed" in actions
            assert "login_succeeded" in actions
            assert "logout_completed" in actions
            assert "login_blocked_user_denied" in actions
            success = next(row for row in rows if row.action == "login_succeeded")
            blocked = next(row for row in rows if row.action == "login_blocked_user_denied")
            assert success.actor_user_id == active_id
            assert blocked.target_user_id == blocked_id
            rendered = str([row.metadata_json for row in rows])
            assert "active-audit@example.com" not in rendered
            assert "blocked-audit@example.com" not in rendered
            assert "missing@example.com" not in rendered
            assert "StrongPass123" not in rendered
    finally:
        engine.dispose()


def test_superadmin_audit_events_filters_detail_and_immutability(monkeypatch, migrated_database: str) -> None:
    admin_id = create_user(migrated_database, email="audit-admin@example.com", role_code="superadmin")
    user_id = create_user(migrated_database, email="audit-user@example.com")
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            audit_event(
                session,
                action="document_download_denied",
                object_type="document",
                object_id="42",
                request=None,
                actor_user_id=user_id,
                target_user_id=user_id,
                bitrix_company_id=700,
                application_id=101,
                metadata={"result": "denied", "reason_code": "DOCUMENT_ACCESS_DENIED", "correlation_id": "corr-audit"},
            )
            audit_event(
                session,
                action="integration_retry_requested",
                object_type="integration_error",
                object_id="5",
                request=None,
                actor_user_id=admin_id,
                metadata={"integration_error_id": 5, "result": "success", "correlation_id": "corr-int"},
            )
            session.commit()
    finally:
        engine.dispose()
    client = create_client(monkeypatch, migrated_database)
    login(client, "audit-user@example.com")
    assert client.get("/superadmin/audit-events").status_code == 403
    client.post("/auth/logout")
    login(client, "audit-admin@example.com")

    filtered = client.get("/superadmin/audit-events?category=document&result=denied&correlation_id=corr-audit")
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["pagination"]["total"] == 1
    event = payload["items"][0]
    assert event["event_type"] == "document_download_denied"
    assert event["category"] == "document"
    assert event["result"] == "denied"
    assert event["application_id"] == "app_101"
    assert event["metadata"]["reason_code"] == "DOCUMENT_ACCESS_DENIED"

    detail = client.get(f"/superadmin/audit-events/{event['id']}")
    assert detail.status_code == 200
    assert detail.json()["event"]["id"] == event["id"]
    patch_response = client.patch(
        f"/superadmin/audit-events/{event['id']}", json={"metadata": {"token": "secret"}}
    )
    assert patch_response.status_code in {404, 405}
    assert client.delete(f"/superadmin/audit-events/{event['id']}").status_code in {404, 405}


def test_role_change_revokes_sessions_and_audit_metadata_is_safe(monkeypatch, migrated_database: str) -> None:
    admin_id = create_user(migrated_database, email="role-admin@example.com", role_code="superadmin")
    user_id = create_user(migrated_database, email="role-user@example.com")
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(
                insert(user_company_roles).values(
                    user_id=user_id,
                    bitrix_company_id=701,
                    role_code="client_executor",
                    access_status="active",
                    bitrix_link_status="confirmed",
                )
            )
            session.commit()
    finally:
        engine.dispose()
    client = create_client(monkeypatch, migrated_database)
    login(client, "role-admin@example.com")

    response = client.patch(
        f"/superadmin/users/usr_{user_id}/roles",
        json={"role_code": "client_admin", "email": "evil@example.com"},
    )

    assert response.status_code == 200
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            rows = session.execute(select(audit_logs).order_by(audit_logs.c.id)).mappings().all()
            actions = [row.action for row in rows]
            assert "user_role_changed" in actions
            assert "all_user_sessions_revoked" in actions
            role_event = next(row for row in rows if row.action == "user_role_changed")
            assert role_event.actor_user_id == admin_id
            assert role_event.target_user_id == user_id
            rendered = str(role_event.metadata_json)
            assert "evil@example.com" not in rendered
            assert "role-user@example.com" not in str([row.metadata_json for row in rows])
    finally:
        engine.dispose()


def test_impersonated_action_contains_actor_effective_and_session(monkeypatch, migrated_database: str) -> None:
    admin_id = create_user(
        migrated_database, email="imp-audit-admin@example.com", role_code="superadmin", two_factor_enabled=True
    )
    target_id = create_user(migrated_database, email="imp-audit-target@example.com")
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(
                insert(user_company_roles).values(
                    user_id=target_id,
                    bitrix_company_id=702,
                    role_code="client_executor",
                    access_status="active",
                    bitrix_link_status="confirmed",
                )
            )
            session.commit()
    finally:
        engine.dispose()
    client = create_client(monkeypatch, migrated_database)
    login(client, "imp-audit-admin@example.com")
    started = client.post(f"/superadmin/users/usr_{target_id}/impersonation", json={"reason": "audit diagnostics"})
    assert started.status_code == 200
    token = started.json()["token"]

    changed = client.post(
        "/auth/change-password",
        headers={"x-impersonation-token": token},
        json={"current_password": "bad", "new_password": "AnotherStrong123"},
    )

    assert changed.status_code == 401
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            row = (
                session.execute(select(audit_logs).where(audit_logs.c.action == "password_change_failed"))
                .mappings()
                .one()
            )
            assert row.actor_user_id == admin_id
            assert row.target_user_id == target_id
            assert row.metadata_json["effective_user_id"] == target_id
            assert row.metadata_json["impersonation_session_id"].startswith("imp_")
            assert row.metadata_json["result"] == "failed"
    finally:
        engine.dispose()


def test_audit_events_date_filter_and_invalid_filter(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, email="date-admin@example.com", role_code="superadmin")
    client = create_client(monkeypatch, migrated_database)
    login(client, "date-admin@example.com")
    future = (now_utc() + timedelta(days=1)).isoformat()

    assert client.get(f"/superadmin/audit-events?date_from={future}").json()["pagination"]["total"] == 0
    assert client.get("/superadmin/audit-events?category=personal_data").status_code == 400
