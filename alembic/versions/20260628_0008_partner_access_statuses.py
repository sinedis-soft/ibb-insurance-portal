from __future__ import annotations

import sqlalchemy as sa

revision = "20260628_0008"
down_revision = "20260628_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("partner_client_links")}
    columns = {
        "status": sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        "is_other_partner_client": sa.Column(
            "is_other_partner_client",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        "confirmed_by_user_id": sa.Column("confirmed_by_user_id", sa.Integer(), nullable=True),
        "confirmed_at": sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in columns.items():
        if name not in existing_columns:
            op.add_column("partner_client_links", column)

    partner_client_links = sa.Table(
        "partner_client_links",
        sa.MetaData(),
        sa.Column("partner_user_id", sa.Integer()),
        sa.Column("bitrix_company_id", sa.Integer()),
    )
    sa.Index(
        "uq_partner_client_links_partner_company",
        partner_client_links.c.partner_user_id,
        partner_client_links.c.bitrix_company_id,
        unique=True,
    ).create(bind=bind, checkfirst=True)


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    partner_client_links = sa.Table(
        "partner_client_links",
        sa.MetaData(),
        sa.Column("partner_user_id", sa.Integer()),
        sa.Column("bitrix_company_id", sa.Integer()),
    )
    sa.Index(
        "uq_partner_client_links_partner_company",
        partner_client_links.c.partner_user_id,
        partner_client_links.c.bitrix_company_id,
        unique=True,
    ).drop(bind=bind, checkfirst=True)
    if bind.dialect.name == "sqlite":
        return
    existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("partner_client_links")}
    for name in ("confirmed_at", "confirmed_by_user_id", "is_other_partner_client", "status"):
        if name in existing_columns:
            op.drop_column("partner_client_links", name)
