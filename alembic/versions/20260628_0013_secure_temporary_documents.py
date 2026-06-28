from __future__ import annotations

import sqlalchemy as sa

revision = "20260628_0013"
down_revision = "20260628_0012"
branch_labels = None
depends_on = None


DOCUMENT_COLUMNS = (
    sa.Column("original_filename", sa.String(length=512), nullable=True),
    sa.Column("file_size", sa.Integer(), nullable=True),
    sa.Column("temporary_storage_path", sa.String(length=1024), nullable=True),
    sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("transfer_started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("local_deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("last_error_code", sa.String(length=128), nullable=True),
)

NEW_STATUS_CHECK = (
    "transfer_status in ('uploaded', 'transferring', 'sent', 'failed', "
    "'retry_required', 'expired', 'deleted')"
)


def _add_missing_columns(table_name: str, columns: tuple[sa.Column, ...]) -> None:
    from alembic import op

    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column.copy())


def upgrade() -> None:
    from alembic import op

    _add_missing_columns("document_transfer_logs", DOCUMENT_COLUMNS)
    bind = op.get_bind()
    op.execute("update document_transfer_logs set file_size = size_bytes where file_size is null")
    op.execute("update document_transfer_logs set uploaded_at = created_at where uploaded_at is null")
    op.execute(
        "update document_transfer_logs set transfer_status = case "
        "when transfer_status in ('pending', 'transfer_pending') then 'uploaded' "
        "when transfer_status in ('transferred', 'synced') then 'sent' "
        "when transfer_status = 'rejected' then 'failed' "
        "else transfer_status end"
    )
    if bind.dialect.name != "sqlite":
        checks = {constraint["name"] for constraint in sa.inspect(bind).get_check_constraints("document_transfer_logs")}
        if "ck_document_transfer_logs_transfer_status" in checks:
            op.drop_constraint(
                "ck_document_transfer_logs_transfer_status",
                "document_transfer_logs",
                type_="check",
            )
        op.create_check_constraint(
            "ck_document_transfer_logs_transfer_status",
            "document_transfer_logs",
            NEW_STATUS_CHECK,
        )


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.drop_constraint("ck_document_transfer_logs_transfer_status", "document_transfer_logs", type_="check")
    op.create_check_constraint(
        "ck_document_transfer_logs_transfer_status",
        "document_transfer_logs",
        "transfer_status in ('pending', 'transfer_pending', 'transferred', 'retry_required', "
        "'rejected', 'failed', 'synced')",
    )
    for column in reversed(DOCUMENT_COLUMNS):
        op.drop_column("document_transfer_logs", column.name)
