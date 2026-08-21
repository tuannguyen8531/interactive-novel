"""Deterministic authorization of typed state patches and scene proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

from .clock import ClockPolicy
from .content import ConsentRecord, ContentPolicy, PolicyDecision, SceneSpec, evaluate_scene
from .errors import DomainError, DomainValidationError, GuardRejected
from .events import Belief, Event, Evidence, Observation
from .knowledge import CanonFact, KnowledgeClaim, PredicateRegistry
from .narrative import NarrativeHook, NarrativeThread
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
from .relationships import DEFAULT_RELATIONSHIP_POLICIES, RelationshipDimension
from .state import GameState


@dataclass(frozen=True, slots=True)
class GuardResult:
    """Summary returned after a complete patch has passed all checks."""

    patch_id: str
    operation_count: int
    start_world_time: int
    end_world_time: int


def _fail(code: str, message: str, *, details: dict[str, Any] | None = None) -> NoReturn:
    raise GuardRejected(code, message, details=details)


class DomainGuard:
    """Validate a patch against a snapshot without mutating that snapshot."""

    def __init__(
        self,
        *,
        predicate_registry: PredicateRegistry | None = None,
        clock_policy: ClockPolicy | None = None,
        content_policy: ContentPolicy | None = None,
    ) -> None:
        self.predicate_registry = predicate_registry or PredicateRegistry.default()
        self.clock_policy = clock_policy or ClockPolicy()
        self.content_policy = content_policy

    def validate_patch(self, state: GameState, patch: StatePatch) -> GuardResult:
        if not isinstance(patch, StatePatch):
            _fail("invalid_patch", "Only StatePatch instances can enter the authoritative path.")
        if patch.branch_id != state.branch_id:
            _fail(
                "branch_scope_mismatch",
                "Patch branch does not match the current branch.",
                details={"patch_branch_id": patch.branch_id, "state_branch_id": state.branch_id},
            )
        if patch.base_world_time is not None and patch.base_world_time != state.world_time:
            _fail(
                "stale_patch_base_time",
                "Patch base world time does not match the current state.",
                details={"expected": state.world_time, "received": patch.base_world_time},
            )

        current_time = state.world_time
        known_characters = set(state.characters)
        known_locations = set(state.locations)
        known_relationships = dict(state.relationships)
        known_claims = dict(state.claims)
        known_claim_links = dict(state.claim_links)
        known_facts = dict(state.canon_facts)
        known_events = dict(state.events)
        known_evidence = dict(state.evidence)
        known_observations = dict(state.observations)
        known_beliefs = dict(state.beliefs)
        known_threads = dict(state.threads)
        known_hooks = dict(state.hooks)
        known_scheduled_events = dict(state.scheduled_events)
        known_consents = dict(state.consents)

        for operation_index, operation in enumerate(patch.operations):
            try:
                if not isinstance(operation, StateOperation):
                    _fail(
                        "untyped_operation",
                        "Untyped values cannot mutate authoritative state.",
                        details={"operation_type": type(operation).__name__},
                    )
                if isinstance(operation, AdvanceClock):
                    if (
                        isinstance(operation.duration_minutes, bool)
                        or not isinstance(operation.duration_minutes, int)
                        or operation.duration_minutes < 0
                    ):
                        _fail("invalid_duration", "Clock duration must be a non-negative integer.")
                    if operation.duration_minutes > self.clock_policy.max_turn_duration_minutes:
                        _fail(
                            "duration_over_limit",
                            "Clock duration exceeds the deterministic Guard limit.",
                            details={"maximum": self.clock_policy.max_turn_duration_minutes},
                        )
                    current_time += operation.duration_minutes
                    elapsed_minutes = current_time - state.world_time
                    if elapsed_minutes > self.clock_policy.max_turn_duration_minutes:
                        _fail(
                            "duration_over_limit",
                            "Total clock movement exceeds the deterministic Guard limit.",
                            details={
                                "maximum": self.clock_policy.max_turn_duration_minutes,
                                "received": elapsed_minutes,
                            },
                        )
                elif isinstance(operation, (SetCharacterLocation, SetCharacterCondition, UpdatePsychology)):
                    if operation.character_id not in known_characters:
                        _fail("unknown_character", f"Unknown character: {operation.character_id}.")
                    if isinstance(operation, SetCharacterLocation):
                        if not operation.location_id.strip():
                            _fail("invalid_location", "Character location cannot be empty.")
                        if known_locations and operation.location_id not in known_locations:
                            _fail("unknown_location", f"Unknown location: {operation.location_id}.")
                    elif isinstance(operation, SetCharacterCondition):
                        if not operation.condition.strip():
                            _fail("invalid_condition", "Character condition cannot be empty.")
                    else:
                        character = state.characters[operation.character_id]
                        character.state.psychology.apply_deltas(operation.deltas)
                elif isinstance(operation, ApplyRelationshipDelta):
                    self._validate_relationship(
                        state,
                        operation,
                        known_characters,
                        known_events,
                        known_relationships,
                    )
                elif isinstance(operation, AddKnowledgeClaim):
                    self._validate_claim(state, operation.claim, known_characters, known_events, current_time)
                    if operation.claim.claim_id in known_claims:
                        _fail("duplicate_claim", f"Claim already exists: {operation.claim.claim_id}.")
                    known_claims[operation.claim.claim_id] = operation.claim
                elif isinstance(operation, AddClaimLink):
                    if operation.link.from_claim_id not in known_claims or operation.link.to_claim_id not in known_claims:
                        _fail("claim_link_reference_invalid", "Claim links must reference existing claims.")
                    if operation.link.link_id in known_claim_links:
                        _fail("duplicate_claim_link", f"Claim link already exists: {operation.link.link_id}.")
                    known_claim_links[operation.link.link_id] = operation.link
                elif isinstance(operation, AssertCanonFact):
                    if operation.claim_id not in known_claims:
                        _fail("unknown_claim", f"Unknown claim: {operation.claim_id}.")
                    if not operation.source_event_or_rule.strip():
                        _fail("invalid_canon_source", "Canon fact source is required.")
                    fact_id = operation.fact_id or f"{patch.patch_id}:fact:{operation_index}"
                    if fact_id in known_facts:
                        _fail("duplicate_canon_fact", f"Canon fact already exists: {fact_id}.")
                    known_facts[fact_id] = CanonFact(
                        fact_id=fact_id,
                        claim_id=operation.claim_id,
                        source_event_or_rule=operation.source_event_or_rule,
                        asserted_world_time=current_time,
                        asserted_turn=operation.asserted_turn,
                    )
                elif isinstance(operation, AddEvent):
                    self._validate_event(state, operation.event, known_characters, known_events, current_time)
                    if operation.event.event_id in known_events:
                        _fail("duplicate_event", f"Event already exists: {operation.event.event_id}.")
                    known_events[operation.event.event_id] = operation.event
                elif isinstance(operation, ScheduleEvent):
                    scheduled = operation.scheduled_event
                    if scheduled.scheduled_event_id in known_scheduled_events:
                        _fail("duplicate_scheduled_event", "Scheduled event ID already exists.")
                    if scheduled.due_world_time < current_time:
                        _fail("scheduled_event_in_past", "Scheduled event due time cannot be in the past.")
                    if scheduled.cause_thread_id is not None and scheduled.cause_thread_id not in known_threads:
                        _fail("unknown_thread", "Scheduled event thread cause does not exist.")
                    self._validate_event(state, scheduled.event, known_characters, known_events, scheduled.due_world_time)
                    known_scheduled_events[scheduled.scheduled_event_id] = scheduled
                elif isinstance(operation, MaterializeScheduledEvent):
                    scheduled = known_scheduled_events.get(operation.scheduled_event_id)
                    if scheduled is None:
                        _fail("unknown_scheduled_event", "Scheduled event does not exist.")
                    if scheduled.due_world_time > current_time:
                        _fail("scheduled_event_not_due", "Scheduled event is not due yet.")
                    known_scheduled_events.pop(operation.scheduled_event_id)
                elif isinstance(operation, AddEvidence):
                    self._validate_evidence(state, operation.evidence, known_characters, known_events, known_claims, current_time)
                    if operation.evidence.evidence_id in known_evidence:
                        _fail("duplicate_evidence", f"Evidence already exists: {operation.evidence.evidence_id}.")
                    known_evidence[operation.evidence.evidence_id] = operation.evidence
                elif isinstance(operation, AddObservation):
                    self._validate_observation(
                        state,
                        operation.observation,
                        known_characters,
                        known_events,
                        known_claims,
                        current_time,
                    )
                    if operation.observation.observation_id in known_observations:
                        _fail("duplicate_observation", f"Observation already exists: {operation.observation.observation_id}.")
                    known_observations[operation.observation.observation_id] = operation.observation
                elif isinstance(operation, UpdateBelief):
                    self._validate_belief(
                        state,
                        operation.belief,
                        known_characters,
                        known_claims,
                        known_evidence,
                        current_time,
                    )
                    known_beliefs[operation.belief.belief_id] = operation.belief
                elif isinstance(operation, AddThread):
                    self._validate_thread(state, operation.thread, known_characters)
                    if operation.thread.thread_id in known_threads:
                        _fail("duplicate_thread", f"Thread already exists: {operation.thread.thread_id}.")
                    known_threads[operation.thread.thread_id] = operation.thread
                elif isinstance(operation, TransitionThread):
                    thread = known_threads.get(operation.thread_id)
                    if thread is None:
                        _fail("unknown_thread", f"Unknown thread: {operation.thread_id}.")
                    known_threads[operation.thread_id] = thread.transition(
                        operation.status,
                        progress_delta=operation.progress_delta,
                        world_time=current_time,
                    )
                elif isinstance(operation, AddHook):
                    self._validate_hook(state, operation.hook, known_threads, known_events)
                    if operation.hook.hook_id in known_hooks:
                        _fail("duplicate_hook", f"Hook already exists: {operation.hook.hook_id}.")
                    known_hooks[operation.hook.hook_id] = operation.hook
                elif isinstance(operation, TransitionHook):
                    hook = known_hooks.get(operation.hook_id)
                    if hook is None:
                        _fail("unknown_hook", f"Unknown hook: {operation.hook_id}.")
                    known_hooks[operation.hook_id] = hook.transition(operation.status)
                elif isinstance(operation, ConsentTransition):
                    if operation.participant_id not in known_characters:
                        _fail("unknown_character", f"Unknown consent participant: {operation.participant_id}.")
                    if not operation.scene_id.strip() or not operation.activity_tag.strip():
                        _fail("invalid_consent_scope", "Consent scene and activity are required.")
                    key = (operation.scene_id, operation.participant_id, operation.activity_tag)
                    record = known_consents.get(
                        key,
                        ConsentRecord(
                            scene_id=operation.scene_id,
                            participant_id=operation.participant_id,
                            activity_tag=operation.activity_tag,
                        ),
                    )
                    known_consents[key] = record.transition(operation.next_state, world_time=current_time)
            except GuardRejected:
                raise
            except DomainError as error:
                raise GuardRejected(error.code, error.message, details=error.details) from error
            except (KeyError, TypeError, ValueError) as error:
                raise GuardRejected("invalid_operation", str(error)) from error

        return GuardResult(patch.patch_id, len(patch.operations), state.world_time, current_time)

    def _validate_relationship(
        self,
        state: GameState,
        operation: ApplyRelationshipDelta,
        known_characters: set[str],
        known_events: dict[str, Event],
        known_relationships: dict[tuple[str, str], Any],
    ) -> None:
        if operation.source_id not in known_characters or operation.target_id not in known_characters:
            _fail("unknown_character", "Relationship endpoints must reference existing characters.")
        if operation.source_id == operation.target_id:
            _fail("self_relationship_not_allowed", "Relationship edges must be directed between distinct characters.")
        if operation.dimension not in DEFAULT_RELATIONSHIP_POLICIES:
            _fail("unknown_relationship_dimension", f"Unknown relationship dimension: {operation.dimension}.")
        if operation.dimension == RelationshipDimension.FAMILIARITY:
            _fail("familiarity_is_engine_derived", "Familiarity cannot be directly mutated.")
        if not operation.cause_event_id or operation.cause_event_id not in known_events:
            _fail("relationship_cause_event_required", "Relationship changes require an existing cause event.")
        policy = DEFAULT_RELATIONSHIP_POLICIES[operation.dimension]
        cause_event = known_events[operation.cause_event_id]
        if not policy.allows_event(cause_event.event_type):
            _fail("relationship_cause_event_invalid", "The cause event is not valid for this relationship dimension.")
        if not operation.reason.strip():
            _fail("relationship_reason_required", "Relationship changes require a reason.")
        if not hasattr(operation.provenance, "source_type"):
            _fail("relationship_provenance_required", "Relationship changes require provenance.")
        vector = known_relationships.get((operation.source_id, operation.target_id))
        if vector is None:
            from .relationships import RelationshipVector

            vector = RelationshipVector.zero()
        updated, _, _ = vector.apply_delta(operation.dimension, operation.proposed_delta)
        known_relationships[(operation.source_id, operation.target_id)] = updated

    def _validate_claim(
        self,
        state: GameState,
        claim: KnowledgeClaim,
        known_characters: set[str],
        known_events: dict[str, Event],
        current_time: int,
    ) -> None:
        try:
            self.predicate_registry.validate(claim)
        except DomainValidationError as error:
            _fail(error.code, error.message)
        if not state.scope_is_authorized(claim.branch_scope):
            _fail("claim_branch_scope_invalid", "Claim branch scope is not visible from this branch.")
        if claim.valid_time.start > current_time:
            _fail("claim_future_time", "Claim cannot assert a future world time.")
        definition = self.predicate_registry.get(claim.predicate)
        if definition is None:
            _fail("predicate_not_registered", f"Predicate is not registered: {claim.predicate}.")
        if definition.subject_kind == "character" and claim.subject_id not in known_characters:
            _fail("claim_subject_owner_invalid", "Claim subject must reference a known character.")
        if definition.object_kind == "character" and claim.object_id not in known_characters:
            _fail("claim_object_reference_invalid", "Claim object must reference a known character.")
        if definition.object_kind == "event" and claim.object_id not in known_events:
            _fail("claim_object_reference_invalid", "Claim object must reference a known event.")

    def _validate_event(
        self,
        state: GameState,
        event: Event,
        known_characters: set[str],
        known_events: dict[str, Event],
        current_time: int,
    ) -> None:
        if not state.scope_is_authorized(event.branch_scope):
            _fail("event_branch_scope_invalid", "Event branch scope is not visible from this branch.")
        if event.world_time > current_time:
            _fail("event_future_time", "Event cannot be materialized in the future.")
        participant_ids = set(event.actor_ids) | set(event.target_ids) | set(event.witness_ids)
        if participant_ids - known_characters:
            _fail("event_participant_reference_invalid", "Event references an unknown character.")
        if event.location_id is not None and state.locations and event.location_id not in state.locations:
            _fail("unknown_location", f"Unknown event location: {event.location_id}.")
        if set(event.cause_event_ids) - set(known_events):
            _fail("event_cause_reference_invalid", "Event references an unknown cause event.")
        if any(known_events[event_id].world_time > event.world_time for event_id in event.cause_event_ids):
            _fail("event_cause_time_invalid", "An event cannot be caused by a future event.")

    def _validate_evidence(
        self,
        state: GameState,
        evidence: Evidence,
        known_characters: set[str],
        known_events: dict[str, Event],
        known_claims: dict[str, KnowledgeClaim],
        current_time: int,
    ) -> None:
        if evidence.owner_id not in known_characters:
            _fail("evidence_owner_invalid", "Evidence owner must be a known character.")
        source_event = known_events.get(evidence.source_event_id)
        claim = known_claims.get(evidence.claim_id)
        if source_event is None or claim is None:
            _fail("evidence_source_invalid", "Evidence must reference an existing event and claim.")
        if not state.scope_is_authorized(evidence.branch_scope):
            _fail("evidence_branch_scope_invalid", "Evidence branch scope is not visible from this branch.")
        if evidence.world_time > current_time:
            _fail("evidence_future_time", "Evidence cannot be created in the future.")
        if source_event.world_time > evidence.world_time or claim.valid_time.start > evidence.world_time:
            _fail("evidence_time_invalid", "Evidence cannot precede its source event or claim validity.")

    def _validate_observation(
        self,
        state: GameState,
        observation: Observation,
        known_characters: set[str],
        known_events: dict[str, Event],
        known_claims: dict[str, KnowledgeClaim],
        current_time: int,
    ) -> None:
        if observation.observer_id not in known_characters:
            _fail("observation_owner_or_source_invalid", "Observation observer must be a known character.")
        event = known_events.get(observation.source_event_id)
        claim = known_claims.get(observation.observed_claim_id)
        if event is None or claim is None:
            _fail("observation_owner_or_source_invalid", "Observation source event and claim must exist.")
        if not state.scope_is_authorized(observation.branch_scope):
            _fail("observation_branch_scope_invalid", "Observation branch scope is not visible from this branch.")
        if observation.world_time > current_time:
            _fail("observation_future_time", "Observation cannot be created in the future.")
        if event.world_time > observation.world_time or claim.valid_time.start > observation.world_time:
            _fail("observation_time_invalid", "Observation cannot precede its source event or claim validity.")
        if observation.method in {"saw", "heard"} and observation.observer_id not in {
            *event.actor_ids,
            *event.target_ids,
            *event.witness_ids,
        }:
            _fail("observation_owner_or_source_invalid", "Observer was not authorized to witness the source event.")

    def _validate_belief(
        self,
        state: GameState,
        belief: Belief,
        known_characters: set[str],
        known_claims: dict[str, KnowledgeClaim],
        known_evidence: dict[str, Evidence],
        current_time: int,
    ) -> None:
        claim = known_claims.get(belief.claim_id)
        if belief.believer_id not in known_characters or claim is None:
            _fail("belief_owner_or_claim_invalid", "Belief must reference a known believer and claim.")
        if not state.scope_is_authorized(belief.branch_scope):
            _fail("belief_branch_scope_invalid", "Belief branch scope is not visible from this branch.")
        if belief.world_time > current_time:
            _fail("belief_future_time", "Belief cannot be created in the future.")
        if claim.valid_time.start > belief.world_time:
            _fail("future_claim_not_authorized", "Belief cannot be formed before the claim becomes valid.")
        evidence_ids = (*belief.evidence_ids, *belief.counter_evidence_ids)
        for evidence_id in evidence_ids:
            evidence = known_evidence.get(evidence_id)
            if evidence is None or evidence.owner_id != belief.believer_id:
                _fail("belief_evidence_owner_invalid", "Belief evidence must belong to the believer.")
            if evidence.world_time > belief.world_time:
                _fail("future_evidence_not_authorized", "Belief cannot use evidence from its future.")

    def _validate_thread(self, state: GameState, thread: NarrativeThread, known_characters: set[str]) -> None:
        if not state.scope_is_authorized(thread.branch_scope):
            _fail("thread_branch_scope_invalid", "Thread branch scope is not visible from this branch.")
        if set(thread.participant_ids) - known_characters:
            _fail("thread_participant_reference_invalid", "Thread references an unknown character.")

    def _validate_hook(
        self,
        state: GameState,
        hook: NarrativeHook,
        known_threads: dict[str, NarrativeThread],
        known_events: dict[str, Event],
    ) -> None:
        if not state.scope_is_authorized(hook.branch_scope):
            _fail("hook_branch_scope_invalid", "Hook branch scope is not visible from this branch.")
        if hook.related_thread_id is not None and hook.related_thread_id not in known_threads:
            _fail("hook_thread_reference_invalid", "Hook references an unknown thread.")
        if hook.related_event_id is not None and hook.related_event_id not in known_events:
            _fail("hook_event_reference_invalid", "Hook references an unknown event.")

    def validate_scene(self, state: GameState, scene: SceneSpec) -> PolicyDecision:
        policy = state.policy or self.content_policy
        if policy is None:
            _fail("content_policy_missing", "A content policy is required before scene authorization.")
        decision = evaluate_scene(policy, scene)
        if decision.decision.value == "deny":
            _fail(
                decision.reason_code or "content_policy_denied",
                "Scene rejected by deterministic content policy.",
                details={
                    "reason_codes": decision.reason_codes,
                    "participant_ages": dict(decision.participant_ages),
                    "evaluated_world_time": decision.evaluated_world_time,
                },
            )
        return decision


__all__ = ["DomainGuard", "GuardResult"]
