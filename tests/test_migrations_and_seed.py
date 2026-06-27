from __future__ import annotations

from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

from alembic import command
from app.models import (
    bitrix_categories,
    bitrix_stage_mappings,
    languages,
    product_groups,
    product_types,
    roles,
)
from app.seed import seed_reference_data


def test_migrations_upgrade_and_downgrade_clean_database(
    monkeypatch,
    sqlite_database_url: str,
    alembic_config: Config,
) -> None:
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    command.upgrade(alembic_config, "head")

    engine = create_engine(sqlite_database_url)
    try:
        inspector = inspect(engine)
        assert inspector.has_table("roles")
        assert inspector.has_table("bitrix_stage_mappings")
    finally:
        engine.dispose()

    command.downgrade(alembic_config, "-1")

    engine = create_engine(sqlite_database_url)
    try:
        assert not inspect(engine).has_table("roles")
    finally:
        engine.dispose()


def test_seed_creates_required_reference_data(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            role_codes = set(session.execute(select(roles.c.code)).scalars())
            language_codes = set(session.execute(select(languages.c.code)).scalars())
            group_codes = set(session.execute(select(product_groups.c.code)).scalars())
            category_ids = set(session.execute(select(bitrix_categories.c.bitrix_category_id)).scalars())

            assert {
                "client_executor",
                "client_admin",
                "client_viewer",
                "partner",
                "superadmin",
            }.issubset(role_codes)
            assert {"ru", "ka"}.issubset(language_codes)
            assert {"auto", "cargo"}.issubset(group_codes)
            assert {0, 19}.issubset(category_ids)

            auto_mappings = session.execute(
                select(func.count())
                .select_from(bitrix_stage_mappings)
                .where(bitrix_stage_mappings.c.bitrix_category_id == 0)
            ).scalar_one()
            cargo_mappings = session.execute(
                select(func.count())
                .select_from(bitrix_stage_mappings)
                .where(bitrix_stage_mappings.c.bitrix_category_id == 19)
            ).scalar_one()

            assert auto_mappings >= 10
            assert cargo_mappings >= 8
    finally:
        engine.dispose()


def test_seed_is_idempotent(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            before = session.execute(select(func.count()).select_from(product_types)).scalar_one()
            seed_reference_data(session)
            seed_reference_data(session)
            after = session.execute(select(func.count()).select_from(product_types)).scalar_one()
    finally:
        engine.dispose()

    assert after == before
