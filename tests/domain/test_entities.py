from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.domain.characters import Character, CharacterProfile
from src.domain.clock import InWorldClock
from src.domain.content import ConsentRecord, ConsentState
from src.domain.errors import DomainValidationError, GuardRejected
from src.domain.events import Event
from src.domain.guard import DomainGuard
from src.domain.narrative import NarrativeThread, ThreadStatus
from src.domain.patch import AddEvent, StatePatch
from src.domain.state import GameState


def test_world_clock_and_age_are_historical_and_monotonic() -> None:
    clock = InWorldClock(10)
    assert clock.advance(5).world_time == 15
    with pytest.raises(DomainValidationError):
        clock.advance(-1)

    profile = CharacterProfile("student", "Student", 17, age_anchor_world_time=0)
    assert profile.age_at(0) == 17
    assert profile.age_at(365 * 24 * 60) == 18
    assert profile.age_at(0) == 17


def test_consent_state_machine_requires_explicit_transitions() -> None:
    record = ConsentRecord("scene-1", "alice", "explicit")
    record = record.transition(ConsentState.REQUESTED, world_time=10)
    record = record.transition(ConsentState.GRANTED, world_time=11)
    record = record.transition(ConsentState.WITHDRAWN, world_time=12)
    assert record.state == ConsentState.WITHDRAWN
    with pytest.raises(DomainValidationError):
        record.transition(ConsentState.GRANTED, world_time=13)


def test_thread_lifecycle_rejects_terminal_revival() -> None:
    thread = NarrativeThread("thread-1", "Find the missing letter", "root")
    thread = thread.transition(ThreadStatus.ACTIVE, world_time=0)
    thread = thread.transition(ThreadStatus.RESOLVED, progress_delta=1.0, world_time=5)
    with pytest.raises(DomainValidationError):
        thread.transition(ThreadStatus.ACTIVE, world_time=6)


def test_active_thread_can_advance_without_changing_lifecycle_status() -> None:
    thread = NarrativeThread("thread-1", "Build trust", "root").transition(ThreadStatus.ACTIVE, world_time=0)

    advanced = thread.transition(ThreadStatus.ACTIVE, progress_delta=0.05, world_time=5)

    assert advanced.status == ThreadStatus.ACTIVE
    assert advanced.progress == pytest.approx(0.05)
    assert advanced.last_advanced_world_time == 5
    with pytest.raises(DomainValidationError):
        advanced.transition(ThreadStatus.ACTIVE, progress_delta=0.0, world_time=6)


def test_property_referential_integrity_rejects_unknown_event_participants() -> None:
    state = GameState.empty(branch_id="root")
    state.characters["alice"] = Character(CharacterProfile("alice", "Alice", 18))
    event = Event(
        event_id="event-invalid",
        event_type="unknown-person-action",
        world_time=0,
        branch_scope="root",
        actor_ids=("missing",),
    )

    with pytest.raises(GuardRejected) as error:
        DomainGuard().validate_patch(
            state,
            StatePatch((AddEvent(event),), branch_id="root", base_world_time=0),
        )
    assert error.value.code == "event_participant_reference_invalid"


@given(missing_id=st.text(min_size=1).filter(lambda value: value != "alice"))
def test_property_hypothesis_referential_integrity_rejects_unknown_participant(missing_id: str) -> None:
    state = GameState.empty(branch_id="root")
    state.characters["alice"] = Character(CharacterProfile("alice", "Alice", 18))
    event = Event(
        event_id="event-invalid-property",
        event_type="unknown-person-action",
        world_time=0,
        branch_scope="root",
        actor_ids=(missing_id,),
    )

    with pytest.raises(GuardRejected) as error:
        DomainGuard().validate_patch(
            state,
            StatePatch((AddEvent(event),), branch_id="root", base_world_time=0),
        )
    assert error.value.code == "event_participant_reference_invalid"
