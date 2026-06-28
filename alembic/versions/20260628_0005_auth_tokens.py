from __future__ import annotations

from app.models import auth_tokens

revision = "20260628_0005"
down_revision = "20260628_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op

    auth_tokens.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from alembic import op

    auth_tokens.drop(bind=op.get_bind(), checkfirst=True)
