"""Pure application of guarded patches with deterministic replay support."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .clock import InWorldClock
from .content import ConsentRecord
from .events import Event
from .guard import DomainGuard
from .knowledge import CanonFact
from .patch import (
    AddClaimLink,
    AddEvent,
    AddEvidence,
    AddHook,
    AddKnowledgeClaim,
    AddObservation,
    AddThread,
    AdvanceClock,
    ApplyRelationshipDelta,
    AssertCanonFact,
    ConsentTransition,
    MaterializeScheduledEvent,
    ScheduleEvent,
    SetCharacterCondition,
    SetCharacterLocation,
    StateOperation,
    StatePatch,
    TransitionHook,
    TransitionThread,
    UpdateBelief,
    UpdatePsychology,
)
from .relationships import RelationshipChange, RelationshipVector, derive_familiarity
from .state import GameState


def _fact_id(patch: StatePatch, operation_index: int, operation: AssertCanonFact) -> str:
    return operation.fact_id or f"{patch.patch_id}:fact:{operation_index}"


def _json_state(value: object) -> object:
    if isinstance(value, tuple):
        return [_json_state(item) for item in value]
    if isinstance(value, list):
        return [_json_state(item) for item in value]
    return value


def _tuple_state(value: object) -> object:
    if isinstance(value, list):
        return tuple(_tuple_state(item) for item in value)
    return value


@dataclass(slots=True)
class DomainRuntime:
    """Explicitly injectable nondeterminism boundary for simulation rules."""

    rng: random.Random
    clock_factory: Callable[[int], InWorldClock]

    @classmethod
    def create(
        cls,
        *,
        rng: random.Random | None = None,
        clock_factory: Callable[[int], InWorldClock] | None = None,
    ) -> DomainRuntime:
        return cls(rng=rng or random.Random(), clock_factory=clock_factory or InWorldClock)


@dataclass(frozen=True, slots=True)
class AppliedPatch:
    """Before/after snapshots make revert and replay explicit and lossless."""

    patch: StatePatch
    before: GameState
    after: GameState

    @property
    def state(self) -> GameState:
        return self.after

    def __getattr__(self, name: str) -> object:
        """Allow simple callers to inspect the resulting state directly."""
        return getattr(self.after, name)


class DomainEngine:
    """Guard, apply and replay domain operations without an LLM or database."""

    def __init__(
        self,
        *,
        guard: DomainGuard | None = None,
        rng: random.Random | None = None,
        clock_factory: Callable[[int], InWorldClock] | None = None,
    ) -> None:
        self.guard = guard or DomainGuard()
        self.runtime = DomainRuntime.create(rng=rng, clock_factory=clock_factory)

    @property
    def rng(self) -> random.Random:
        return self.runtime.rng

    def apply(self, state: GameState, patch: StatePatch) -> AppliedPatch:
        """Validate then apply a patch to a copy, leaving the input untouched."""
        self._restore_rng(state)
        self.guard.validate_patch(state, patch)
        before = state.copy()
        working = state.copy()
        for operation_index, operation in enumerate(patch.operations):
            self._apply_operation(working, patch, operation_index, operation)
        self._refresh_familiarity(working)
        self._store_rng(working)
        return AppliedPatch(patch=patch, before=before, after=working)

    def random_int(self, state: GameState, lower: int, upper: int) -> int:
        """Consume a seeded random rule and persist its state on the domain snapshot."""
        if lower > upper:
            raise ValueError("Random lower bound cannot exceed upper bound.")
        self._restore_rng(state)
        value = self.runtime.rng.randint(lower, upper)
        self._store_rng(state)
        return value

    def _restore_rng(self, state: GameState) -> None:
        metadata: Mapping[str, object] = state.metadata
        saved = metadata.get("rng_state")
        if saved:
            restored = _tuple_state(saved)
            if not isinstance(restored, tuple):
                raise ValueError("Serialized RNG state must be a tuple-shaped value.")
            self.runtime.rng.setstate(restored)
        elif metadata.get("rng_seed") is not None:
            self.runtime.rng.seed(str(metadata["rng_seed"]))

    def _store_rng(self, state: GameState) -> None:
        if "rng_seed" in state.metadata or "rng_state" in state.metadata:
            state.metadata["rng_state"] = _json_state(self.runtime.rng.getstate())

    @staticmethod
    def _refresh_familiarity(state: GameState) -> None:
        """Derive directed familiarity from shared canonical events and elapsed world time."""
        shared_counts: dict[tuple[str, str], int] = {}
        meaningful_counts: dict[tuple[str, str], int] = {}
        for event in state.events.values():
            participants = tuple(dict.fromkeys((*event.actor_ids, *event.target_ids, *event.witness_ids)))
            for source_id in participants:
                for target_id in participants:
                    if source_id == target_id:
                        continue
                    key = (source_id, target_id)
                    shared_counts[key] = shared_counts.get(key, 0) + 1
                    if event.salience >= 0.5 or event.emotional_intensity >= 0.5:
                        meaningful_counts[key] = meaningful_counts.get(key, 0) + 1
        for key in set(state.relationships) | set(shared_counts):
            vector = state.relationships.get(key, RelationshipVector.zero())
            familiarity = derive_familiarity(
                shared_scene_count=shared_counts.get(key, 0),
                meaningful_event_count=meaningful_counts.get(key, 0),
                elapsed_minutes=state.world_time,
            )
            state.relationships[key] = vector.with_derived_familiarity(familiarity)

    def revert(self, applied: AppliedPatch) -> GameState:
        """Return the exact pre-patch snapshot."""
        return applied.before.copy()

    def replay(self, initial_state: GameState, patches: Iterable[StatePatch]) -> GameState:
        """Replay the ordered canonical patch stream from a clean snapshot."""
        current = initial_state.copy()
        for patch in patches:
            current = self.apply(current, patch).after
        return current

    @staticmethod
    def due_scheduled_operations(state: GameState) -> tuple[MaterializeScheduledEvent, ...]:
        """Return due schedules in stable order; no autonomous world tick is performed."""
        return tuple(
            MaterializeScheduledEvent(item.scheduled_event_id)
            for item in sorted(state.scheduled_events.values(), key=lambda item: (item.due_world_time, item.scheduled_event_id))
            if item.due_world_time <= state.world_time
        )

    def _apply_operation(self, state: GameState, patch: StatePatch, operation_index: int, operation: object) -> None:
        if isinstance(operation, AdvanceClock):
            state.clock = self.runtime.clock_factory(state.world_time + operation.duration_minutes)
        elif isinstance(operation, SetCharacterLocation):
            character = state.characters[operation.character_id]
            state.characters[operation.character_id] = character.with_state(location_id=operation.location_id)
        elif isinstance(operation, SetCharacterCondition):
            character = state.characters[operation.character_id]
            state.characters[operation.character_id] = character.with_state(physical_condition=operation.condition)
        elif isinstance(operation, UpdatePsychology):
            character = state.characters[operation.character_id]
            psychology = character.state.psychology.apply_deltas(operation.deltas)
            state.characters[operation.character_id] = character.with_state(psychology=psychology)
        elif isinstance(operation, ApplyRelationshipDelta):
            key = (operation.source_id, operation.target_id)
            vector = state.relationships.get(key, RelationshipVector.zero())
            updated, validated_delta, after = vector.apply_delta(operation.dimension, operation.proposed_delta)
            state.relationships[key] = updated
            state.relationship_changes.append(
                RelationshipChange(
                    source_id=operation.source_id,
                    target_id=operation.target_id,
                    dimension=operation.dimension,
                    before=vector.value(operation.dimension),
                    proposed_delta=operation.proposed_delta,
                    validated_delta=validated_delta,
                    after=after,
                    cause_event_id=operation.cause_event_id,
                    reason=operation.reason,
                    provenance=operation.provenance,
                )
            )
        elif isinstance(operation, AddKnowledgeClaim):
            state.claims[operation.claim.claim_id] = operation.claim
        elif isinstance(operation, AddClaimLink):
            state.claim_links[operation.link.link_id] = operation.link
        elif isinstance(operation, AssertCanonFact):
            fact_id = _fact_id(patch, operation_index, operation)
            state.canon_facts[fact_id] = CanonFact(
                fact_id=fact_id,
                claim_id=operation.claim_id,
                source_event_or_rule=operation.source_event_or_rule,
                asserted_world_time=state.world_time,
                asserted_turn=operation.asserted_turn,
            )
        elif isinstance(operation, AddEvent):
            state.events[operation.event.event_id] = operation.event
        elif isinstance(operation, ScheduleEvent):
            state.scheduled_events[operation.scheduled_event.scheduled_event_id] = operation.scheduled_event
        elif isinstance(operation, MaterializeScheduledEvent):
            scheduled = state.scheduled_events.pop(operation.scheduled_event_id)
            event = scheduled.event
            state.events[event.event_id] = Event(
                event_id=event.event_id,
                event_type=event.event_type,
                world_time=state.world_time,
                branch_scope=event.branch_scope,
                location_id=event.location_id,
                actor_ids=event.actor_ids,
                target_ids=event.target_ids,
                witness_ids=event.witness_ids,
                payload=dict(event.payload),
                salience=event.salience,
                emotional_intensity=event.emotional_intensity,
                cause_event_ids=(*event.cause_event_ids, f"scheduled:{scheduled.scheduled_event_id}"),
                turn_id=event.turn_id,
                provenance=event.provenance,
            )
        elif isinstance(operation, AddEvidence):
            state.evidence[operation.evidence.evidence_id] = operation.evidence
        elif isinstance(operation, AddObservation):
            state.observations[operation.observation.observation_id] = operation.observation
        elif isinstance(operation, UpdateBelief):
            state.beliefs[operation.belief.belief_id] = operation.belief
        elif isinstance(operation, AddThread):
            state.threads[operation.thread.thread_id] = operation.thread
        elif isinstance(operation, TransitionThread):
            thread = state.threads[operation.thread_id]
            state.threads[operation.thread_id] = thread.transition(
                operation.status,
                progress_delta=operation.progress_delta,
                world_time=state.world_time,
            )
        elif isinstance(operation, AddHook):
            state.hooks[operation.hook.hook_id] = operation.hook
        elif isinstance(operation, TransitionHook):
            hook = state.hooks[operation.hook_id]
            state.hooks[operation.hook_id] = hook.transition(operation.status)
        elif isinstance(operation, ConsentTransition):
            key = (operation.scene_id, operation.participant_id, operation.activity_tag)
            record = state.consents.get(
                key,
                ConsentRecord(
                    scene_id=operation.scene_id,
                    participant_id=operation.participant_id,
                    activity_tag=operation.activity_tag,
                ),
            )
            state.consents[key] = record.transition(operation.next_state, world_time=state.world_time)
        elif not isinstance(operation, StateOperation):
            # The Guard is the authority, but keeping this branch explicit makes
            # direct/private calls fail closed as well.
            raise TypeError(f"Untyped operation at index {operation_index}: {type(operation).__name__}")


def apply_patch(state: GameState, patch: StatePatch, *, engine: DomainEngine | None = None) -> GameState:
    """Convenience function returning the accepted after-state."""
    return (engine or DomainEngine()).apply(state, patch).after


def revert_patch(applied: AppliedPatch, *, engine: DomainEngine | None = None) -> GameState:
    """Convenience function restoring the before-state snapshot."""
    return (engine or DomainEngine()).revert(applied)


def replay_patches(
    initial_state: GameState,
    patches: Iterable[StatePatch],
    *,
    engine: DomainEngine | None = None,
) -> GameState:
    """Convenience function for deterministic patch replay."""
    return (engine or DomainEngine()).replay(initial_state, patches)


__all__ = [
    "AppliedPatch",
    "DomainEngine",
    "DomainRuntime",
    "apply_patch",
    "replay_patches",
    "revert_patch",
]
