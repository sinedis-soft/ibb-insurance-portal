from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260628_0002"
down_revision = "20260627_0001"
branch_labels = None
depends_on = None

COUNTRY_CODE_PAIRS = [
    ("poland", "PL"),
    ("kazakhstan", "KZ"),
    ("georgia", "GE"),
    ("belarus", "BY"),
    ("russia", "RU"),
    ("latvia", "LV"),
    ("lithuania", "LT"),
    ("european_union", "EU"),
    ("other", "OTHER"),
]


def _rename_country_code(old_code: str, new_code: str) -> None:
    op.get_bind().execute(
        sa.text(
            """
            update countries
            set code = :new_code
            where code = :old_code
              and not exists (
                select 1 from countries existing where existing.code = :new_code
              )
            """
        ),
        {"old_code": old_code, "new_code": new_code},
    )


def upgrade() -> None:
    for old_code, new_code in COUNTRY_CODE_PAIRS:
        _rename_country_code(old_code, new_code)


def downgrade() -> None:
    for old_code, new_code in reversed(COUNTRY_CODE_PAIRS):
        _rename_country_code(new_code, old_code)
