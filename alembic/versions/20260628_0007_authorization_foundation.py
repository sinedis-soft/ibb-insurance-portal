from __future__ import annotations

from app.models import document_transfer_logs, partner_client_links, portal_applications

revision = "20260628_0007"
down_revision = "20260628_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    partner_client_links.create(bind=bind, checkfirst=True)
    portal_applications.create(bind=bind, checkfirst=True)
    document_transfer_logs.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    document_transfer_logs.drop(bind=bind, checkfirst=True)
    portal_applications.drop(bind=bind, checkfirst=True)
    partner_client_links.drop(bind=bind, checkfirst=True)
