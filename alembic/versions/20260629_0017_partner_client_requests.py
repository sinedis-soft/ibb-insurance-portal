from __future__ import annotations

import sqlalchemy as sa

revision = "20260629_0017"
down_revision = "20260629_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "partner_client_requests" not in inspector.get_table_names():
        op.create_table(
            "partner_client_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("partner_user_id", sa.Integer(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("company_name", sa.String(length=255), nullable=False),
            sa.Column("country", sa.String(length=16), nullable=True),
            sa.Column("registration_number", sa.String(length=128), nullable=True),
            sa.Column("tax_id", sa.String(length=128), nullable=True),
            sa.Column("address", sa.String(length=512), nullable=True),
            sa.Column("contact_name", sa.String(length=255), nullable=False),
            sa.Column("contact_email", sa.String(length=320), nullable=False),
            sa.Column("contact_phone", sa.String(length=64), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=64), nullable=False, server_default="pending"),
            sa.Column("bitrix_check_entity_type", sa.String(length=64), nullable=True),
            sa.Column("bitrix_check_entity_id", sa.Integer(), nullable=True),
            sa.Column("bitrix_sync_status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("bitrix_sync_error_code", sa.String(length=128), nullable=True),
            sa.Column("confirmed_company_id", sa.Integer(), nullable=True),
            sa.Column("confirmed_bitrix_company_id", sa.Integer(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("clarification_comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                "status in ('draft', 'pending', 'clarification_required', 'confirmed', "
                "'duplicate_found', 'rejected')",
                name="ck_partner_client_requests_status",
            ),
            sa.CheckConstraint(
                "bitrix_sync_status in ('pending', 'synced', 'sync_error', 'retry_required', 'failed')",
                name="ck_partner_client_requests_bitrix_sync_status",
            ),
            sa.ForeignKeyConstraint(
                ["partner_user_id"],
                ["portal_users.id"],
                name="fk_partner_client_requests_partner",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"],
                ["portal_users.id"],
                name="fk_partner_client_requests_created_by",
            ),
        )
        op.create_index(
            "ix_partner_client_requests_partner_user_id",
            "partner_client_requests",
            ["partner_user_id"],
        )
        op.create_index("ix_partner_client_requests_status", "partner_client_requests", ["status"])
        op.create_index(
            "ix_partner_client_requests_bitrix_check_entity",
            "partner_client_requests",
            ["bitrix_check_entity_type", "bitrix_check_entity_id"],
        )

    app_columns = {column["name"] for column in inspector.get_columns("portal_applications")}
    if "partner_client_request_id" not in app_columns:
        op.add_column("portal_applications", sa.Column("partner_client_request_id", sa.Integer(), nullable=True))
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_portal_applications_partner_client_request_id",
                "portal_applications",
                "partner_client_requests",
                ["partner_client_request_id"],
                ["id"],
            )
        op.create_index(
            "ix_portal_applications_partner_client_request_id",
            "portal_applications",
            ["partner_client_request_id"],
        )


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        app_columns = {column["name"] for column in sa.inspect(bind).get_columns("portal_applications")}
        if "partner_client_request_id" in app_columns:
            op.drop_index("ix_portal_applications_partner_client_request_id", table_name="portal_applications")
            op.drop_constraint(
                "fk_portal_applications_partner_client_request_id",
                "portal_applications",
                type_="foreignkey",
            )
            op.drop_column("portal_applications", "partner_client_request_id")
        if "partner_client_requests" in sa.inspect(bind).get_table_names():
            op.drop_index("ix_partner_client_requests_bitrix_check_entity", table_name="partner_client_requests")
            op.drop_index("ix_partner_client_requests_status", table_name="partner_client_requests")
            op.drop_index("ix_partner_client_requests_partner_user_id", table_name="partner_client_requests")
            op.drop_table("partner_client_requests")
