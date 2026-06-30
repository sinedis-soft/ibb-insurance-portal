from __future__ import annotations

import sqlalchemy as sa

revision = "20260629_0019"
down_revision = "20260629_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("partner_client_requests")}
    additions = [
        ("decision_status", sa.Column("decision_status", sa.String(length=64), nullable=True)),
        ("decision_reason", sa.Column("decision_reason", sa.Text(), nullable=True)),
        ("decided_at", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True)),
        ("decided_by_bitrix_user_id", sa.Column("decided_by_bitrix_user_id", sa.Integer(), nullable=True)),
        (
            "linked_to_existing",
            sa.Column("linked_to_existing", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
        ("linked_bitrix_company_id", sa.Column("linked_bitrix_company_id", sa.Integer(), nullable=True)),
        ("original_bitrix_company_id", sa.Column("original_bitrix_company_id", sa.Integer(), nullable=True)),
    ]
    for name, column in additions:
        if name not in columns:
            op.add_column("partner_client_requests", column)


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("partner_client_requests")}
    for name in (
        "original_bitrix_company_id",
        "linked_bitrix_company_id",
        "linked_to_existing",
        "decided_by_bitrix_user_id",
        "decided_at",
        "decision_reason",
        "decision_status",
    ):
        if name in columns:
            op.drop_column("partner_client_requests", name)
