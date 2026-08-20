from __future__ import annotations

import random

import pytest

from src.domain.characters import Character, CharacterProfile
from src.domain.clock import ClockPolicy
from src.domain.engine import DomainEngine
from src.domain.errors import GuardRejected
from src.domain.events import Event
from src.domain.guard import DomainGuard
from src.domain.knowledge import KnowledgeClaim
from src.domain.patch import (
    AddEvent,
    AddKnowledgeClaim,
    AdvanceClock,
    ApplyRelationshipDelta,
    AssertCanonFact,
    SetCharacterLocation,
    StatePatch,
    UpdatePsychology,
)
from src.domain.state import GameState
from src.domain.values import Provenance, TimeRange


def _state() -> GameState:
    state = GameState.empty(world_id="world", playthrough_id="playthrough", branch_id="root")
    state.locations.add("clubroom")
    state.characters = {
        character_id: Character(CharacterProfile(character_id, character_id.title(), 18)) for character_id in ("yuki", "akira")
    }
    return state


def _patch() -> StatePatch:
    cause = Event(
        event_id="event-betrayal",
        event_type="betrayal",
        world_time=0,
        branch_scope="root",
        actor_ids=("yuki", "akira"),
    )
    claim = KnowledgeClaim(
        subject_id="yuki",
        predicate="located_at",
        object_id="clubroom",
        valid_time=TimeRange(0, None),
        branch_scope="root",
    )
    return StatePatch(
        (
            AddEvent(cause),
            ApplyRelationshipDelta(
                source_id="yuki",
                target_id="akira",
                dimension="trust",
                proposed_delta=-0.2,
                cause_event_id=cause.event_id,
                reason="A broken promise was witnessed.",
                provenance=Provenance("fixture", "relationship-proposal", turn_id="turn-1"),
            ),
            SetCharacterLocation("yuki", "clubroom"),
            UpdatePsychology("yuki", {"stress": 0.25, "valence": -0.4}),
            AdvanceClock(5),
            AddKnowledgeClaim(claim),
            AssertCanonFact(claim.claim_id, source_event_or_rule=cause.event_id),
        ),
        branch_id="root",
        base_world_time=0,
        patch_id="patch-fixture-1",
    )


def test_fixture_patch_validates_applies_reverts_and_replays_in_memory() -> None:
    initial = _state()
    engine = DomainEngine(guard=DomainGuard(), rng=random.Random(7))
    patch = _patch()

    applied = engine.apply(initial, patch)
    assert initial.world_time == 0
    assert applied.after.world_time == 5
    assert applied.after.characters["yuki"].state.location_id == "clubroom"
    assert applied.after.characters["yuki"].state.psychology.stress == 0.25
    assert applied.after.relationship_vector("yuki", "akira").value("trust") == 0.0
    assert len(applied.after.relationship_changes) == 1
    assert len(applied.after.canon_facts) == 1
    assert engine.revert(applied) == initial

    replayed = engine.replay(initial, [patch])
    assert replayed == applied.after


def test_invalid_transition_and_branch_are_rejected_before_mutation() -> None:
    state = _state()
    invalid = StatePatch(({"operation_type": "set_character_location"},), branch_id="root", base_world_time=0)
    with pytest.raises(GuardRejected) as untyped_error:
        DomainGuard().validate_patch(state, invalid)
    assert untyped_error.value.code == "untyped_operation"

    wrong_branch = StatePatch((AdvanceClock(1),), branch_id="sibling", base_world_time=0)
    with pytest.raises(GuardRejected) as branch_error:
        DomainGuard().validate_patch(state, wrong_branch)
    assert branch_error.value.code == "branch_scope_mismatch"


def test_guard_limits_total_clock_movement_across_operations() -> None:
    state = _state()
    patch = StatePatch(
        (AdvanceClock(6), AdvanceClock(5)),
        branch_id="root",
        base_world_time=0,
    )

    with pytest.raises(GuardRejected) as duration_error:
        DomainGuard(clock_policy=ClockPolicy(max_turn_duration_minutes=10)).validate_patch(state, patch)

    assert duration_error.value.code == "duration_over_limit"
    assert duration_error.value.details == {"maximum": 10, "received": 11}
