from __future__ import annotations

import sqlalchemy as sa

revision = "20260713_0021"
down_revision = "20260629_0020"
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
            op, inspector, "portal_users", sa.Column("blocked_reason", sa.String(512), nullable=True)
        )
        _add_column_if_missing(
            op, inspector, "portal_users", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True)
        )
        _add_column_if_missing(
            op, inspector, "portal_users", sa.Column("blocked_by_user_id", sa.Integer(), nullable=True)
        )
        _add_column_if_missing(
            op,
            inspector,
            "portal_users",
            sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "portal_applications" in tables:
        _add_column_if_missing(
            op, inspector, "portal_applications", sa.Column("assigned_to_user_id", sa.Integer(), nullable=True)
        )
        _add_column_if_missing(
            op,
            inspector,
            "portal_applications",
            sa.Column("assignment_status", sa.String(64), nullable=False, server_default="assigned"),
        )
        _add_column_if_missing(
            op, inspector, "portal_applications", sa.Column("reassigned_from_user_id", sa.Integer(), nullable=True)
        )
        _add_column_if_missing(
            op, inspector, "portal_applications", sa.Column("reassigned_at", sa.DateTime(timezone=True), nullable=True)
        )
        _add_column_if_missing(
            op, inspector, "portal_applications", sa.Column("reassignment_reason", sa.String(512), nullable=True)
        )
    if "impersonation_sessions" not in tables:
        op.create_table(
            "impersonation_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=False),
            sa.Column("effective_user_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(512), nullable=False),
            sa.Column("session_token_hash", sa.String(128), nullable=False, unique=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_by_user_id", sa.Integer(), nullable=True),
            sa.Column("end_reason", sa.String(64), nullable=True),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("critical_actions", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["portal_users.id"], name="fk_impersonation_actor_user_id"),
            sa.ForeignKeyConstraint(
                ["effective_user_id"], ["portal_users.id"], name="fk_impersonation_effective_user_id"
            ),
        )
        op.create_index("ix_impersonation_sessions_actor", "impersonation_sessions", ["actor_user_id"])
        op.create_index("ix_impersonation_sessions_effective", "impersonation_sessions", ["effective_user_id"])


def downgrade() -> None:
    from alembic import op

    if op.get_bind().dialect.name == "sqlite":
        return
    inspector = sa.inspect(op.get_bind())
    if "impersonation_sessions" in inspector.get_table_names():
        op.drop_index("ix_impersonation_sessions_effective", table_name="impersonation_sessions")
        op.drop_index("ix_impersonation_sessions_actor", table_name="impersonation_sessions")
        op.drop_table("impersonation_sessions")
