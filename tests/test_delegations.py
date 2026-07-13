from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.orm import Session

from app.auth import hash_password, now_utc
from app.models import (
    application_delegation_items,
    application_delegations,
    audit_logs,
    portal_applications,
    portal_users,
    user_company_roles,
)


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


def login(client: TestClient, email: str) -> None:
    response = client.post("/auth/login", json={"email": email, "password": "StrongPass123!"})
    assert response.status_code == 200


def create_user(session: Session, email: str, role_code: str = "client_executor", status: str = "active") -> int:
    return session.execute(
        insert(portal_users)
        .values(
            email=email,
            password_hash=hash_password("StrongPass123!"),
            status=status,
            user_type="client",
            role_code=role_code,
            language="ru",
        )
        .returning(portal_users.c.id)
    ).scalar_one()


def add_role(
    session: Session, user_id: int, company_id: int, role_code: str = "client_executor", status: str = "active"
) -> None:
    session.execute(
        insert(user_company_roles).values(
            user_id=user_id,
            bitrix_company_id=company_id,
            role_code=role_code,
            access_status=status,
            bitrix_link_status="confirmed",
        )
    )


def add_app(session: Session, *, user_id: int, company_id: int, deal_id: int, status: str = "received") -> int:
    return session.execute(
        insert(portal_applications)
        .values(
            application_type="auto",
            bitrix_deal_id=deal_id,
            bitrix_company_id=company_id,
            portal_status=status,
            bitrix_category_id=0,
            bitrix_stage_id="NEW",
            product_type_code="green_card_ge",
            title_cache=f"App {deal_id}",
            created_by_user_id=user_id,
            assigned_to_user_id=user_id,
        )
        .returning(portal_applications.c.id)
    ).scalar_one()


def seed(database_url: str):
    engine = create_engine(database_url)
    with Session(engine) as session:
        delegator = create_user(session, "delegator@example.com")
        delegate = create_user(session, "delegate@example.com")
        other = create_user(session, "other@example.com")
        viewer = create_user(session, "viewer@example.com", role_code="client_viewer")
        admin = create_user(session, "admin-deleg@example.com", role_code="client_admin")
        superadmin = create_user(session, "super-deleg@example.com", role_code="superadmin")
        for user_id, role in [
            (delegator, "client_executor"),
            (delegate, "client_executor"),
            (viewer, "client_viewer"),
            (admin, "client_admin"),
        ]:
            add_role(session, user_id, 300, role)
        add_role(session, other, 301)
        app1 = add_app(session, user_id=delegator, company_id=300, deal_id=91001)
        app2 = add_app(session, user_id=delegator, company_id=300, deal_id=91002)
        other_app = add_app(session, user_id=other, company_id=301, deal_id=91003)
        session.commit()
    engine.dispose()
    return {
        "delegator": delegator,
        "delegate": delegate,
        "other": other,
        "viewer": viewer,
        "admin": admin,
        "superadmin": superadmin,
        "app1": app1,
        "app2": app2,
        "other_app": other_app,
    }


def test_delegate_gets_only_selected_active_applications_and_cancel_revokes(
    monkeypatch, migrated_database: str
) -> None:
    ids = seed(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "delegator@example.com")
    now = now_utc()
    created = client.post(
        "/delegations",
        json={
            "company_id": 300,
            "delegate_user_id": f"usr_{ids['delegate']}",
            "application_ids": [f"app_{ids['app1']}"],
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
            "reason": "vacation",
            "idempotency_key": "one",
        },
    )
    assert created.status_code == 201, created.text
    delegation_id = created.json()["delegation"]["id"]
    assert created.json()["delegation"]["status"] == "active"
    client.post("/auth/logout")
    login(client, "delegate@example.com")
    assert client.get(f"/applications/app_{ids['app1']}").status_code == 200
    assert client.get(f"/applications/app_{ids['app2']}").status_code == 404
    listing = client.get("/applications")
    assert [item["id"] for item in listing.json()["items"]] == [f"app_{ids['app1']}"]
    client.post("/auth/logout")
    login(client, "delegator@example.com")
    cancelled = client.post(f"/delegations/{delegation_id}/cancel", json={"reason": "back"})
    assert cancelled.status_code == 200
    client.post("/auth/logout")
    login(client, "delegate@example.com")
    assert client.get(f"/applications/app_{ids['app1']}").status_code == 404


def test_scheduled_worker_activation_and_expiration_are_idempotent(monkeypatch, migrated_database: str) -> None:
    ids = seed(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "delegator@example.com")
    now = now_utc()
    created = client.post(
        "/delegations",
        json={
            "company_id": 300,
            "delegate_user_id": f"usr_{ids['delegate']}",
            "application_ids": [f"app_{ids['app1']}", f"app_{ids['app2']}"],
            "starts_at": (now + timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=2)).isoformat(),
            "reason": "planned",
            "idempotency_key": "planned",
        },
    )
    assert created.status_code == 201
    delegation_id = created.json()["delegation"]["id"]
    assert created.json()["delegation"]["status"] == "scheduled"
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        session.execute(
            update(application_delegations).values(
                starts_at=now - timedelta(minutes=1), ends_at=now + timedelta(minutes=5)
            )
        )
        session.commit()
    engine.dispose()
    client.post("/auth/logout")
    login(client, "super-deleg@example.com")
    assert client.post("/delegations/run-worker").json()["activated"] == 1
    assert client.post("/delegations/run-worker").json()["activated"] == 0
    client.post("/auth/logout")
    login(client, "delegate@example.com")
    assert client.get(f"/applications/app_{ids['app2']}").status_code == 200
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        parsed = int(delegation_id.removeprefix("dlg_"))
        session.execute(
            update(application_delegations)
            .where(application_delegations.c.id == parsed)
            .values(starts_at=now - timedelta(minutes=10), ends_at=now - timedelta(minutes=1))
        )
        session.commit()
    engine.dispose()
    client.post("/auth/logout")
    login(client, "super-deleg@example.com")
    assert client.post("/delegations/run-worker").json()["expired"] == 1
    assert client.post("/delegations/run-worker").json()["expired"] == 0
    client.post("/auth/logout")
    login(client, "delegate@example.com")
    assert client.get(f"/applications/app_{ids['app2']}").status_code == 404


def test_negative_validation_and_list_access_filtering(monkeypatch, migrated_database: str) -> None:
    ids = seed(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    now = now_utc()
    login(client, "delegator@example.com")
    viewer = client.post(
        "/delegations",
        json={
            "company_id": 300,
            "delegate_user_id": f"usr_{ids['viewer']}",
            "application_ids": [f"app_{ids['app1']}"],
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
            "reason": "bad",
        },
    )
    assert viewer.status_code == 409
    same_user = client.post(
        "/delegations",
        json={
            "company_id": 300,
            "delegate_user_id": f"usr_{ids['delegator']}",
            "application_ids": [f"app_{ids['app1']}"],
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
            "reason": "bad",
        },
    )
    assert same_user.status_code == 409
    too_long = client.post(
        "/delegations",
        json={
            "company_id": 300,
            "delegate_user_id": f"usr_{ids['delegate']}",
            "application_ids": [f"app_{ids['app1']}"],
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=31)).isoformat(),
            "reason": "bad",
        },
    )
    assert too_long.status_code == 409
    ok = client.post(
        "/delegations",
        json={
            "company_id": 300,
            "delegate_user_id": f"usr_{ids['delegate']}",
            "application_ids": [f"app_{ids['app1']}"],
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
            "reason": "ok",
        },
    )
    assert ok.status_code == 201
    conflict = client.post(
        "/delegations",
        json={
            "company_id": 300,
            "delegate_user_id": f"usr_{ids['delegate']}",
            "application_ids": [f"app_{ids['app1']}"],
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
            "reason": "duplicate",
        },
    )
    assert conflict.status_code == 409
    client.post("/auth/logout")
    login(client, "other@example.com")
    assert client.get("/delegations").json()["pagination"]["total"] == 0
    assert client.get(f"/delegations/{ok.json()['delegation']['id']}").status_code == 404
    client.post("/auth/logout")
    login(client, "admin-deleg@example.com")
    assert client.get("/delegations").json()["pagination"]["total"] == 1


def test_blocking_delegate_terminates_active_delegation(monkeypatch, migrated_database: str) -> None:
    ids = seed(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login(client, "delegator@example.com")
    now = now_utc()
    created = client.post(
        "/delegations",
        json={
            "company_id": 300,
            "delegate_user_id": f"usr_{ids['delegate']}",
            "application_ids": [f"app_{ids['app1']}"],
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=1)).isoformat(),
            "reason": "active",
        },
    )
    assert created.status_code == 201
    client.post("/auth/logout")
    login(client, "super-deleg@example.com")
    blocked = client.post(f"/superadmin/users/usr_{ids['delegate']}/block", json={"reason": "blocked delegate"})
    assert blocked.status_code == 200
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        statuses = set(session.execute(select(application_delegations.c.status)).scalars())
        actions = set(session.execute(select(audit_logs.c.action)).scalars())
        item_statuses = set(session.execute(select(application_delegation_items.c.status)).scalars())
    engine.dispose()
    assert statuses == {"terminated"}
    assert item_statuses == {"terminated"}
    assert "delegation_terminated" in actions
    assert "delegation_access_revoked" in actions
