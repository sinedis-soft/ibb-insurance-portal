from __future__ import annotations

import sqlalchemy as sa

revision = "20260713_0023"
down_revision = "20260713_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "application_delegations" not in tables:
        op.create_table(
            "application_delegations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("delegator_user_id", sa.Integer(), nullable=False),
            sa.Column("delegate_user_id", sa.Integer(), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="scheduled"),
            sa.Column("reason", sa.String(512), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completion_reason", sa.String(128), nullable=True),
            sa.Column("idempotency_key", sa.String(128), nullable=True),
            sa.Column("activated_notification_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expiring_notification_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_notification_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("ends_at > starts_at", name="ck_application_delegations_dates"),
            sa.CheckConstraint(
                "delegator_user_id != delegate_user_id", name="ck_application_delegations_distinct_users"
            ),
            sa.CheckConstraint(
                "status in ('scheduled', 'active', 'cancelled', 'expired', 'terminated', 'failed')",
                name="ck_application_delegations_status",
            ),
            sa.ForeignKeyConstraint(["delegator_user_id"], ["portal_users.id"], name="fk_app_delegations_delegator"),
            sa.ForeignKeyConstraint(["delegate_user_id"], ["portal_users.id"], name="fk_app_delegations_delegate"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["portal_users.id"], name="fk_app_delegations_created_by"),
            sa.ForeignKeyConstraint(
                ["cancelled_by_user_id"], ["portal_users.id"], name="fk_app_delegations_cancelled_by"
            ),
            sa.UniqueConstraint("created_by_user_id", "idempotency_key", name="uq_application_delegations_idempotency"),
        )
        op.create_index("ix_application_delegations_company_id", "application_delegations", ["company_id"])
        op.create_index("ix_application_delegations_delegator", "application_delegations", ["delegator_user_id"])
        op.create_index("ix_application_delegations_delegate", "application_delegations", ["delegate_user_id"])
        op.create_index("ix_application_delegations_status", "application_delegations", ["status"])
    if "application_delegation_items" not in tables:
        op.create_table(
            "application_delegation_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("delegation_id", sa.Integer(), nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="scheduled"),
            sa.Column("access_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("access_ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completion_reason", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "status in ('scheduled', 'active', 'cancelled', 'expired', 'terminated', 'failed')",
                name="ck_application_delegation_items_status",
            ),
            sa.ForeignKeyConstraint(
                ["delegation_id"], ["application_delegations.id"], name="fk_delegation_items_delegation"
            ),
            sa.ForeignKeyConstraint(
                ["application_id"], ["portal_applications.id"], name="fk_delegation_items_application"
            ),
        )
        op.create_index("ix_application_delegation_items_delegation", "application_delegation_items", ["delegation_id"])
        op.create_index(
            "ix_application_delegation_items_application", "application_delegation_items", ["application_id"]
        )
        op.create_index(
            "uq_application_delegation_items_open",
            "application_delegation_items",
            ["application_id"],
            unique=True,
            sqlite_where=sa.text("status in ('scheduled', 'active')"),
            postgresql_where=sa.text("status in ('scheduled', 'active')"),
        )

    if "application_delegation_notifications" not in tables:
        op.create_table(
            "application_delegation_notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("delegation_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "status in ('pending', 'sent', 'failed', 'cancelled')", name="ck_delegation_notifications_status"
            ),
            sa.ForeignKeyConstraint(
                ["delegation_id"], ["application_delegations.id"], name="fk_delegation_notifications_delegation"
            ),
            sa.ForeignKeyConstraint(
                ["recipient_user_id"], ["portal_users.id"], name="fk_delegation_notifications_recipient"
            ),
            sa.UniqueConstraint(
                "delegation_id", "event_type", "recipient_user_id", name="uq_delegation_notification_once"
            ),
        )
        op.create_index("ix_delegation_notifications_status", "application_delegation_notifications", ["status"])


def downgrade() -> None:
    from alembic import op

    op.drop_table("application_delegation_notifications")
    op.drop_table("application_delegation_items")
    op.drop_table("application_delegations")
