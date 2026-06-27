from __future__ import annotations

from alembic import op
from app.models import metadata
from app.seed import seed_reference_data

revision = "20260627_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(bind=bind)
    from sqlalchemy.orm import Session

    with Session(bind=bind) as session:
        seed_reference_data(session)


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(bind=bind)
