"""Add durable application background jobs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_background_jobs"
down_revision: str | None = "0004_application_services"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("turn_run_id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=False),
        sa.Column("parent_turn_id", sa.String(length=36), nullable=True),
        sa.Column("config_snapshot_id", sa.String(length=160), nullable=False),
        sa.Column("command_fingerprint", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_jobs_idempotency"),
        sa.UniqueConstraint("turn_run_id", name="uq_jobs_turn_run_id"),
    )
    op.create_index("ix_jobs_playthrough_id", "jobs", ["playthrough_id"])
    op.create_index("ix_jobs_branch_id", "jobs", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_branch_id", table_name="jobs")
    op.drop_index("ix_jobs_playthrough_id", table_name="jobs")
    op.drop_table("jobs")
