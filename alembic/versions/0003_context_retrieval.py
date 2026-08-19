"""Add derived embedding metadata and retrieval trace storage."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_context_retrieval"
down_revision: str | None = "0002_event_log_snapshot_branching"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_embeddings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding_version", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("dimensions > 0", name="ck_memory_embeddings_dimensions_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "model",
            "embedding_version",
            "content_hash",
            name="uq_memory_embeddings_source_version",
        ),
    )
    op.create_index("ix_memory_embeddings_source_id", "memory_embeddings", ["source_id"])
    op.create_index("ix_memory_embeddings_playthrough_id", "memory_embeddings", ["playthrough_id"])
    op.create_index("ix_memory_embeddings_branch_id", "memory_embeddings", ["branch_id"])
    op.create_index("ix_memory_embeddings_content_hash", "memory_embeddings", ["content_hash"])

    op.create_table(
        "retrieval_traces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("query_id", sa.String(length=160), nullable=False),
        sa.Column("phase", sa.String(length=24), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=160), nullable=True),
        sa.Column("world_time", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("world_time >= 0", name="ck_retrieval_traces_time_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retrieval_traces_query_id", "retrieval_traces", ["query_id"])
    op.create_index("ix_retrieval_traces_playthrough_id", "retrieval_traces", ["playthrough_id"])
    op.create_index("ix_retrieval_traces_branch_id", "retrieval_traces", ["branch_id"])
    op.create_index("ix_retrieval_traces_owner_id", "retrieval_traces", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_traces_owner_id", table_name="retrieval_traces")
    op.drop_index("ix_retrieval_traces_branch_id", table_name="retrieval_traces")
    op.drop_index("ix_retrieval_traces_playthrough_id", table_name="retrieval_traces")
    op.drop_index("ix_retrieval_traces_query_id", table_name="retrieval_traces")
    op.drop_table("retrieval_traces")
    op.drop_index("ix_memory_embeddings_content_hash", table_name="memory_embeddings")
    op.drop_index("ix_memory_embeddings_branch_id", table_name="memory_embeddings")
    op.drop_index("ix_memory_embeddings_playthrough_id", table_name="memory_embeddings")
    op.drop_index("ix_memory_embeddings_source_id", table_name="memory_embeddings")
    op.drop_table("memory_embeddings")
