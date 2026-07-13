from __future__ import annotations

import sqlalchemy as sa

revision = "20260713_0022"
down_revision = "20260713_0021"
branch_labels = None
depends_on = None


def _add_column_if_missing(op, inspector, table: str, column: sa.Column) -> None:
    if column.name not in {col["name"] for col in inspector.get_columns(table)}:
        op.add_column(table, column)


def upgrade() -> None:
    from alembic import op

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "portal_users" in tables:
        _add_column_if_missing(
            op,
            inspector,
            "portal_users",
            sa.Column("bitrix_contact_link_status", sa.String(32), nullable=False, server_default="not_linked"),
        )
        _add_column_if_missing(
            op,
            inspector,
            "portal_users",
            sa.Column("bitrix_contact_verified_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "user_company_roles" in tables:
        _add_column_if_missing(
            op,
            inspector,
            "user_company_roles",
            sa.Column("bitrix_company_verified_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "integration_errors" in tables:
        _add_column_if_missing(
            op, inspector, "integration_errors", sa.Column("correlation_id", sa.String(128), nullable=True)
        )
        _add_column_if_missing(
            op, inspector, "integration_errors", sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=True)
        )
        _add_column_if_missing(
            op, inspector, "integration_errors", sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True)
        )
        _add_column_if_missing(
            op,
            inspector,
            "integration_errors",
            sa.Column("retry_supported", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        _add_column_if_missing(
            op,
            inspector,
            "integration_errors",
            sa.Column("attempt_history_json", sa.JSON(), nullable=False, server_default="[]"),
        )
        op.create_index(
            "ix_integration_errors_correlation_id",
            "integration_errors",
            ["correlation_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    from alembic import op

    if op.get_bind().dialect.name == "sqlite":
        return
    inspector = sa.inspect(op.get_bind())
    if "integration_errors" in inspector.get_table_names():
        indexes = {idx["name"] for idx in inspector.get_indexes("integration_errors")}
        if "ix_integration_errors_correlation_id" in indexes:
            op.drop_index("ix_integration_errors_correlation_id", table_name="integration_errors")
