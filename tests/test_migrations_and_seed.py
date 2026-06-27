from __future__ import annotations

from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, update
from sqlalchemy.orm import Session

from alembic import command
from app.models import (
    bitrix_categories,
    bitrix_stage_mappings,
    countries,
    languages,
    product_groups,
    product_types,
    roles,
)
from app.scripts.seed_reference_data import main as seed_reference_data_command
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
        inspector = inspect(engine)
        assert inspector.has_table("roles")
        assert inspector.has_table("countries")
    finally:
        engine.dispose()

    command.downgrade(alembic_config, "base")

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
            country_codes = set(session.execute(select(countries.c.code)).scalars())
            language_codes = set(session.execute(select(languages.c.code)).scalars())
            group_codes = set(session.execute(select(product_groups.c.code)).scalars())
            product_type_codes = set(session.execute(select(product_types.c.code)).scalars())
            category_ids = set(session.execute(select(bitrix_categories.c.bitrix_category_id)).scalars())

            assert {
                "client_executor",
                "client_admin",
                "client_viewer",
                "partner",
                "superadmin",
            }.issubset(role_codes)
            assert {"PL", "KZ", "GE", "BY", "RU", "LV", "LT", "EU", "OTHER"}.issubset(country_codes)
            assert {"ru", "ka"}.issubset(language_codes)
            assert {"auto", "cargo"}.issubset(group_codes)
            assert {
                "osago_rf_non_resident",
                "osago_kz_non_resident",
                "green_card_kz",
                "green_card_ge",
                "rocta",
                "cargo_single_shipment",
                "cargo_contract_cover",
                "cargo_document_request",
            }.issubset(product_type_codes)
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
            technical_stage = session.execute(
                select(
                    bitrix_stage_mappings.c.portal_status,
                    bitrix_stage_mappings.c.is_visible_to_client,
                    bitrix_stage_mappings.c.is_visible_to_partner,
                ).where(
                    bitrix_stage_mappings.c.bitrix_category_id == 0,
                    bitrix_stage_mappings.c.bitrix_stage_id == "UC_VEK6VN",
                )
            ).one()
            assert technical_stage.portal_status == "in_work"
            assert technical_stage.is_visible_to_client is False
            assert technical_stage.is_visible_to_partner is False
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


def test_seed_normalizes_legacy_country_codes(migrated_database: str) -> None:
    engine = create_engine(migrated_database)
    try:
        with Session(engine) as session:
            session.execute(update(countries).where(countries.c.code == "PL").values(code="poland"))
            session.commit()

            seed_reference_data(session)

            country_codes = set(session.execute(select(countries.c.code)).scalars())
            assert "PL" in country_codes
            assert "poland" not in country_codes
    finally:
        engine.dispose()


def test_seed_reference_data_command_is_importable() -> None:
    assert callable(seed_reference_data_command)
