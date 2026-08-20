"""Store progress-aware player move suggestions with canonical turns."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_turn_suggested_actions"
down_revision: str | None = "0006_phase_13_derived_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "turns",
        sa.Column("suggested_actions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("turns", "suggested_actions")
