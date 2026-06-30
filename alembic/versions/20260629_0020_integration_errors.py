from __future__ import annotations

import sqlalchemy as sa

revision = "20260629_0020"
down_revision = "20260629_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    inspector = sa.inspect(op.get_bind())
    if "integration_errors" in inspector.get_table_names():
        return
    op.create_table(
        "integration_errors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.String(length=128), nullable=True),
        sa.Column("bitrix_entity_type", sa.String(length=64), nullable=True),
        sa.Column("bitrix_entity_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="failed"),
        sa.Column("error_code", sa.String(length=128), nullable=False),
        sa.Column("safe_message", sa.String(length=512), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "object_type in ('user', 'company', 'application', 'partner_client_request', 'document', 'bitrix')",
            name="ck_integration_errors_object_type",
        ),
        sa.CheckConstraint(
            "operation in ('create', 'update', 'sync', 'webhook', 'upload')",
            name="ck_integration_errors_operation",
        ),
        sa.CheckConstraint(
            "status in ('pending', 'failed', 'retrying', 'resolved')",
            name="ck_integration_errors_status",
        ),
    )
    op.create_index("ix_integration_errors_object", "integration_errors", ["object_type", "object_id"])
    op.create_index("ix_integration_errors_status", "integration_errors", ["status"])
    op.create_index(
        "ix_integration_errors_bitrix_entity",
        "integration_errors",
        ["bitrix_entity_type", "bitrix_entity_id"],
    )


def downgrade() -> None:
    from alembic import op

    if op.get_bind().dialect.name == "sqlite":
        return
    inspector = sa.inspect(op.get_bind())
    if "integration_errors" not in inspector.get_table_names():
        return
    op.drop_index("ix_integration_errors_bitrix_entity", table_name="integration_errors")
    op.drop_index("ix_integration_errors_status", table_name="integration_errors")
    op.drop_index("ix_integration_errors_object", table_name="integration_errors")
    op.drop_table("integration_errors")
