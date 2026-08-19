"""Add application-level active branch selection."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_application_services"
down_revision: str | None = "0003_context_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "playthroughs",
        sa.Column("active_branch_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_playthroughs_active_branch_id", "playthroughs", ["active_branch_id"])


def downgrade() -> None:
    op.drop_index("ix_playthroughs_active_branch_id", table_name="playthroughs")
    op.drop_column("playthroughs", "active_branch_id")
