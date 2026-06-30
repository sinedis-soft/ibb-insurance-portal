from __future__ import annotations

import sqlalchemy as sa

revision = "20260628_0010"
down_revision = "20260628_0009"
branch_labels = None
depends_on = None


def _portal_policies_table() -> sa.Table:
    metadata = sa.MetaData()
    sa.Table("portal_applications", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table("document_transfer_logs", metadata, sa.Column("id", sa.Integer, primary_key=True))
    return sa.Table(
        "portal_policies",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, nullable=False),
        sa.Column("bitrix_deal_id", sa.Integer, nullable=True),
        sa.Column("bitrix_company_id", sa.Integer, nullable=False),
        sa.Column("policy_number", sa.String(128), nullable=False),
        sa.Column("product_type_code", sa.String(128), nullable=True),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_to", sa.Date, nullable=True),
        sa.Column("premium_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("premium_currency", sa.String(16), nullable=True),
        sa.Column("policy_status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("document_transfer_log_id", sa.Integer, nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "policy_status in ('active', 'expiring_soon', 'expired', 'cancelled', 'annulled', 'draft')",
            name="ck_portal_policies_policy_status",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["portal_applications.id"],
            name="fk_portal_policies_application_id",
        ),
        sa.ForeignKeyConstraint(
            ["document_transfer_log_id"],
            ["document_transfer_logs.id"],
            name="fk_portal_policies_document_transfer_log_id",
        ),
        sa.Index("ix_portal_policies_application_id", "application_id"),
        sa.Index("ix_portal_policies_bitrix_company_id", "bitrix_company_id"),
        sa.Index("ix_portal_policies_policy_status", "policy_status"),
        sa.Index("ix_portal_policies_valid_to", "valid_to"),
        sa.Index("ix_portal_policies_policy_number", "policy_number"),
    )


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    _portal_policies_table().create(bind, checkfirst=True)


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    _portal_policies_table().drop(bind, checkfirst=True)
