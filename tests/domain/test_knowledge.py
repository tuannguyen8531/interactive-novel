from __future__ import annotations

import pytest

from src.domain.characters import Character, CharacterProfile
from src.domain.errors import GuardRejected
from src.domain.events import Belief, Event, Evidence, Observation
from src.domain.guard import DomainGuard
from src.domain.knowledge import ClaimLink, ClaimLinkKind, KnowledgeClaim
from src.domain.patch import AddClaimLink, AddEvent, AddEvidence, AddKnowledgeClaim, AddObservation, StatePatch, UpdateBelief
from src.domain.state import GameState
from src.domain.values import TimeRange


def _characters() -> dict[str, Character]:
    return {
        character_id: Character(CharacterProfile(character_id, character_id.title(), 18))
        for character_id in ("alice", "bob", "yuki", "akira")
    }


def _state(world_time: int = 100) -> GameState:
    state = GameState.empty(branch_id="root", world_time=world_time, policy=None)
    state.characters = _characters()
    return state


def test_normalized_claim_fingerprint_ignores_mapping_key_order() -> None:
    first = KnowledgeClaim(
        subject_id="yuki",
        predicate="public_fact",
        typed_value={"preference": "tea", "strength": 0.7},
        qualifiers={"context": "clubroom", "location": "school"},
        valid_time=TimeRange(10, 20),
        branch_scope="root",
    )
    second = KnowledgeClaim(
        subject_id="yuki",
        predicate="public_fact",
        typed_value={"strength": 0.7, "preference": "tea"},
        qualifiers={"location": "school", "context": "clubroom"},
        valid_time=TimeRange(10, 20),
        branch_scope="root",
    )

    assert first.normalized_fingerprint == second.normalized_fingerprint


def test_unknown_predicate_and_untyped_mutation_are_rejected() -> None:
    state = _state()
    unknown = KnowledgeClaim(
        subject_id="yuki",
        predicate="probably_has_a_crush",
        object_id="akira",
        branch_scope="root",
    )
    guard = DomainGuard()

    with pytest.raises(GuardRejected) as unknown_error:
        guard.validate_patch(state, StatePatch((AddKnowledgeClaim(unknown),), branch_id="root", base_world_time=100))
    assert unknown_error.value.code == "predicate_not_registered"

    with pytest.raises(GuardRejected) as untyped_error:
        guard.validate_patch(state, StatePatch(({"kind": "narrative_text"},), branch_id="root", base_world_time=100))
    assert untyped_error.value.code == "untyped_operation"


def test_claim_scope_time_and_link_referential_integrity_are_guarded() -> None:
    state = _state()
    valid = KnowledgeClaim(subject_id="yuki", predicate="public_fact", typed_value="known", branch_scope="root")
    sibling = KnowledgeClaim(subject_id="yuki", predicate="public_fact", typed_value="leak", branch_scope="sibling")
    future = KnowledgeClaim(
        subject_id="yuki",
        predicate="public_fact",
        typed_value="tomorrow",
        branch_scope="root",
        valid_time=TimeRange(101, None),
    )
    guard = DomainGuard()

    for claim, expected in ((sibling, "claim_branch_scope_invalid"), (future, "claim_future_time")):
        with pytest.raises(GuardRejected) as error:
            guard.validate_patch(state, StatePatch((AddKnowledgeClaim(claim),), branch_id="root", base_world_time=100))
        assert error.value.code == expected

    second = KnowledgeClaim(subject_id="akira", predicate="public_fact", typed_value="known", branch_scope="root")
    link = ClaimLink(valid.claim_id, second.claim_id, ClaimLinkKind.SUPPORTS)
    patch = StatePatch(
        (AddKnowledgeClaim(valid), AddKnowledgeClaim(second), AddClaimLink(link)),
        branch_id="root",
        base_world_time=100,
    )
    assert guard.validate_patch(state, patch).operation_count == 3

    missing_link = ClaimLink(valid.claim_id, "missing-claim", ClaimLinkKind.SUPPORTS)
    with pytest.raises(GuardRejected) as link_error:
        guard.validate_patch(
            state,
            StatePatch((AddKnowledgeClaim(valid), AddClaimLink(missing_link)), branch_id="root", base_world_time=100),
        )
    assert link_error.value.code == "claim_link_reference_invalid"


def test_observation_requires_owner_to_witness_saw_event() -> None:
    state = _state()
    claim = KnowledgeClaim(subject_id="yuki", predicate="public_fact", typed_value="secret", branch_scope="root")
    event = Event(
        event_id="event-letter",
        event_type="hide_letter",
        world_time=10,
        branch_scope="root",
        actor_ids=("alice",),
        witness_ids=("alice",),
    )
    observation = Observation(
        observation_id="observation-bob",
        observer_id="bob",
        observed_claim_id=claim.claim_id,
        source_event_id=event.event_id,
        method="saw",
        branch_scope="root",
        world_time=20,
    )
    patch = StatePatch(
        (AddKnowledgeClaim(claim), AddObservation(observation)),
        branch_id="root",
        base_world_time=100,
    )

    state.events[event.event_id] = event
    with pytest.raises(GuardRejected) as error:
        DomainGuard().validate_patch(state, patch)
    assert error.value.code == "observation_owner_or_source_invalid"


def test_belief_cannot_use_future_evidence() -> None:
    state = _state(world_time=250)
    claim = KnowledgeClaim(subject_id="yuki", predicate="public_fact", typed_value="secret", branch_scope="root")
    event = Event(event_id="event-future", event_type="reveal", world_time=200, branch_scope="root", actor_ids=("bob",))
    evidence = Evidence(
        evidence_id="evidence-future",
        owner_id="bob",
        source_event_id=event.event_id,
        claim_id=claim.claim_id,
        branch_scope="root",
        world_time=200,
    )
    belief = Belief(
        belief_id="belief-before-evidence",
        believer_id="bob",
        claim_id=claim.claim_id,
        evidence_ids=(evidence.evidence_id,),
        branch_scope="root",
        world_time=100,
    )
    patch = StatePatch(
        (
            AddKnowledgeClaim(claim),
            # The engine validates the event before evidence; the event itself is historical.
            AddEvent(event),
            AddEvidence(evidence),
            UpdateBelief(belief),
        ),
        branch_id="root",
        base_world_time=250,
    )

    with pytest.raises(GuardRejected) as error:
        DomainGuard().validate_patch(state, patch)
    assert error.value.code == "future_evidence_not_authorized"
