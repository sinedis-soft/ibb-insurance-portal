from __future__ import annotations

import sqlalchemy as sa

revision = "20260628_0009"
down_revision = "20260628_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("portal_applications")}

    def add_column_if_missing(column: sa.Column) -> None:
        if column.name not in columns:
            op.add_column("portal_applications", column)

    add_column_if_missing(sa.Column("application_type", sa.String(32), nullable=False, server_default="auto"))
    add_column_if_missing(sa.Column("bitrix_contact_id", sa.Integer(), nullable=True))
    add_column_if_missing(sa.Column("bitrix_category_id", sa.Integer(), nullable=True))
    add_column_if_missing(sa.Column("bitrix_stage_id", sa.String(128), nullable=True))
    add_column_if_missing(sa.Column("product_type_code", sa.String(128), nullable=True))
    add_column_if_missing(sa.Column("title_cache", sa.String(255), nullable=True))
    add_column_if_missing(sa.Column("client_reference_number", sa.String(128), nullable=True))
    add_column_if_missing(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    add_column_if_missing(sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("portal_applications")}
    if "ix_portal_applications_portal_status" not in indexes:
        op.create_index("ix_portal_applications_portal_status", "portal_applications", ["portal_status"])
    if "ix_portal_applications_application_type" not in indexes:
        op.create_index("ix_portal_applications_application_type", "portal_applications", ["application_type"])


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("portal_applications")}
    if "ix_portal_applications_application_type" in indexes:
        op.drop_index("ix_portal_applications_application_type", table_name="portal_applications")
    if "ix_portal_applications_portal_status" in indexes:
        op.drop_index("ix_portal_applications_portal_status", table_name="portal_applications")

    if bind.dialect.name == "sqlite":
        return

    columns = {column["name"] for column in inspector.get_columns("portal_applications")}
    for column_name in (
        "last_synced_at",
        "submitted_at",
        "client_reference_number",
        "title_cache",
        "product_type_code",
        "bitrix_stage_id",
        "bitrix_category_id",
        "bitrix_contact_id",
        "application_type",
    ):
        if column_name in columns:
            op.drop_column("portal_applications", column_name)
