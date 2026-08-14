"""SQLAlchemy mappings for the Phase 2 persistence foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Metadata root owned by the persistence adapter."""


class WorldModel(Base):
    __tablename__ = "worlds"
    __table_args__ = (UniqueConstraint("name", name="uq_worlds_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    premise: Mapped[str] = mapped_column(Text, nullable=False, default="")
    genre: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    tone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    canon_rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    content_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlaythroughModel(Base):
    __tablename__ = "playthroughs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(String(36), ForeignKey("worlds.id", ondelete="RESTRICT"), nullable=False, index=True)
    player_character_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True
    )
    root_branch_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    provider_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    world_clock_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rng_seed: Mapped[str] = mapped_column(String(160), nullable=False)
    rng_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    lifecycle: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BranchModel(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True
    )
    fork_turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="RESTRICT"), nullable=True)
    head_turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="RESTRICT"), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    head_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifecycle: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TurnModel(Base):
    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="RESTRICT"), nullable=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    final_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_patch: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    world_time_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    world_time_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turn_run_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CharacterModel(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(String(36), ForeignKey("worlds.id", ondelete="RESTRICT"), nullable=False, index=True)
    playthrough_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CharacterStateModel(Base):
    __tablename__ = "character_states"
    __table_args__ = (UniqueConstraint("character_id", "playthrough_id", "branch_id", name="uq_character_states_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    playthrough_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_active_turn_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("turns.id", ondelete="SET NULL"), nullable=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    world_time: Mapped[int] = mapped_column(Integer, nullable=False)
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    salience: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    emotional_intensity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cause_event_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EventParticipantModel(Base):
    __tablename__ = "event_participants"
    __table_args__ = (UniqueConstraint("event_id", "participant_id", "role", name="uq_event_participant_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False)


class KnowledgeClaimModel(Base):
    __tablename__ = "knowledge_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    object_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    typed_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    polarity: Mapped[str] = mapped_column(String(16), nullable=False)
    qualifiers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    valid_time_start: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_time_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch_scope: Mapped[str] = mapped_column(String(36), nullable=False, default="public")
    normalized_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CanonFactModel(Base):
    __tablename__ = "canon_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_claims.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    source_event_or_rule: Mapped[str] = mapped_column(String(160), nullable=False)
    asserted_world_time: Mapped[int] = mapped_column(Integer, nullable=False)
    asserted_turn: Mapped[str | None] = mapped_column(String(36), nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class ClaimLinkModel(Base):
    __tablename__ = "claim_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    from_claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_claims.id", ondelete="CASCADE"), index=True)
    to_claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_claims.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)


class ObservationModel(Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    observer_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    observed_claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_claims.id", ondelete="CASCADE"), index=True)
    source_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    world_time: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    distortion: Mapped[float] = mapped_column(Float, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class BeliefModel(Base):
    __tablename__ = "beliefs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    believer_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_claims.id", ondelete="CASCADE"), index=True)
    stance: Mapped[str] = mapped_column(String(24), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    branch_scope: Mapped[str] = mapped_column(String(36), nullable=False)
    world_time: Mapped[int] = mapped_column(Integer, nullable=False)
    source_reliability: Mapped[float] = mapped_column(Float, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class BeliefEvidenceModel(Base):
    __tablename__ = "belief_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    belief_id: Mapped[str] = mapped_column(String(36), ForeignKey("beliefs.id", ondelete="CASCADE"), index=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    source_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_claims.id", ondelete="CASCADE"), index=True)
    world_time: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class RelationshipModel(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint("playthrough_id", "branch_id", "source_id", "target_id", name="uq_relationship_scope_edge"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RelationshipChangeModel(Base):
    __tablename__ = "relationship_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    relationship_id: Mapped[str] = mapped_column(String(36), ForeignKey("relationships.id", ondelete="CASCADE"), index=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    dimension: Mapped[str] = mapped_column(String(24), nullable=False)
    before: Mapped[float] = mapped_column(Float, nullable=False)
    proposed_delta: Mapped[float] = mapped_column(Float, nullable=False)
    validated_delta: Mapped[float] = mapped_column(Float, nullable=False)
    after: Mapped[float] = mapped_column(Float, nullable=False)
    cause_event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class EmotionalTensionModel(Base):
    __tablename__ = "emotional_tensions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    observer_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    rival_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    focus_id: Mapped[str] = mapped_column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    intensity: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class NarrativeThreadModel(Base):
    __tablename__ = "narrative_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    progress: Mapped[float] = mapped_column(Float, nullable=False)
    urgency: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class NarrativeHookModel(Base):
    __tablename__ = "narrative_hooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(36), ForeignKey("turns.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    source_turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="SET NULL"), nullable=True)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    world_clock_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rng_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    state_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    builder_version: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DerivedJobModel(Base):
    __tablename__ = "derived_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_derived_jobs_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    source_turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="SET NULL"), nullable=True)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    playthrough_id: Mapped[str] = mapped_column(String(36), ForeignKey("playthroughs.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turns.id", ondelete="SET NULL"), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = [
    "Base",
    "BeliefEvidenceModel",
    "BeliefModel",
    "BranchModel",
    "CanonFactModel",
    "ClaimLinkModel",
    "CharacterModel",
    "CharacterStateModel",
    "DerivedJobModel",
    "EmotionalTensionModel",
    "EventModel",
    "EventParticipantModel",
    "KnowledgeClaimModel",
    "NarrativeHookModel",
    "NarrativeThreadModel",
    "ObservationModel",
    "OutboxEventModel",
    "PlaythroughModel",
    "RelationshipChangeModel",
    "RelationshipModel",
    "SnapshotModel",
    "TurnModel",
    "WorldModel",
]
