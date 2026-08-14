from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.domain.characters import Character, CharacterProfile
from src.domain.errors import GuardRejected
from src.domain.events import Event
from src.domain.guard import DomainGuard
from src.domain.patch import AddEvent, ApplyRelationshipDelta, StatePatch
from src.domain.relationships import RELATIONSHIP_BOUNDS, RelationshipVector, derive_familiarity
from src.domain.state import GameState
from src.domain.values import Provenance


def _state() -> GameState:
    state = GameState.empty(branch_id="root")
    state.characters = {
        "alice": Character(CharacterProfile("alice", "Alice", 18)),
        "bob": Character(CharacterProfile("bob", "Bob", 18)),
    }
    return state


def test_property_relationship_dimensions_stay_within_individual_bounds() -> None:
    for dimension, (lower, upper) in RELATIONSHIP_BOUNDS.items():
        if dimension == "familiarity":
            continue
        for initial in (-10.0, -1.0, 0.0, 0.5, 1.0, 10.0):
            vector = RelationshipVector({dimension: initial})
            for delta in (-100.0, -1.0, 0.0, 1.0, 100.0):
                updated, _, after = vector.apply_delta(dimension, delta)
                assert lower <= updated.value(dimension) <= upper
                assert lower <= after <= upper


@given(
    dimension=st.sampled_from(tuple(dimension for dimension in RELATIONSHIP_BOUNDS if dimension != "familiarity")),
    initial=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_property_hypothesis_relationship_range_invariant(dimension: str, initial: float, delta: float) -> None:
    lower, upper = RELATIONSHIP_BOUNDS[dimension]
    updated, _, after = RelationshipVector({dimension: initial}).apply_delta(dimension, delta)
    assert lower <= updated.value(dimension) <= upper
    assert lower <= after <= upper


def test_familiarity_is_monotonic_and_not_directly_mutable() -> None:
    values = [
        derive_familiarity(shared_scene_count=count, meaningful_event_count=count, elapsed_minutes=count * 60)
        for count in range(8)
    ]
    assert values == sorted(values)
    with pytest.raises(ValueError):
        RelationshipVector.zero().apply_delta("familiarity", 0.2)


def test_directed_relationships_require_cause_and_preserve_audit_record() -> None:
    state = _state()
    event = Event(
        event_id="event-promise",
        event_type="broken_promise",
        world_time=0,
        branch_scope="root",
        actor_ids=("alice", "bob"),
    )
    operation = ApplyRelationshipDelta(
        source_id="alice",
        target_id="bob",
        dimension="trust",
        proposed_delta=-0.2,
        cause_event_id=event.event_id,
        reason="Alice saw Bob break a promise.",
        provenance=Provenance("test", "relationship-proposal"),
    )
    patch = StatePatch((AddEvent(event), operation), branch_id="root", base_world_time=0)
    result = DomainGuard().validate_patch(state, patch)
    assert result.operation_count == 2

    missing_cause = StatePatch((operation,), branch_id="root", base_world_time=0)
    with pytest.raises(GuardRejected) as error:
        DomainGuard().validate_patch(state, missing_cause)
    assert error.value.code == "relationship_cause_event_required"
