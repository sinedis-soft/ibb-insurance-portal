# ruff: noqa: E501,F401
from __future__ import annotations

import sqlalchemy as sa

revision = "20260713_0024"
down_revision = "20260713_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    inspector = sa.inspect(op.get_bind())
    if "email_messages" in inspector.get_table_names():
        return
    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_code", sa.String(length=128), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("locale", sa.String(length=16), nullable=False, server_default="ru"),
        sa.Column("recipient_user_id", sa.Integer(), nullable=True),
        sa.Column("recipient_ref", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("safe_error_code", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("template_variables", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('pending', 'processing', 'sent', 'retry_scheduled', 'failed', 'cancelled', 'delivered', 'bounced', 'rejected')", name="ck_email_messages_status"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["portal_users.id"], name="fk_email_messages_recipient_user_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_email_messages_idempotency_key"),
    )
    op.create_index("ix_email_messages_status_scheduled", "email_messages", ["status", "scheduled_at"])
    op.create_index("ix_email_messages_template_code", "email_messages", ["template_code"])
    op.create_index("ix_email_messages_event_type", "email_messages", ["event_type"])
    op.create_index("ix_email_messages_target", "email_messages", ["target_type", "target_id"])
    op.create_index("ix_email_messages_correlation_id", "email_messages", ["correlation_id"])


def downgrade() -> None:
    from alembic import op

    inspector = sa.inspect(op.get_bind())
    if "email_messages" not in inspector.get_table_names():
        return
    op.drop_index("ix_email_messages_correlation_id", table_name="email_messages")
    op.drop_index("ix_email_messages_target", table_name="email_messages")
    op.drop_index("ix_email_messages_event_type", table_name="email_messages")
    op.drop_index("ix_email_messages_template_code", table_name="email_messages")
    op.drop_index("ix_email_messages_status_scheduled", table_name="email_messages")
    op.drop_table("email_messages")
