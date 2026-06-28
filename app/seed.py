from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Table, insert, select, update
from sqlalchemy.orm import Session

from app.models import (
    auto_product_rules,
    auto_products,
    bitrix_categories,
    bitrix_stage_mappings,
    countries,
    languages,
    portal_statuses,
    product_groups,
    product_types,
    roles,
)
from app.reference_data import (
    AUTO_PRODUCT_RULES,
    AUTO_PRODUCTS,
    BITRIX_CATEGORIES,
    BITRIX_STAGE_MAPPINGS,
    COUNTRIES,
    LANGUAGES,
    PORTAL_STATUSES,
    PRODUCT_GROUPS,
    PRODUCT_TYPES,
    ROLES,
)

LEGACY_COUNTRY_CODE_MAP = {
    "poland": "PL",
    "kazakhstan": "KZ",
    "georgia": "GE",
    "belarus": "BY",
    "russia": "RU",
    "latvia": "LV",
    "lithuania": "LT",
    "european_union": "EU",
    "other": "OTHER",
}


def upsert_by_keys(session: Session, table: Table, rows: Iterable[dict], key_columns: tuple[str, ...]) -> None:
    for row in rows:
        filters = [table.c[column] == row[column] for column in key_columns]
        existing_id = session.execute(select(table.c.id).where(*filters)).scalar_one_or_none()
        if existing_id is None:
            session.execute(insert(table).values(**row))
        else:
            values = {key: value for key, value in row.items() if key not in key_columns}
            if values:
                session.execute(update(table).where(table.c.id == existing_id).values(**values))


def normalize_legacy_country_codes(session: Session) -> None:
    for legacy_code, current_code in LEGACY_COUNTRY_CODE_MAP.items():
        current_id = session.execute(
            select(countries.c.id).where(countries.c.code == current_code)
        ).scalar_one_or_none()
        legacy_id = session.execute(select(countries.c.id).where(countries.c.code == legacy_code)).scalar_one_or_none()
        if legacy_id is not None and current_id is None:
            session.execute(update(countries).where(countries.c.id == legacy_id).values(code=current_code))


def seed_reference_data(session: Session) -> None:
    upsert_by_keys(session, roles, ROLES, ("code",))
    normalize_legacy_country_codes(session)
    upsert_by_keys(session, countries, COUNTRIES, ("code",))
    upsert_by_keys(session, languages, LANGUAGES, ("code",))
    upsert_by_keys(session, product_groups, PRODUCT_GROUPS, ("code",))
    upsert_by_keys(session, auto_products, AUTO_PRODUCTS, ("code",))
    upsert_by_keys(
        session,
        auto_product_rules,
        AUTO_PRODUCT_RULES,
        (
            "product_code",
            "company_country_code",
            "vehicle_registration_country_code",
            "coverage_country_code",
            "coverage_zone_code",
        ),
    )
    upsert_by_keys(session, portal_statuses, PORTAL_STATUSES, ("code",))
    upsert_by_keys(session, bitrix_categories, BITRIX_CATEGORIES, ("bitrix_category_id",))

    group_ids = dict(session.execute(select(product_groups.c.code, product_groups.c.id)).all())
    product_type_rows = [
        {
            "product_group_id": group_ids[row["group_code"]],
            "code": row["code"],
            "name_ru": row["name_ru"],
            "name_ka": row["name_ka"],
            "sort_order": row["sort_order"],
            "is_active": True,
        }
        for row in PRODUCT_TYPES
    ]
    upsert_by_keys(session, product_types, product_type_rows, ("product_group_id", "code"))

    stage_rows = [
        {
            "bitrix_category_id": row["bitrix_category_id"],
            "bitrix_stage_id": row["bitrix_stage_id"],
            "portal_status": row["portal_status"],
            "is_visible_to_client": row.get("is_visible_to_client", True),
            "is_visible_to_partner": row.get("is_visible_to_partner", True),
            "allowed_client_action": row.get("allowed_client_action"),
        }
        for row in BITRIX_STAGE_MAPPINGS
    ]
    upsert_by_keys(session, bitrix_stage_mappings, stage_rows, ("bitrix_category_id", "bitrix_stage_id"))
    session.commit()


def main() -> None:
    from app.db import SessionLocal

    with SessionLocal() as session:
        seed_reference_data(session)


if __name__ == "__main__":
    main()
