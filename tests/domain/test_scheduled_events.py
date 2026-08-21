from __future__ import annotations

import pytest

from src.domain.codec import patch_from_payload, patch_to_payload, state_from_payload, state_to_payload
from src.domain.engine import DomainEngine
from src.domain.errors import GuardRejected
from src.domain.events import Event, ScheduledEvent
from src.domain.patch import AddEvent, AdvanceClock, MaterializeScheduledEvent, ScheduleEvent, StatePatch
from src.domain.state import GameState


def _scheduled() -> ScheduledEvent:
    return ScheduledEvent(
        scheduled_event_id="schedule-1",
        due_world_time=5,
        event=Event(
            event_id="event-offscreen",
            event_type="club_meeting",
            world_time=5,
            branch_scope="root",
            actor_ids=("alice", "bob"),
        ),
    )


def _cause() -> Event:
    return Event(event_id="event-cause", event_type="promise", world_time=0, branch_scope="root")


def test_scheduled_event_waits_until_due_then_materializes() -> None:
    state = GameState.empty(branch_id="root", world_time=0)
    state.characters = {"alice": object(), "bob": object()}  # type: ignore[assignment]
    schedule = _scheduled()
    scheduled_patch = StatePatch((AddEvent(_cause()), ScheduleEvent(schedule)), branch_id="root", base_world_time=0)
    waiting = DomainEngine().apply(state, scheduled_patch).after
    assert "schedule-1" in waiting.scheduled_events
    assert DomainEngine.due_scheduled_operations(waiting) == ()

    advanced = (
        DomainEngine()
        .apply(
            waiting,
            StatePatch((AdvanceClock(5),), branch_id="root", base_world_time=0),
        )
        .after
    )
    operation = DomainEngine.due_scheduled_operations(advanced)[0]
    materialized = (
        DomainEngine()
        .apply(
            advanced,
            StatePatch((MaterializeScheduledEvent(operation.scheduled_event_id),), branch_id="root", base_world_time=5),
        )
        .after
    )
    assert "schedule-1" not in materialized.scheduled_events
    assert materialized.events["event-offscreen"].world_time == 5
    assert "scheduled:schedule-1" in materialized.events["event-offscreen"].cause_event_ids


def test_scheduled_event_cannot_materialize_before_due() -> None:
    state = GameState.empty(branch_id="root", world_time=0)
    state.characters = {"alice": object(), "bob": object()}  # type: ignore[assignment]
    with pytest.raises(GuardRejected) as error:
        DomainEngine().apply(
            state,
            StatePatch(
                (AddEvent(_cause()), ScheduleEvent(_scheduled()), MaterializeScheduledEvent("schedule-1")),
                branch_id="root",
            ),
        )
    assert error.value.code == "scheduled_event_not_due"


def test_scheduled_events_survive_patch_and_snapshot_codec() -> None:
    state = GameState.empty(branch_id="root")
    state.scheduled_events["schedule-1"] = _scheduled()
    payload = patch_to_payload(StatePatch((ScheduleEvent(_scheduled()),), branch_id="root"))
    assert isinstance(patch_from_payload(payload).operations[0], ScheduleEvent)
    restored = state_from_payload(state_to_payload(state))
    assert restored.scheduled_events["schedule-1"].due_world_time == 5
