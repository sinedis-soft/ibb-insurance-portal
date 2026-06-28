from __future__ import annotations

import sqlalchemy as sa

revision = "20260629_0015"
down_revision = "20260628_0014"
branch_labels = None
depends_on = None


APPLICATION_SYNC_COLUMNS = (
    sa.Column("sync_status", sa.String(length=32), nullable=False, server_default="pending"),
    sa.Column("last_sync_error_code", sa.String(length=128), nullable=True),
    sa.Column("last_sync_warning_code", sa.String(length=128), nullable=True),
)
POLICY_SYNC_COLUMNS = (sa.Column("insurer_name", sa.String(length=255), nullable=True),)


def _add_missing_columns(table_name: str, columns: tuple[sa.Column, ...]) -> None:
    from alembic import op

    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column.copy())


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    _add_missing_columns("portal_applications", APPLICATION_SYNC_COLUMNS)
    _add_missing_columns("portal_policies", POLICY_SYNC_COLUMNS)
    op.execute("update portal_applications set sync_status = 'synced' where bitrix_deal_id is not null")
    if bind.dialect.name != "sqlite":
        checks = {constraint["name"] for constraint in sa.inspect(bind).get_check_constraints("portal_applications")}
        if "ck_portal_applications_sync_status" not in checks:
            op.create_check_constraint(
                "ck_portal_applications_sync_status",
                "portal_applications",
                "sync_status in ('pending', 'synced', 'sync_error', 'retry_required')",
            )


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    if bind.dialect.name != "sqlite":
        checks = {constraint["name"] for constraint in sa.inspect(bind).get_check_constraints("portal_applications")}
        if "ck_portal_applications_sync_status" in checks:
            op.drop_constraint("ck_portal_applications_sync_status", "portal_applications", type_="check")
    for column in reversed(APPLICATION_SYNC_COLUMNS):
        op.drop_column("portal_applications", column.name)
    for column in reversed(POLICY_SYNC_COLUMNS):
        op.drop_column("portal_policies", column.name)
