from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from src.application.contracts.jobs import JobRecord
from src.application.contracts.persistence import BranchRecord, PlaythroughRecord
from src.application.contracts.turns import SubmitTurnCommand
from src.application.errors import ResourceConflictError
from src.application.ports.persistence import UowFactory
from src.application.services.events import InMemoryJobEventBroker
from src.application.services.jobs import InMemoryJobStore
from src.application.services.turns import TurnApplicationService
from src.domain.state import GameState


class FakePlaythroughs:
    def __init__(self, playthrough: PlaythroughRecord) -> None:
        self.playthrough = playthrough

    async def get(self, playthrough_id: str):
        return self.playthrough if self.playthrough.id == playthrough_id else None


class FakeCanonical:
    def __init__(self, branches: list[BranchRecord]) -> None:
        self.branches = {branch.id: branch for branch in branches}

    async def get_branch(self, branch_id: str):
        return self.branches.get(branch_id)

    async def get_turn_by_run_id(self, _run_id: str):
        return None

    async def get_turn(self, _turn_id: str):
        return None


class FakeUow:
    def __init__(self, playthrough: PlaythroughRecord, branches: list[BranchRecord]) -> None:
        self.playthroughs = FakePlaythroughs(playthrough)
        self.canonical = FakeCanonical(branches)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeRunner:
    def __init__(self) -> None:
        self.release: dict[str, asyncio.Event] = {}
        self.cancelled: set[str] = set()
        self.active = 0
        self.max_active = 0
        self.calls: list[str] = []

    async def run(self, request: Any) -> dict[str, Any]:
        self.calls.append(request.turn_run_id)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        gate = self.release.setdefault(request.turn_run_id, asyncio.Event())
        try:
            await gate.wait()
            if request.turn_run_id in self.cancelled:
                return {"status": "cancelled"}
            return {"status": "completed", "commit_done": True, "result": {"run": request.turn_run_id}}
        finally:
            self.active -= 1

    def cancel(self, turn_run_id: str) -> None:
        self.cancelled.add(turn_run_id)
        self.release.setdefault(turn_run_id, asyncio.Event()).set()


def _factory(playthrough: PlaythroughRecord, branches: list[BranchRecord]):
    def factory() -> FakeUow:
        return FakeUow(playthrough, branches)

    return cast(UowFactory, factory)


def _command(playthrough: PlaythroughRecord, *, branch_id: str, run_id: str, key: str) -> SubmitTurnCommand:
    return SubmitTurnCommand(
        idempotency_key=key,
        turn_run_id=run_id,
        playthrough_id=playthrough.id,
        branch_id=branch_id,
        base_revision=0,
        raw_input=f"input:{run_id}",
        actor_id="player",
        game_state=GameState.empty(
            world_id=playthrough.world_id,
            playthrough_id=playthrough.id,
            branch_id=branch_id,
        ),
    )


def _fixture():
    playthrough = PlaythroughRecord.new(world_id="world-1")
    root = BranchRecord.root(playthrough_id=playthrough.id, branch_id="root")
    side = BranchRecord.root(playthrough_id=playthrough.id, branch_id="side")
    return playthrough, [root, side]


@pytest.mark.asyncio
async def test_durable_job_idempotency_and_terminal_state() -> None:
    playthrough, branches = _fixture()
    runner = FakeRunner()
    store = InMemoryJobStore()
    service = TurnApplicationService(
        _factory(playthrough, branches),
        runner,
        job_store=store,
        event_broker=InMemoryJobEventBroker(),
    )

    first = await service.submit_turn(_command(playthrough, branch_id="root", run_id="run-1", key="key-1"))
    duplicate = await service.submit_turn(_command(playthrough, branch_id="root", run_id="run-1", key="key-1"))
    assert duplicate.job_id == first.job_id
    assert len(store.jobs) == 1

    await asyncio.sleep(0)
    runner.release["run-1"].set()
    completed = await service.wait_for_turn("run-1")
    assert completed.status == "completed"
    assert store.jobs[first.job_id].status == "completed"  # type: ignore[index]


@pytest.mark.asyncio
async def test_global_semaphore_and_per_branch_lock_are_enforced() -> None:
    playthrough, branches = _fixture()
    runner = FakeRunner()
    service = TurnApplicationService(
        _factory(playthrough, branches),
        runner,
        job_store=InMemoryJobStore(),
        max_concurrency=1,
    )

    first = await service.submit_turn(_command(playthrough, branch_id="root", run_id="run-1", key="key-1"))
    with pytest.raises(ResourceConflictError):
        await service.submit_turn(_command(playthrough, branch_id="root", run_id="run-2", key="key-2"))
    second = await service.submit_turn(_command(playthrough, branch_id="side", run_id="run-3", key="key-3"))

    await asyncio.sleep(0)
    runner.release["run-1"].set()
    await asyncio.sleep(0)
    runner.release.setdefault("run-3", asyncio.Event()).set()
    await service.wait_for_turn(first.turn_run_id)
    await service.wait_for_turn(second.turn_run_id)
    assert runner.max_active == 1


@pytest.mark.asyncio
async def test_start_marks_previous_process_jobs_interrupted() -> None:
    store = InMemoryJobStore()
    store.jobs["job-1"] = JobRecord(
        id="job-1",
        kind="turn",
        idempotency_key="key-1",
        turn_run_id="run-1",
        playthrough_id="playthrough-1",
        branch_id="root",
        base_revision=0,
        raw_input="hello",
        actor_id="player",
        parent_turn_id=None,
        config_snapshot_id="test",
        command_fingerprint=("run-1",),
        status="running",
    )
    playthrough, branches = _fixture()
    service = TurnApplicationService(_factory(playthrough, branches), FakeRunner(), job_store=store)

    assert await service.start() == 1
    assert store.jobs["job-1"].status == "interrupted"


@pytest.mark.asyncio
async def test_event_broker_replays_from_last_event_and_closes_on_terminal() -> None:
    broker = InMemoryJobEventBroker(history_size=8)
    await broker.register(job_id="job-1", turn_run_id="run-1")
    await broker.publish_job_event(
        job_id="job-1", turn_run_id="run-1", event_type="job_queued", phase="job", payload={"status": "queued"}
    )
    await broker.publish_job_event(
        job_id="job-1", turn_run_id="run-1", event_type="writer_token", phase="writer", payload={"text": "A"}
    )
    await broker.publish_job_event(
        job_id="job-1",
        turn_run_id="run-1",
        event_type="completed",
        phase="job",
        payload={"status": "completed"},
        terminal=True,
    )

    events = [event async for event in broker.subscribe("job-1", last_event_id="1")]
    assert [event.event_type for event in events] == ["writer_token", "completed"]
    assert [event.id for event in events] == ["2", "3"]
