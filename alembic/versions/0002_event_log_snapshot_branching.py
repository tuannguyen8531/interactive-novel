"""Add canonical event/knowledge/branching records and derived artifacts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_event_log_snapshot_branching"
down_revision: str | None = "0001_initial_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("world_time", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("salience", sa.Float(), nullable=False),
        sa.Column("emotional_intensity", sa.Float(), nullable=False),
        sa.Column("cause_event_ids", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("world_time >= 0", name="ck_events_world_time_nonnegative"),
        sa.CheckConstraint("salience >= 0 AND salience <= 1", name="ck_events_salience_range"),
        sa.CheckConstraint(
            "emotional_intensity >= 0 AND emotional_intensity <= 1",
            name="ck_events_emotional_intensity_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_scope_time", "events", ["playthrough_id", "branch_id", "world_time"])
    op.create_index("ix_events_turn_id", "events", ["turn_id"])

    op.create_table(
        "event_participants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("participant_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "participant_id", "role", name="uq_event_participant_role"),
    )
    op.create_index("ix_event_participants_event_id", "event_participants", ["event_id"])
    op.create_index("ix_event_participants_participant_id", "event_participants", ["participant_id"])

    op.create_table(
        "knowledge_claims",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("claim_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("predicate", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=36), nullable=True),
        sa.Column("typed_value", sa.JSON(), nullable=True),
        sa.Column("polarity", sa.String(length=16), nullable=False),
        sa.Column("qualifiers", sa.JSON(), nullable=False),
        sa.Column("valid_time_start", sa.Integer(), nullable=False),
        sa.Column("valid_time_end", sa.Integer(), nullable=True),
        sa.Column("branch_scope", sa.String(length=36), nullable=False),
        sa.Column("normalized_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("valid_time_start >= 0", name="ck_claims_valid_start_nonnegative"),
        sa.CheckConstraint(
            "valid_time_end IS NULL OR valid_time_end >= valid_time_start",
            name="ck_claims_valid_end_after_start",
        ),
        sa.CheckConstraint("polarity IN ('positive', 'negative')", name="ck_claims_polarity"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_claims_scope_predicate", "knowledge_claims", ["playthrough_id", "branch_id", "predicate"])
    op.create_index("ix_knowledge_claims_fingerprint", "knowledge_claims", ["normalized_fingerprint"])

    op.create_table(
        "canon_facts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("claim_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_event_or_rule", sa.String(length=160), nullable=False),
        sa.Column("asserted_world_time", sa.Integer(), nullable=False),
        sa.Column("asserted_turn", sa.String(length=36), nullable=True),
        sa.Column("superseded_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["knowledge_claims.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('active', 'retracted', 'superseded')", name="ck_canon_facts_status"),
        sa.CheckConstraint("asserted_world_time >= 0", name="ck_canon_facts_time_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "claim_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("from_claim_id", sa.String(length=36), nullable=False),
        sa.Column("to_claim_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_claim_id"], ["knowledge_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_claim_id"], ["knowledge_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("from_claim_id <> to_claim_id", name="ck_claim_links_not_self"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("observer_id", sa.String(length=36), nullable=False),
        sa.Column("observed_claim_id", sa.String(length=36), nullable=False),
        sa.Column("source_event_id", sa.String(length=36), nullable=False),
        sa.Column("method", sa.String(length=24), nullable=False),
        sa.Column("world_time", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("distortion", sa.Float(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observed_claim_id"], ["knowledge_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observer_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("world_time >= 0", name="ck_observations_time_nonnegative"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_observations_confidence_range"),
        sa.CheckConstraint("distortion >= 0 AND distortion <= 1", name="ck_observations_distortion_range"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "beliefs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("believer_id", sa.String(length=36), nullable=False),
        sa.Column("claim_id", sa.String(length=36), nullable=False),
        sa.Column("stance", sa.String(length=24), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("branch_scope", sa.String(length=36), nullable=False),
        sa.Column("world_time", sa.Integer(), nullable=False),
        sa.Column("source_reliability", sa.Float(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["believer_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["knowledge_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("stance IN ('supports', 'rejects', 'uncertain')", name="ck_beliefs_stance"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_beliefs_confidence_range"),
        sa.CheckConstraint("source_reliability >= 0 AND source_reliability <= 1", name="ck_beliefs_reliability_range"),
        sa.CheckConstraint("world_time >= 0", name="ck_beliefs_time_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "belief_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("belief_id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("source_event_id", sa.String(length=36), nullable=False),
        sa.Column("claim_id", sa.String(length=36), nullable=False),
        sa.Column("world_time", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=24), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["belief_id"], ["beliefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["knowledge_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("world_time >= 0", name="ck_belief_evidence_time_nonnegative"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_belief_evidence_confidence_range"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["characters.id"], ondelete="CASCADE"),
        sa.CheckConstraint("source_id <> target_id", name="ck_relationships_not_self"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("playthrough_id", "branch_id", "source_id", "target_id", name="uq_relationship_scope_edge"),
    )

    op.create_table(
        "relationship_changes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("relationship_id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("dimension", sa.String(length=24), nullable=False),
        sa.Column("before", sa.Float(), nullable=False),
        sa.Column("proposed_delta", sa.Float(), nullable=False),
        sa.Column("validated_delta", sa.Float(), nullable=False),
        sa.Column("after", sa.Float(), nullable=False),
        sa.Column("cause_event_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "emotional_tensions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("observer_id", sa.String(length=36), nullable=False),
        sa.Column("rival_id", sa.String(length=36), nullable=False),
        sa.Column("focus_id", sa.String(length=36), nullable=False),
        sa.Column("intensity", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["focus_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observer_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rival_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("intensity >= 0 AND intensity <= 1", name="ck_tensions_intensity_range"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "narrative_threads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("urgency", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.CheckConstraint("progress >= 0 AND progress <= 1", name="ck_threads_progress_range"),
        sa.CheckConstraint("urgency >= 0 AND urgency <= 1", name="ck_threads_urgency_range"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "narrative_hooks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("source_turn_id", sa.String(length=36), nullable=True),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("world_clock_minutes", sa.Integer(), nullable=False),
        sa.Column("rng_state", sa.JSON(), nullable=False),
        sa.Column("state_payload", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("builder_version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_turn_id"], ["turns.id"], ondelete="SET NULL"),
        sa.CheckConstraint("source_revision >= 0", name="ck_snapshots_revision_nonnegative"),
        sa.CheckConstraint("world_clock_minutes >= 0", name="ck_snapshots_clock_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_snapshots_branch_revision", "snapshots", ["branch_id", "source_revision"])

    op.create_table(
        "derived_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("source_turn_id", sa.String(length=36), nullable=True),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_turn_id"], ["turns.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="ck_derived_jobs_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_derived_jobs_attempts_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_derived_jobs_idempotency"),
    )
    op.create_index("ix_derived_jobs_status", "derived_jobs", ["status"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("playthrough_id", sa.String(length=36), nullable=False),
        sa.Column("branch_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('pending', 'dispatched', 'failed')", name="ck_outbox_events_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency"),
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_index("ix_derived_jobs_status", table_name="derived_jobs")
    op.drop_table("derived_jobs")
    op.drop_index("ix_snapshots_branch_revision", table_name="snapshots")
    op.drop_table("snapshots")
    op.drop_table("narrative_hooks")
    op.drop_table("narrative_threads")
    op.drop_table("emotional_tensions")
    op.drop_table("relationship_changes")
    op.drop_table("relationships")
    op.drop_table("belief_evidence")
    op.drop_table("beliefs")
    op.drop_table("observations")
    op.drop_table("claim_links")
    op.drop_table("canon_facts")
    op.drop_index("ix_knowledge_claims_fingerprint", table_name="knowledge_claims")
    op.drop_index("ix_knowledge_claims_scope_predicate", table_name="knowledge_claims")
    op.drop_table("knowledge_claims")
    op.drop_index("ix_event_participants_participant_id", table_name="event_participants")
    op.drop_index("ix_event_participants_event_id", table_name="event_participants")
    op.drop_table("event_participants")
    op.drop_index("ix_events_turn_id", table_name="events")
    op.drop_index("ix_events_scope_time", table_name="events")
    op.drop_table("events")
