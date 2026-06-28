from __future__ import annotations

import sqlalchemy as sa

revision = "20260628_0012"
down_revision = "20260628_0011"
branch_labels = None
depends_on = None


USER_COMPANY_ELIGIBILITY_COLUMNS = (
    sa.Column("portal_applications_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("auto_ergo_lv_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("auto_dionis_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("auto_deda_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("auto_russian_insurers_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("auto_belarusian_insurers_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("auto_polish_insurers_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("cargo_dionis_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("cargo_deda_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("cargo_russian_insurers_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("cargo_belarusian_insurers_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("cargo_polish_insurers_allowed_cache", sa.Boolean(), nullable=False, server_default=sa.false()),
)

DOCUMENT_COLUMNS = (
    sa.Column("bitrix_company_id", sa.Integer(), nullable=True),
    sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
    sa.Column("mime_type", sa.String(length=255), nullable=True),
    sa.Column("size_bytes", sa.Integer(), nullable=True),
    sa.Column("storage_provider", sa.String(length=64), nullable=False, server_default="portal_temp"),
    sa.Column("storage_key", sa.String(length=512), nullable=True),
    sa.Column("bitrix_file_id", sa.String(length=128), nullable=True),
    sa.Column("bitrix_deal_id", sa.Integer(), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
)


def _add_missing_columns(table_name: str, columns: tuple[sa.Column, ...]) -> None:
    from alembic import op

    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column.copy())


def _create_missing_indexes(table_name: str, indexes: dict[str, list[str]]) -> None:
    from alembic import op

    bind = op.get_bind()
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    for index_name, columns in indexes.items():
        if index_name not in existing:
            op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    from alembic import op

    _add_missing_columns("user_company_roles", USER_COMPANY_ELIGIBILITY_COLUMNS)
    _add_missing_columns("document_transfer_logs", DOCUMENT_COLUMNS)
    _create_missing_indexes(
        "document_transfer_logs",
        {
            "ix_document_transfer_logs_bitrix_company_id": ["bitrix_company_id"],
            "ix_document_transfer_logs_transfer_status": ["transfer_status"],
        },
    )

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        checks = {constraint["name"] for constraint in sa.inspect(bind).get_check_constraints("document_transfer_logs")}
        if "ck_document_transfer_logs_document_type" in checks:
            op.drop_constraint(
                "ck_document_transfer_logs_document_type",
                "document_transfer_logs",
                type_="check",
            )
        op.create_check_constraint(
            "ck_document_transfer_logs_document_type",
            "document_transfer_logs",
            "document_type in ('client_document', 'policy_file', 'invoice', 'certificate', 'other', "
            "'vehicle_registration_certificate', 'lease_agreement', 'previous_policy', 'cmr', "
            "'transport_document', 'cargo_description', 'contract', 'certificate_basis')",
        )
        if "ck_document_transfer_logs_transfer_status" not in checks:
            op.create_check_constraint(
                "ck_document_transfer_logs_transfer_status",
                "document_transfer_logs",
                "transfer_status in ('pending', 'transfer_pending', 'transferred', 'retry_required', "
                "'rejected', 'failed', 'synced')",
            )


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    for index_name in (
        "ix_document_transfer_logs_transfer_status",
        "ix_document_transfer_logs_bitrix_company_id",
    ):
        op.drop_index(index_name, table_name="document_transfer_logs")
    op.drop_constraint("ck_document_transfer_logs_transfer_status", "document_transfer_logs", type_="check")

    for column in reversed(DOCUMENT_COLUMNS):
        op.drop_column("document_transfer_logs", column.name)
    for column in reversed(USER_COMPANY_ELIGIBILITY_COLUMNS):
        op.drop_column("user_company_roles", column.name)
