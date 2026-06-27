from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command


@pytest.fixture
def sqlite_database_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'ibb_test.db'}"


@pytest.fixture
def alembic_config() -> Config:
    return Config("alembic.ini")


@pytest.fixture
def migrated_database(monkeypatch: pytest.MonkeyPatch, sqlite_database_url: str, alembic_config: Config) -> str:
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("JWT_SECRET", "test_jwt_secret_with_minimum_32_bytes")
    monkeypatch.setenv("COOKIE_SECRET", "test_cookie_secret_with_minimum_32_bytes")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("BITRIX_OUTBOUND_WEBHOOK_SECRET", "test_outbound_secret")
    monkeypatch.setenv("BITRIX_WEBHOOK_URL", "https://example.invalid/rest/1/webhook")
    monkeypatch.setenv("PORTAL_PUBLIC_URL", "http://localhost:3000")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@example.invalid")

    from app.config import get_settings

    get_settings.cache_clear()
    command.upgrade(alembic_config, "head")
    return sqlite_database_url
