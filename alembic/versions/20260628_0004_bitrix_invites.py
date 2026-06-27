from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.models import invite_tokens

revision = "20260628_0004"
down_revision = "20260628_0003"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column("portal_users", "user_type"):
        op.add_column(
            "portal_users",
            sa.Column("user_type", sa.String(32), nullable=False, server_default="client"),
        )
    if bind.dialect.name != "sqlite":
        op.alter_column("portal_users", "role_code", existing_type=sa.String(64), nullable=True)
    invite_tokens.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    invite_tokens.drop(bind=bind, checkfirst=True)
    if bind.dialect.name == "sqlite":
        return
    if bind.dialect.name != "sqlite":
        op.alter_column("portal_users", "role_code", existing_type=sa.String(64), nullable=False)
    if _has_column("portal_users", "user_type"):
        op.drop_column("portal_users", "user_type")
