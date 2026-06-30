from __future__ import annotations

import sqlalchemy as sa

revision = "20260629_0018"
down_revision = "20260629_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("partner_client_requests")}
    if "bitrix_check_status" not in columns:
        op.add_column(
            "partner_client_requests",
            sa.Column("bitrix_check_status", sa.String(length=64), nullable=False, server_default="pending"),
        )
    if "bitrix_sync_error" not in columns:
        op.add_column("partner_client_requests", sa.Column("bitrix_sync_error", sa.String(length=128), nullable=True))
    if "bitrix_synced_at" not in columns:
        op.add_column(
            "partner_client_requests",
            sa.Column("bitrix_synced_at", sa.DateTime(timezone=True), nullable=True),
        )
    if bind.dialect.name != "sqlite":
        op.drop_constraint(
            "ck_partner_client_requests_bitrix_sync_status",
            "partner_client_requests",
            type_="check",
        )
        op.create_check_constraint(
            "ck_partner_client_requests_bitrix_sync_status",
            "partner_client_requests",
            "bitrix_sync_status in ('pending', 'synced', 'sync_error', 'retry_required', 'failed')",
        )
        op.create_check_constraint(
            "ck_partner_client_requests_bitrix_check_status",
            "partner_client_requests",
            "bitrix_check_status in ('pending', 'clarification_required', 'confirmed', 'duplicate_found', 'rejected')",
        )


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("partner_client_requests")}
    if "bitrix_check_status" in columns:
        op.drop_constraint(
            "ck_partner_client_requests_bitrix_check_status",
            "partner_client_requests",
            type_="check",
        )
    op.drop_constraint(
        "ck_partner_client_requests_bitrix_sync_status",
        "partner_client_requests",
        type_="check",
    )
    op.create_check_constraint(
        "ck_partner_client_requests_bitrix_sync_status",
        "partner_client_requests",
        "bitrix_sync_status in ('pending', 'synced', 'sync_error', 'retry_required')",
    )
    if "bitrix_check_status" in columns:
        op.drop_column("partner_client_requests", "bitrix_check_status")
    if "bitrix_sync_error" in columns:
        op.drop_column("partner_client_requests", "bitrix_sync_error")
    if "bitrix_synced_at" in columns:
        op.drop_column("partner_client_requests", "bitrix_synced_at")
