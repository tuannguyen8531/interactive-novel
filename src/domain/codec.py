"""JSON-safe codecs for canonical patches and derived state snapshots.

The codec is deliberately domain-owned: persistence may store the result, but
it does not learn how to reconstruct authoritative operations itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from .characters import Character, CharacterProfile, CharacterState
from .content import ConsentRecord, ConsentState, ContentPolicy
from .events import Belief, Event, Evidence, Observation, ScheduledEvent
from .knowledge import CanonFact, ClaimLink, KnowledgeClaim
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
from .psychology import PsychologicalState
from .relationships import RelationshipChange, RelationshipVector
from .state import GameState
from .values import Provenance, TimeRange


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(item) for item in value]
    return value


def _provenance(value: Mapping[str, Any] | None) -> Provenance | None:
    return None if value is None else Provenance(**dict(value))


def _time_range(value: Mapping[str, Any]) -> TimeRange:
    return TimeRange(start=int(value["start"]), end=None if value.get("end") is None else int(value["end"]))


def _claim(value: Mapping[str, Any]) -> KnowledgeClaim:
    data = dict(value)
    data.pop("normalized_fingerprint", None)
    data["valid_time"] = _time_range(data["valid_time"])
    data["provenance"] = _provenance(data.get("provenance"))
    return KnowledgeClaim(**data)


def _event(value: Mapping[str, Any]) -> Event:
    data = dict(value)
    data["provenance"] = _provenance(data.get("provenance"))
    return Event(**data)


def _scheduled_event(value: Mapping[str, Any]) -> ScheduledEvent:
    data = dict(value)
    data["event"] = _event(data["event"])
    return ScheduledEvent(**data)


def _evidence(value: Mapping[str, Any]) -> Evidence:
    data = dict(value)
    data["provenance"] = _provenance(data.get("provenance"))
    return Evidence(**data)


def _observation(value: Mapping[str, Any]) -> Observation:
    data = dict(value)
    data["provenance"] = _provenance(data.get("provenance"))
    return Observation(**data)


def _belief(value: Mapping[str, Any]) -> Belief:
    data = dict(value)
    data["provenance"] = _provenance(data.get("provenance"))
    return Belief(**data)


def _fact(value: Mapping[str, Any]) -> CanonFact:
    return CanonFact(**dict(value))


def _claim_link(value: Mapping[str, Any]) -> ClaimLink:
    return ClaimLink(**dict(value))


def _thread(value: Mapping[str, Any]) -> NarrativeThread:
    return NarrativeThread(**dict(value))


def _hook(value: Mapping[str, Any]) -> NarrativeHook:
    data = dict(value)
    data["payoff_window"] = _time_range(data["payoff_window"])
    return NarrativeHook(**data)


def patch_to_payload(patch: StatePatch) -> dict[str, Any]:
    """Encode a typed patch with an operation discriminator for replay."""
    operations = []
    for operation in patch.operations:
        if not isinstance(operation, StateOperation):
            raise TypeError(f"Cannot encode untyped operation: {type(operation).__name__}")
        operations.append({"operation_type": operation.operation_type, "payload": _jsonable(operation)})
    return {
        "patch_id": patch.patch_id,
        "branch_id": patch.branch_id,
        "base_world_time": patch.base_world_time,
        "operations": operations,
    }


def patch_from_payload(payload: Mapping[str, Any]) -> StatePatch:
    """Reconstruct the typed operation objects used by the domain engine."""
    operations: list[object] = []
    constructors = {
        "advance_clock": lambda data: AdvanceClock(**data),
        "set_character_location": lambda data: SetCharacterLocation(**data),
        "set_character_condition": lambda data: SetCharacterCondition(**data),
        "update_psychology": lambda data: UpdatePsychology(**data),
        "relationship_delta": lambda data: ApplyRelationshipDelta(**{**data, "provenance": _provenance(data.get("provenance"))}),
        "add_knowledge_claim": lambda data: AddKnowledgeClaim(_claim(data["claim"])),
        "add_claim_link": lambda data: AddClaimLink(_claim_link(data["link"])),
        "assert_canon_fact": lambda data: AssertCanonFact(**data),
        "add_event": lambda data: AddEvent(_event(data["event"])),
        "schedule_event": lambda data: ScheduleEvent(_scheduled_event(data["scheduled_event"])),
        "materialize_scheduled_event": lambda data: MaterializeScheduledEvent(**data),
        "add_evidence": lambda data: AddEvidence(_evidence(data["evidence"])),
        "add_observation": lambda data: AddObservation(_observation(data["observation"])),
        "update_belief": lambda data: UpdateBelief(_belief(data["belief"])),
        "add_thread": lambda data: AddThread(_thread(data["thread"])),
        "transition_thread": lambda data: TransitionThread(**data),
        "add_hook": lambda data: AddHook(_hook(data["hook"])),
        "transition_hook": lambda data: TransitionHook(**data),
        "consent_transition": lambda data: ConsentTransition(**data),
    }
    for item in payload.get("operations", []):
        operation_type = str(item["operation_type"])
        try:
            operations.append(constructors[operation_type](dict(item["payload"])))
        except KeyError as error:
            raise ValueError(f"Unknown state operation type: {operation_type}") from error
    return StatePatch(
        operations=tuple(operations),
        branch_id=str(payload["branch_id"]),
        base_world_time=payload.get("base_world_time"),
        patch_id=str(payload["patch_id"]),
    )


def state_to_payload(state: GameState) -> dict[str, Any]:
    """Encode canonical in-memory state for a derived snapshot."""
    return {
        "world_id": state.world_id,
        "playthrough_id": state.playthrough_id,
        "branch_id": state.branch_id,
        "clock_minutes": state.world_time,
        "branch_ancestry": list(state.branch_ancestry),
        "characters": {character_id: _jsonable(character) for character_id, character in state.characters.items()},
        "locations": sorted(state.locations),
        "relationships": [
            {"source_id": source_id, "target_id": target_id, "values": _jsonable(vector.values)}
            for (source_id, target_id), vector in state.relationships.items()
        ],
        "relationship_changes": [_jsonable(change) for change in state.relationship_changes],
        "claims": [_jsonable(claim) for claim in state.claims.values()],
        "claim_links": [_jsonable(link) for link in state.claim_links.values()],
        "canon_facts": [_jsonable(fact) for fact in state.canon_facts.values()],
        "events": [_jsonable(event) for event in state.events.values()],
        "scheduled_events": [_jsonable(event) for event in state.scheduled_events.values()],
        "evidence": [_jsonable(item) for item in state.evidence.values()],
        "observations": [_jsonable(item) for item in state.observations.values()],
        "beliefs": [_jsonable(item) for item in state.beliefs.values()],
        "threads": [_jsonable(item) for item in state.threads.values()],
        "hooks": [_jsonable(item) for item in state.hooks.values()],
        "consents": [_jsonable(item) for item in state.consents.values()],
        "policy": _jsonable(state.policy) if state.policy is not None else None,
        "metadata": _jsonable(state.metadata),
    }


def state_from_payload(payload: Mapping[str, Any]) -> GameState:
    """Decode a snapshot payload without importing persistence/framework code."""
    characters: dict[str, Character] = {}
    for character_id, value in payload.get("characters", {}).items():
        profile_data = dict(value["profile"])
        state_data = dict(value["state"])
        state_data["psychology"] = PsychologicalState(**state_data["psychology"])
        characters[str(character_id)] = Character(CharacterProfile(**profile_data), CharacterState(**state_data))

    state = GameState.empty(
        world_id=str(payload["world_id"]),
        playthrough_id=str(payload["playthrough_id"]),
        branch_id=str(payload["branch_id"]),
        world_time=int(payload.get("clock_minutes", 0)),
    )
    state.branch_ancestry = tuple(payload.get("branch_ancestry", [state.branch_id]))
    state.characters = characters
    state.locations = set(payload.get("locations", []))
    state.relationships = {
        (str(item["source_id"]), str(item["target_id"])): RelationshipVector(item.get("values", {}))
        for item in payload.get("relationships", [])
    }
    state.relationship_changes = [
        RelationshipChange(**{**dict(item), "provenance": _provenance(item.get("provenance"))})
        for item in payload.get("relationship_changes", [])
    ]
    state.claims = {claim.claim_id: claim for claim in (_claim(item) for item in payload.get("claims", []))}
    state.claim_links = {link.link_id: link for link in (_claim_link(item) for item in payload.get("claim_links", []))}
    state.canon_facts = {fact.fact_id: fact for fact in (_fact(item) for item in payload.get("canon_facts", []))}
    state.events = {event.event_id: event for event in (_event(item) for item in payload.get("events", []))}
    state.scheduled_events = {
        item.scheduled_event_id: item for item in (_scheduled_event(value) for value in payload.get("scheduled_events", []))
    }
    state.evidence = {item.evidence_id: item for item in (_evidence(item) for item in payload.get("evidence", []))}
    state.observations = {item.observation_id: item for item in (_observation(item) for item in payload.get("observations", []))}
    state.beliefs = {item.belief_id: item for item in (_belief(item) for item in payload.get("beliefs", []))}
    state.threads = {item.thread_id: item for item in (_thread(item) for item in payload.get("threads", []))}
    state.hooks = {item.hook_id: item for item in (_hook(item) for item in payload.get("hooks", []))}
    state.consents = {
        (item.scene_id, item.participant_id, item.activity_tag): item
        for item in (
            ConsentRecord(**{**dict(value), "state": ConsentState(value["state"])}) for value in payload.get("consents", [])
        )
    }
    policy = payload.get("policy")
    if policy is not None:
        state.policy = ContentPolicy.from_mapping(policy, player_overrides=policy.get("player_overrides"))
    state.metadata = dict(payload.get("metadata", {}))
    return state


__all__ = ["patch_from_payload", "patch_to_payload", "state_from_payload", "state_to_payload"]
