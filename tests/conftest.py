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

    from app.config import get_settings

    get_settings.cache_clear()
    command.upgrade(alembic_config, "head")
    return sqlite_database_url
