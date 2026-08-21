"""Add versioned, discardable derived artifacts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_derived_artifacts"
down_revision: str | None = "0005_background_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "derived_artifacts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("source_turn_id", sa.String(length=36), nullable=True),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("artifact_version", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_turn_id"], ["turns.id"], ondelete="SET NULL"),
        sa.CheckConstraint("source_revision >= 0", name="ck_derived_artifacts_revision_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "playthrough_id",
            "branch_id",
            "artifact_type",
            "source_revision",
            "artifact_version",
            name="uq_derived_artifacts_revision",
        ),
    )
    op.create_index("ix_derived_artifacts_artifact_type", "derived_artifacts", ["artifact_type"])
    op.create_index("ix_derived_artifacts_playthrough_id", "derived_artifacts", ["playthrough_id"])
    op.create_index("ix_derived_artifacts_branch_id", "derived_artifacts", ["branch_id"])
    op.create_index("ix_derived_artifacts_content_hash", "derived_artifacts", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_derived_artifacts_content_hash", table_name="derived_artifacts")
    op.drop_index("ix_derived_artifacts_branch_id", table_name="derived_artifacts")
    op.drop_index("ix_derived_artifacts_playthrough_id", table_name="derived_artifacts")
    op.drop_index("ix_derived_artifacts_artifact_type", table_name="derived_artifacts")
    op.drop_table("derived_artifacts")
