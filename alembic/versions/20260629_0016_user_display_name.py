from __future__ import annotations

import sqlalchemy as sa

revision = "20260629_0016"
down_revision = "20260629_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("portal_users")}
    if "display_name_cache" not in columns:
        op.add_column("portal_users", sa.Column("display_name_cache", sa.String(length=255), nullable=True))


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("portal_users")}
    if "display_name_cache" in columns:
        op.drop_column("portal_users", "display_name_cache")
