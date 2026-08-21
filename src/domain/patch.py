"""Typed state operations proposed to, and accepted by, the domain Guard."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar

from .content import ConsentState
from .events import Belief, Event, Evidence, Observation, ScheduledEvent
from .knowledge import ClaimLink, KnowledgeClaim
from .narrative import HookStatus, NarrativeHook, NarrativeThread, ThreadStatus
from .values import Provenance


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class StateOperation:
    """Marker base for the only objects that may mutate authoritative state."""

    operation_type: ClassVar[str] = "state_operation"


@dataclass(frozen=True, slots=True)
class AdvanceClock(StateOperation):
    duration_minutes: int
    operation_type: ClassVar[str] = "advance_clock"


@dataclass(frozen=True, slots=True)
class SetCharacterLocation(StateOperation):
    character_id: str
    location_id: str
    operation_type: ClassVar[str] = "set_character_location"


@dataclass(frozen=True, slots=True)
class SetCharacterCondition(StateOperation):
    character_id: str
    condition: str
    operation_type: ClassVar[str] = "set_character_condition"


@dataclass(frozen=True, slots=True)
class UpdatePsychology(StateOperation):
    character_id: str
    deltas: dict[str, float] = field(default_factory=dict)
    operation_type: ClassVar[str] = "update_psychology"


@dataclass(frozen=True, slots=True)
class ApplyRelationshipDelta(StateOperation):
    source_id: str
    target_id: str
    dimension: str
    proposed_delta: float
    cause_event_id: str
    reason: str
    provenance: Provenance
    operation_type: ClassVar[str] = "relationship_delta"


@dataclass(frozen=True, slots=True)
class AddKnowledgeClaim(StateOperation):
    claim: KnowledgeClaim
    operation_type: ClassVar[str] = "add_knowledge_claim"


@dataclass(frozen=True, slots=True)
class AddClaimLink(StateOperation):
    link: ClaimLink
    operation_type: ClassVar[str] = "add_claim_link"


@dataclass(frozen=True, slots=True)
class AssertCanonFact(StateOperation):
    claim_id: str
    fact_id: str | None = None
    source_event_or_rule: str = "guarded_state_operation"
    asserted_turn: str | None = None
    operation_type: ClassVar[str] = "assert_canon_fact"


@dataclass(frozen=True, slots=True)
class AddEvent(StateOperation):
    event: Event
    operation_type: ClassVar[str] = "add_event"


@dataclass(frozen=True, slots=True)
class ScheduleEvent(StateOperation):
    scheduled_event: ScheduledEvent
    operation_type: ClassVar[str] = "schedule_event"


@dataclass(frozen=True, slots=True)
class MaterializeScheduledEvent(StateOperation):
    scheduled_event_id: str
    operation_type: ClassVar[str] = "materialize_scheduled_event"


@dataclass(frozen=True, slots=True)
class AddEvidence(StateOperation):
    evidence: Evidence
    operation_type: ClassVar[str] = "add_evidence"


@dataclass(frozen=True, slots=True)
class AddObservation(StateOperation):
    observation: Observation
    operation_type: ClassVar[str] = "add_observation"


@dataclass(frozen=True, slots=True)
class UpdateBelief(StateOperation):
    belief: Belief
    operation_type: ClassVar[str] = "update_belief"


@dataclass(frozen=True, slots=True)
class AddThread(StateOperation):
    thread: NarrativeThread
    operation_type: ClassVar[str] = "add_thread"


@dataclass(frozen=True, slots=True)
class TransitionThread(StateOperation):
    thread_id: str
    status: ThreadStatus
    progress_delta: float = 0.0
    operation_type: ClassVar[str] = "transition_thread"


@dataclass(frozen=True, slots=True)
class AddHook(StateOperation):
    hook: NarrativeHook
    operation_type: ClassVar[str] = "add_hook"


@dataclass(frozen=True, slots=True)
class TransitionHook(StateOperation):
    hook_id: str
    status: HookStatus
    operation_type: ClassVar[str] = "transition_hook"


@dataclass(frozen=True, slots=True)
class ConsentTransition(StateOperation):
    scene_id: str
    participant_id: str
    activity_tag: str
    next_state: ConsentState
    operation_type: ClassVar[str] = "consent_transition"


@dataclass(frozen=True, slots=True)
class StatePatch:
    """A branch-scoped, ordered list of typed operations."""

    operations: tuple[object, ...]
    branch_id: str
    base_world_time: int | None = None
    patch_id: str = field(default_factory=_new_id)

    def __post_init__(self) -> None:
        object.__setattr__(self, "operations", tuple(self.operations))
        if not self.patch_id.strip() or not self.branch_id.strip():
            raise ValueError("StatePatch requires patch and branch IDs.")
        if self.base_world_time is not None and (isinstance(self.base_world_time, bool) or self.base_world_time < 0):
            raise ValueError("StatePatch base world time must be non-negative.")

    @classmethod
    def from_operations(
        cls,
        operations: Sequence[object],
        *,
        branch_id: str,
        base_world_time: int | None = None,
        patch_id: str | None = None,
    ) -> StatePatch:
        values: dict[str, Any] = {"operations": tuple(operations), "branch_id": branch_id, "base_world_time": base_world_time}
        if patch_id is not None:
            values["patch_id"] = patch_id
        return cls(**values)


# Short name used in some callers and in the domain model prose.
RelationshipDelta = ApplyRelationshipDelta


__all__ = [
    "AddEvent",
    "AddEvidence",
    "AddHook",
    "AddClaimLink",
    "AddKnowledgeClaim",
    "AddObservation",
    "AddThread",
    "AdvanceClock",
    "ApplyRelationshipDelta",
    "AssertCanonFact",
    "ConsentTransition",
    "MaterializeScheduledEvent",
    "ScheduleEvent",
    "RelationshipDelta",
    "SetCharacterCondition",
    "SetCharacterLocation",
    "StateOperation",
    "StatePatch",
    "TransitionHook",
    "TransitionThread",
    "UpdateBelief",
    "UpdatePsychology",
]
