"""Persistence-neutral records for the application persistence boundary.

These records deliberately describe only the stable persistence contract. The
full domain entities and invariant-rich value objects belong to the domain layer.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class PersistenceError(RuntimeError):
    """Base error raised by a persistence adapter through its inward port."""

    code = "persistence_error"


class PersistenceNotFoundError(PersistenceError):
    code = "persistence_not_found"


class PersistenceStaleHeadError(PersistenceError):
    code = "stale_branch_revision"


class PersistenceIdempotencyConflictError(PersistenceError):
    code = "idempotency_conflict"


class PersistenceSnapshotError(PersistenceError):
    code = "invalid_snapshot"


def utc_now() -> datetime:
    """Return an aware UTC timestamp for audit columns."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class WorldRecord:
    """Persistence-neutral representation of a reusable world."""

    id: str
    name: str
    premise: str
    genre: str
    tone: str
    canon_rules: dict[str, Any]
    content_policy: dict[str, Any]
    schema_version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        name: str,
        premise: str = "",
        genre: str = "",
        tone: str = "",
        canon_rules: dict[str, Any] | None = None,
        content_policy: dict[str, Any] | None = None,
        world_id: str | None = None,
    ) -> WorldRecord:
        if not name.strip():
            raise ValueError("World name must not be empty.")
        now = utc_now()
        return cls(
            id=world_id or str(uuid4()),
            name=name,
            premise=premise,
            genre=genre,
            tone=tone,
            canon_rules=dict(canon_rules or {}),
            content_policy=dict(content_policy or {}),
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class CharacterRecord:
    """Persistence-neutral character seed/profile owned by a world."""

    id: str
    world_id: str
    playthrough_id: str | None
    display_name: str
    aliases: tuple[str, ...]
    profile: dict[str, Any]
    schema_version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        world_id: str,
        display_name: str,
        aliases: tuple[str, ...] = (),
        profile: dict[str, Any] | None = None,
        playthrough_id: str | None = None,
        character_id: str | None = None,
    ) -> CharacterRecord:
        if not world_id.strip() or not display_name.strip():
            raise ValueError("Character world and display name must not be empty.")
        now = utc_now()
        return cls(
            id=character_id or str(uuid4()),
            world_id=world_id,
            playthrough_id=playthrough_id,
            display_name=display_name,
            aliases=tuple(aliases),
            profile=dict(profile or {}),
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class PlaythroughRecord:
    """Persistence-neutral representation of a single playthrough."""

    id: str
    world_id: str
    player_character_id: str | None
    root_branch_id: str | None
    provider_config_snapshot: dict[str, Any]
    world_clock_minutes: int
    rng_seed: str
    rng_state: dict[str, Any]
    active_branch_id: str | None = None
    lifecycle: str = "active"
    schema_version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        world_id: str,
        player_character_id: str | None = None,
        root_branch_id: str | None = None,
        provider_config_snapshot: dict[str, Any] | None = None,
        world_clock_minutes: int = 0,
        rng_seed: str | None = None,
        rng_state: dict[str, Any] | None = None,
        active_branch_id: str | None = None,
        playthrough_id: str | None = None,
    ) -> PlaythroughRecord:
        if world_clock_minutes < 0:
            raise ValueError("World clock cannot be negative.")
        now = utc_now()
        return cls(
            id=playthrough_id or str(uuid4()),
            world_id=world_id,
            player_character_id=player_character_id,
            root_branch_id=root_branch_id,
            provider_config_snapshot=dict(provider_config_snapshot or {}),
            world_clock_minutes=world_clock_minutes,
            rng_seed=rng_seed or str(uuid4()),
            rng_state=dict(rng_state or {}),
            active_branch_id=active_branch_id,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class BranchRecord:
    """Canonical branch head and ancestry metadata."""

    id: str
    playthrough_id: str
    parent_branch_id: str | None
    fork_turn_id: str | None
    head_turn_id: str | None
    depth: int
    head_revision: int
    lifecycle: str = "active"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def root(cls, *, playthrough_id: str, branch_id: str | None = None) -> BranchRecord:
        now = utc_now()
        return cls(
            id=branch_id or str(uuid4()),
            playthrough_id=playthrough_id,
            parent_branch_id=None,
            fork_turn_id=None,
            head_turn_id=None,
            depth=0,
            head_revision=0,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class TurnRecord:
    """Canonical committed turn returned without exposing an ORM model."""

    id: str
    playthrough_id: str
    branch_id: str
    parent_turn_id: str | None
    raw_input: str
    normalized_input: str | None
    base_revision: int
    status: str
    final_narrative: str | None
    approved_patch: dict[str, Any] | None
    world_time_start: int
    duration_minutes: int
    world_time_end: int
    turn_run_id: str
    schema_version: int
    created_at: datetime
    updated_at: datetime
    suggested_actions: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class EventRecord:
    event_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    event_type: str
    world_time: int
    location_id: str | None = None
    actor_ids: tuple[str, ...] = ()
    target_ids: tuple[str, ...] = ()
    witness_ids: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    salience: float = 0.5
    emotional_intensity: float = 0.0
    cause_event_ids: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class KnowledgeClaimRecord:
    claim_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    claim_type: str
    subject_id: str
    predicate: str
    object_id: str | None
    typed_value: Any
    polarity: str
    qualifiers: dict[str, Any]
    valid_time_start: int
    valid_time_end: int | None
    branch_scope: str
    normalized_fingerprint: str
    schema_version: str
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CanonFactRecord:
    fact_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    claim_id: str
    status: str
    source_event_or_rule: str
    asserted_world_time: int
    asserted_turn: str | None = None
    superseded_by: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimLinkRecord:
    link_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    from_claim_id: str
    to_claim_id: str
    kind: str


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    observation_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    observer_id: str
    observed_claim_id: str
    source_event_id: str
    method: str
    world_time: int
    confidence: float
    distortion: float
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BeliefRecord:
    belief_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    believer_id: str
    claim_id: str
    stance: str
    confidence: float
    branch_scope: str
    world_time: int
    source_reliability: float
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BeliefEvidenceRecord:
    evidence_id: str
    belief_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    owner_id: str
    source_event_id: str
    claim_id: str
    world_time: int
    method: str
    confidence: float
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CharacterStateRecord:
    character_id: str
    playthrough_id: str
    branch_id: str
    state: dict[str, Any]
    last_active_turn_id: str | None
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class RelationshipRecord:
    relationship_id: str
    playthrough_id: str
    branch_id: str
    source_id: str
    target_id: str
    values: dict[str, float]
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class RelationshipChangeRecord:
    change_id: str
    relationship_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    dimension: str
    before: float
    proposed_delta: float
    validated_delta: float
    after: float
    cause_event_id: str
    reason: str
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmotionalTensionRecord:
    tension_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    observer_id: str
    rival_id: str
    focus_id: str
    intensity: float
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NarrativeThreadRecord:
    thread_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    status: str
    progress: float
    urgency: float
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NarrativeHookRecord:
    hook_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    status: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CanonicalTurnBundle:
    """All canonical artifacts written by one atomic turn commit."""

    playthrough_id: str
    branch_id: str
    raw_input: str
    base_revision: int
    world_time_start: int
    duration_minutes: int
    world_time_end: int
    turn_run_id: str
    final_narrative: str
    approved_patch: dict[str, Any]
    turn_id: str = field(default_factory=lambda: str(uuid4()))
    parent_turn_id: str | None = None
    normalized_input: str | None = None
    character_states: tuple[CharacterStateRecord, ...] = ()
    events: tuple[EventRecord, ...] = ()
    claims: tuple[KnowledgeClaimRecord, ...] = ()
    canon_facts: tuple[CanonFactRecord, ...] = ()
    claim_links: tuple[ClaimLinkRecord, ...] = ()
    observations: tuple[ObservationRecord, ...] = ()
    beliefs: tuple[BeliefRecord, ...] = ()
    belief_evidence: tuple[BeliefEvidenceRecord, ...] = ()
    relationships: tuple[RelationshipRecord, ...] = ()
    relationship_changes: tuple[RelationshipChangeRecord, ...] = ()
    tensions: tuple[EmotionalTensionRecord, ...] = ()
    threads: tuple[NarrativeThreadRecord, ...] = ()
    hooks: tuple[NarrativeHookRecord, ...] = ()
    suggested_actions: tuple[dict[str, str], ...] = ()
    derived_job_types: tuple[str, ...] = ("snapshot", "summary", "embedding")
    schema_version: int = 1


def snapshot_checksum(payload: Mapping[str, Any]) -> str:
    """Hash canonical JSON so corrupted/stale snapshots are detectable."""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    playthrough_id: str
    branch_id: str
    source_turn_id: str | None
    source_revision: int
    world_clock_minutes: int
    rng_state: dict[str, Any]
    state_payload: dict[str, Any]
    checksum: str
    builder_version: str = "canonical-builder"
    schema_version: int = 1
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)

    @classmethod
    def from_payload(
        cls,
        *,
        playthrough_id: str,
        branch_id: str,
        source_turn_id: str | None,
        source_revision: int,
        world_clock_minutes: int,
        rng_state: dict[str, Any],
        state_payload: dict[str, Any],
        builder_version: str = "canonical-builder",
    ) -> SnapshotRecord:
        return cls(
            playthrough_id=playthrough_id,
            branch_id=branch_id,
            source_turn_id=source_turn_id,
            source_revision=source_revision,
            world_clock_minutes=world_clock_minutes,
            rng_state=dict(rng_state),
            state_payload=dict(state_payload),
            checksum=snapshot_checksum(state_payload),
            builder_version=builder_version,
        )

    def is_valid(self) -> bool:
        return self.checksum == snapshot_checksum(self.state_payload)


@dataclass(frozen=True, slots=True)
class InvariantReport:
    """Read-only result of checking a branch's canonical persistence invariants."""

    branch_id: str
    valid: bool
    violations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DerivedJobRecord:
    id: str
    idempotency_key: str
    job_type: str
    playthrough_id: str
    branch_id: str
    source_turn_id: str | None
    source_revision: int
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    attempts: int = 0
    last_error: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class DerivedArtifactRecord:
    """Discardable, versioned output of a post-commit derived job."""

    id: str
    artifact_type: str
    playthrough_id: str
    branch_id: str
    source_turn_id: str | None
    source_revision: int
    artifact_version: str
    content_hash: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "fresh"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        artifact_type: str,
        playthrough_id: str,
        branch_id: str,
        source_turn_id: str | None,
        source_revision: int,
        artifact_version: str,
        payload: Mapping[str, Any],
        artifact_id: str | None = None,
    ) -> DerivedArtifactRecord:
        if not artifact_type.strip() or not artifact_version.strip():
            raise ValueError("Derived artifact type and version are required.")
        if source_revision < 0:
            raise ValueError("Derived artifact source revision cannot be negative.")
        encoded = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        now = utc_now()
        return cls(
            id=artifact_id or str(uuid4()),
            artifact_type=artifact_type,
            playthrough_id=playthrough_id,
            branch_id=branch_id,
            source_turn_id=source_turn_id,
            source_revision=source_revision,
            artifact_version=artifact_version,
            content_hash=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            payload=dict(payload),
            created_at=now,
            updated_at=now,
        )

    def is_fresh_for(self, source_revision: int, *, artifact_version: str | None = None) -> bool:
        """Only an exact source revision may satisfy a current read."""
        return self.source_revision == source_revision and (artifact_version is None or self.artifact_version == artifact_version)


@dataclass(frozen=True, slots=True)
class OutboxEventRecord:
    id: str
    idempotency_key: str
    event_type: str
    playthrough_id: str
    branch_id: str
    turn_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=utc_now)


__all__ = [
    "BeliefEvidenceRecord",
    "BeliefRecord",
    "BranchRecord",
    "CanonFactRecord",
    "CanonicalTurnBundle",
    "CharacterRecord",
    "CharacterStateRecord",
    "ClaimLinkRecord",
    "DerivedArtifactRecord",
    "DerivedJobRecord",
    "EmotionalTensionRecord",
    "EventRecord",
    "InvariantReport",
    "KnowledgeClaimRecord",
    "NarrativeHookRecord",
    "NarrativeThreadRecord",
    "ObservationRecord",
    "OutboxEventRecord",
    "RelationshipChangeRecord",
    "RelationshipRecord",
    "SnapshotRecord",
    "TurnRecord",
    "WorldRecord",
    "PersistenceError",
    "PersistenceIdempotencyConflictError",
    "PersistenceNotFoundError",
    "PersistenceSnapshotError",
    "PersistenceStaleHeadError",
    "PlaythroughRecord",
    "snapshot_checksum",
    "utc_now",
]
