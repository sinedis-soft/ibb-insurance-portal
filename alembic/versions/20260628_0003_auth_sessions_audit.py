from __future__ import annotations

from alembic import op
from app.models import audit_logs, portal_users, user_sessions

revision = "20260628_0003"
down_revision = "20260628_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    portal_users.create(bind=bind, checkfirst=True)
    user_sessions.create(bind=bind, checkfirst=True)
    audit_logs.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    audit_logs.drop(bind=bind, checkfirst=True)
    user_sessions.drop(bind=bind, checkfirst=True)
    portal_users.drop(bind=bind, checkfirst=True)
