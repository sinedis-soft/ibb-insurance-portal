from __future__ import annotations

import sqlalchemy as sa

revision = "20260628_0014"
down_revision = "20260628_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    if "application_submit_attempts" not in existing_tables:
        op.create_table(
            "application_submit_attempts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=False),
            sa.Column("attempt_no", sa.Integer(), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="started", nullable=False),
            sa.Column("bitrix_deal_id", sa.Integer(), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                "status in ('started', 'succeeded', 'failed', 'retry_required')",
                name="ck_application_submit_attempts_status",
            ),
            sa.ForeignKeyConstraint(
                ["application_id"],
                ["portal_applications.id"],
                name="fk_application_submit_attempts_application_id",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        )
        op.create_index(
            "ix_application_submit_attempts_application_id",
            "application_submit_attempts",
            ["application_id"],
        )
        op.create_index("ix_application_submit_attempts_status", "application_submit_attempts", ["status"])

    existing_statuses = {
        row[0]
        for row in bind.execute(
            sa.text("select code from portal_statuses where code in ('submitting', 'submit_error')")
        )
    }
    if "submitting" not in existing_statuses:
        bind.execute(
            sa.text(
                "insert into portal_statuses "
                "(code, name_ru, name_ka, is_final, is_active, sort_order) "
                "values "
                "('submitting', 'Отправляется', 'იგზავნება', 0, 1, 15)"
            )
        )
    if "submit_error" not in existing_statuses:
        bind.execute(
            sa.text(
                "insert into portal_statuses "
                "(code, name_ru, name_ka, is_final, is_active, sort_order) "
                "values "
                "('submit_error', 'Ошибка отправки', 'გაგზავნის შეცდომა', 0, 1, 25)"
            )
        )


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    if "application_submit_attempts" in existing_tables:
        op.drop_index("ix_application_submit_attempts_status", table_name="application_submit_attempts")
        op.drop_index("ix_application_submit_attempts_application_id", table_name="application_submit_attempts")
        op.drop_table("application_submit_attempts")
    bind.execute(sa.text("delete from portal_statuses where code in ('submitting', 'submit_error')"))
