from __future__ import annotations

import sqlalchemy as sa

revision = "20260628_0011"
down_revision = "20260628_0010"
branch_labels = None
depends_on = None


def _auto_products_table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "auto_products",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def _auto_product_rules_table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "auto_product_rules",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_code", sa.String(64), nullable=False),
        sa.Column("company_country_code", sa.String(16), nullable=True),
        sa.Column("vehicle_registration_country_code", sa.String(16), nullable=True),
        sa.Column("coverage_country_code", sa.String(16), nullable=True),
        sa.Column("coverage_zone_code", sa.String(16), nullable=True),
        sa.Column("allowed_user_types", sa.JSON, nullable=True),
        sa.Column("allowed_role_codes", sa.JSON, nullable=True),
        sa.Column("requires_manual_review", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["product_code"], ["auto_products.code"], name="fk_auto_product_rules_product_code"),
        sa.Index("ix_auto_product_rules_product_code", "product_code"),
        sa.Index("ix_auto_product_rules_is_active", "is_active"),
    )


def upgrade() -> None:
    from sqlalchemy.orm import Session

    from alembic import op

    bind = op.get_bind()
    metadata = sa.MetaData()
    auto_products = _auto_products_table(metadata)
    auto_product_rules = _auto_product_rules_table(metadata)
    auto_products.create(bind, checkfirst=True)
    auto_product_rules.create(bind, checkfirst=True)

    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("portal_applications")}
    if "draft_data_json" not in columns:
        op.add_column("portal_applications", sa.Column("draft_data_json", sa.JSON(), nullable=True))

    from app.seed import seed_reference_data

    with Session(bind=bind) as session:
        seed_reference_data(session)


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if bind.dialect.name != "sqlite":
        columns = {column["name"] for column in inspector.get_columns("portal_applications")}
        if "draft_data_json" in columns:
            op.drop_column("portal_applications", "draft_data_json")

    metadata = sa.MetaData()
    auto_products = _auto_products_table(metadata)
    auto_product_rules = _auto_product_rules_table(metadata)
    auto_product_rules.drop(bind, checkfirst=True)
    auto_products.drop(bind, checkfirst=True)
