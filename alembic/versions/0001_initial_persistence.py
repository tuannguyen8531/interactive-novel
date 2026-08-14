"""Create the Phase 2 persistence foundation tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial_persistence"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worlds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("premise", sa.Text(), nullable=False),
        sa.Column("genre", sa.String(length=80), nullable=False),
        sa.Column("tone", sa.String(length=80), nullable=False),
        sa.Column("canon_rules", sa.JSON(), nullable=False),
        sa.Column("content_policy", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_worlds_name"),
    )
    op.create_table(
        "playthroughs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("world_id", sa.String(length=36), nullable=False),
        sa.Column("player_character_id", sa.String(length=36), nullable=True),
        sa.Column("root_branch_id", sa.String(length=36), nullable=True),
        sa.Column("provider_config_snapshot", sa.JSON(), nullable=False),
        sa.Column("world_clock_minutes", sa.Integer(), nullable=False),
        sa.Column("rng_seed", sa.String(length=160), nullable=False),
        sa.Column("rng_state", sa.JSON(), nullable=False),
        sa.Column("lifecycle", sa.String(length=24), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["root_branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_character_id"], ["characters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "lifecycle IN ('active', 'completed', 'archived')",
            name="ck_playthroughs_lifecycle",
        ),
        sa.CheckConstraint("world_clock_minutes >= 0", name="ck_playthroughs_clock_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_playthroughs_world_id", "playthroughs", ["world_id"])
    op.create_table(
        "characters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("world_id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_characters_playthrough_id", "characters", ["playthrough_id"])
    op.create_index("ix_characters_world_id", "characters", ["world_id"])
    op.create_table(
        "branches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("parent_branch_id", sa.String(length=36), nullable=True),
        sa.Column("fork_turn_id", sa.String(length=36), nullable=True),
        sa.Column("head_turn_id", sa.String(length=36), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("head_revision", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["fork_turn_id"], ["turns.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["head_turn_id"], ["turns.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.CheckConstraint("depth >= 0", name="ck_branches_depth_nonnegative"),
        sa.CheckConstraint("head_revision >= 0", name="ck_branches_revision_nonnegative"),
        sa.CheckConstraint("lifecycle IN ('active', 'abandoned')", name="ck_branches_lifecycle"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_branches_playthrough_id", "branches", ["playthrough_id"])
    op.create_table(
        "turns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("parent_turn_id", sa.String(length=36), nullable=True),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("normalized_input", sa.Text(), nullable=True),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("final_narrative", sa.Text(), nullable=True),
        sa.Column("approved_patch", sa.JSON(), nullable=True),
        sa.Column("world_time_start", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("world_time_end", sa.Integer(), nullable=False),
        sa.Column("turn_run_id", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_turn_id"], ["turns.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_turns_status",
        ),
        sa.CheckConstraint("base_revision >= 0", name="ck_turns_base_revision_nonnegative"),
        sa.CheckConstraint("world_time_start >= 0", name="ck_turns_start_nonnegative"),
        sa.CheckConstraint("duration_minutes >= 0", name="ck_turns_duration_nonnegative"),
        sa.CheckConstraint("world_time_end >= world_time_start", name="ck_turns_end_after_start"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turn_run_id", name="uq_turns_run_id"),
    )
    op.create_index("ix_turns_branch_id", "turns", ["branch_id"])
    op.create_index("ix_turns_playthrough_id", "turns", ["playthrough_id"])
    op.create_table(
        "character_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("last_active_turn_id", sa.String(length=36), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_active_turn_id"], ["turns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "character_id",
            "playthrough_id",
            "branch_id",
            name="uq_character_states_scope",
        ),
    )
    op.create_index("ix_character_states_branch_id", "character_states", ["branch_id"])
    op.create_index("ix_character_states_character_id", "character_states", ["character_id"])
    op.create_index("ix_character_states_playthrough_id", "character_states", ["playthrough_id"])


def downgrade() -> None:
    op.drop_table("character_states")
    op.drop_index("ix_turns_playthrough_id", table_name="turns")
    op.drop_index("ix_turns_branch_id", table_name="turns")
    op.drop_table("turns")
    op.drop_index("ix_branches_playthrough_id", table_name="branches")
    op.drop_table("branches")
    op.drop_index("ix_characters_world_id", table_name="characters")
    op.drop_index("ix_characters_playthrough_id", table_name="characters")
    op.drop_table("characters")
    op.drop_index("ix_playthroughs_world_id", table_name="playthroughs")
    op.drop_table("playthroughs")
    op.drop_table("worlds")
