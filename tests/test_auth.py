from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.auth import hash_password, hash_refresh_token, now_utc
from app.models import audit_logs, portal_users, user_sessions


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


def create_client(monkeypatch, migrated_database: str, fake_redis: FakeRedis | None = None) -> TestClient:
    from app.config import get_settings
    from app.main import create_app

    if fake_redis is None:
        fake_redis = FakeRedis()

    async def redis_factory() -> FakeRedis:
        return fake_redis

    import app.auth as auth_module

    monkeypatch.setattr(auth_module, "get_redis_client", redis_factory)
    get_settings.cache_clear()
    return TestClient(create_app())


def create_user(
    database_url: str,
    *,
    email: str = "user@example.com",
    password: str = "StrongPass123!",
    status: str = "active",
) -> int:
    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            user_id = session.execute(
                insert(portal_users)
                .values(
                    email=email,
                    password_hash=hash_password(password),
                    status=status,
                    role_code="client_executor",
                    language="ru",
                    bitrix_contact_id=12345,
                )
                .returning(portal_users.c.id)
            ).scalar_one()
            session.commit()
            return user_id
    finally:
        engine.dispose()


def test_login_me_refresh_and_logout(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database)
    client = create_client(monkeypatch, migrated_database)

    login_response = client.post("/auth/login", json={"email": "USER@example.com", "password": "StrongPass123!"})

    assert login_response.status_code == 200
    assert login_response.json() == {
        "user": {
            "id": "usr_1",
            "role": "client_executor",
            "language": "ru",
            "status": "active",
        }
    }
    assert "ibb_access_token" in login_response.cookies
    assert "ibb_refresh_token" in login_response.cookies
    assert "ibb_access_token" not in login_response.text
    assert "ibb_refresh_token" not in login_response.text

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "client_executor"
    assert "email" not in me_response.json()

    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json() == {"status": "ok"}

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json() == {"status": "ok"}
    assert client.get("/auth/me").status_code == 401


def test_login_invalid_and_unknown_email_return_same_error(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database)
    client = create_client(monkeypatch, migrated_database)

    invalid_password = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong"})
    unknown_email = client.post("/auth/login", json={"email": "missing@example.com", "password": "wrong"})

    assert invalid_password.status_code == 401
    assert unknown_email.status_code == 401
    assert invalid_password.json() == unknown_email.json() == {
        "error_code": "INVALID_CREDENTIALS",
        "message": "Неверный email или пароль",
    }


def test_blocked_user_cannot_login(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database, status="blocked")
    client = create_client(monkeypatch, migrated_database)

    response = client.post("/auth/login", json={"email": "user@example.com", "password": "StrongPass123!"})

    assert response.status_code == 403
    assert response.json()["error_code"] == "USER_BLOCKED"


def test_refresh_rejects_revoked_session(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    login_response = client.post("/auth/login", json={"email": "user@example.com", "password": "StrongPass123!"})
    assert login_response.status_code == 200

    from sqlalchemy import create_engine

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(update(user_sessions).values(revoked_at=now_utc()))
            session.commit()
    finally:
        engine.dispose()

    response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error_code"] == "SESSION_EXPIRED"


def test_rate_limit_uses_hashed_email_and_returns_429(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database)
    fake_redis = FakeRedis()
    client = create_client(monkeypatch, migrated_database, fake_redis)

    for _ in range(5):
        assert client.post("/auth/login", json={"email": "user@example.com", "password": "wrong"}).status_code == 401
    response = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong"})

    assert response.status_code == 429
    assert response.json()["error_code"] == "TOO_MANY_LOGIN_ATTEMPTS"
    assert all("user@example.com" not in key for key in fake_redis.values)


def test_refresh_token_is_stored_only_as_hash(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database)
    client = create_client(monkeypatch, migrated_database)
    response = client.post("/auth/login", json={"email": "user@example.com", "password": "StrongPass123!"})
    refresh_cookie = response.cookies["ibb_refresh_token"]

    from sqlalchemy import create_engine

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            stored_hash = session.execute(select(user_sessions.c.refresh_token_hash)).scalar_one()
            assert stored_hash != refresh_cookie
            assert stored_hash == hash_refresh_token(refresh_cookie)
    finally:
        engine.dispose()


def test_auth_audit_metadata_and_technical_logs_are_sanitized(monkeypatch, migrated_database: str) -> None:
    create_user(migrated_database)
    handler = ListHandler()
    logger = logging.getLogger("ibb_portal")
    logger.disabled = False
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    client = create_client(monkeypatch, migrated_database)
    password = "StrongPass123!"

    try:
        response = client.post("/auth/login", json={"email": "user@example.com", "password": password})
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    log_text = "\n".join(handler.messages)
    assert "request_completed" in log_text
    assert "user@example.com" not in log_text
    assert password not in log_text
    assert "ibb_access_token" not in log_text
    assert "ibb_refresh_token" not in log_text

    from sqlalchemy import create_engine

    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            actions = set(session.execute(select(audit_logs.c.action)).scalars())
            metadata_rows = session.execute(select(audit_logs.c.metadata_json)).scalars().all()
            assert "login_success" in actions
            assert all("user@example.com" not in str(row) for row in metadata_rows)
            assert all(password not in str(row) for row in metadata_rows)
    finally:
        engine.dispose()
