from __future__ import annotations

from app.models import user_company_roles

revision = "20260628_0006"
down_revision = "20260628_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    user_company_roles.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from alembic import op

    user_company_roles.drop(bind=op.get_bind(), checkfirst=True)
