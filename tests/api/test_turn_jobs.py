from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import httpx
import pytest

from src.api.factory import create_app
from src.application.contracts.persistence import BranchRecord, PlaythroughRecord
from src.application.ports.persistence import UowFactory
from src.application.services.events import InMemoryJobEventBroker
from src.application.services.jobs import InMemoryJobStore
from src.application.services.turns import TurnApplicationService
from src.config import Settings
from src.domain.state import GameState


class FakePlaythroughs:
    def __init__(self, playthrough: PlaythroughRecord) -> None:
        self.playthrough = playthrough

    async def get_playthrough(self, playthrough_id: str) -> PlaythroughRecord:
        assert playthrough_id == self.playthrough.id
        return self.playthrough

    async def get(self, playthrough_id: str) -> PlaythroughRecord | None:
        return self.playthrough if playthrough_id == self.playthrough.id else None


class FakeCanonical:
    def __init__(self, branch: BranchRecord) -> None:
        self.branch = branch

    async def get_branch(self, branch_id: str):
        return self.branch if branch_id == self.branch.id else None

    async def get_turn_by_run_id(self, _run_id: str):
        return None

    async def get_turn(self, _turn_id: str):
        return None


class FakeUow:
    def __init__(self, playthrough: PlaythroughRecord, branch: BranchRecord) -> None:
        self.playthroughs = FakePlaythroughs(playthrough)
        self.canonical = FakeCanonical(branch)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeRunner:
    async def run(self, request: Any) -> dict[str, Any]:
        return {"status": "completed", "commit_done": True, "result": {"narrative": "A final line."}}

    def cancel(self, turn_run_id: str) -> None:
        del turn_run_id
        return None


class FakeGameStates:
    async def load(self, *, playthrough_id: str, branch_id: str) -> GameState:
        return GameState.empty(
            world_id="world-1",
            playthrough_id=playthrough_id,
            branch_id=branch_id,
        )


def _services() -> tuple[SimpleNamespace, TurnApplicationService]:
    playthrough = PlaythroughRecord.new(world_id="world-1")
    branch = BranchRecord.root(playthrough_id=playthrough.id, branch_id="root")

    def raw_uow_factory() -> FakeUow:
        return FakeUow(playthrough, branch)

    uow_factory = cast(UowFactory, raw_uow_factory)
    events = InMemoryJobEventBroker()
    turns = TurnApplicationService(
        uow_factory,
        FakeRunner(),
        job_store=InMemoryJobStore(),
        event_broker=events,
    )
    return (
        SimpleNamespace(
            playthroughs=FakePlaythroughs(playthrough),
            game_states=FakeGameStates(),
            turns=turns,
            events=events,
        ),
        turns,
    )


@pytest.mark.asyncio
async def test_submit_is_idempotent_and_sse_reconnect_replays_final_event() -> None:
    services, turns = _services()
    app = create_app(Settings(app_name="api-test"), services=services)  # type: ignore[arg-type]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        body = {
            "playthrough_id": services.playthroughs.playthrough.id,
            "branch_id": "root",
            "raw_input": "look around",
            "base_revision": 0,
            "turn_run_id": "run-api-1",
            "idempotency_key": "key-api-1",
        }
        first = await client.post("/api/turns", json=body)
        duplicate = await client.post("/api/turns", json=body)
        assert first.status_code == duplicate.status_code == 202
        assert first.json()["job_id"] == duplicate.json()["job_id"]

        completed = await turns.wait_for_turn("run-api-1")
        job_id = completed.job_id
        assert completed.status == "completed"
        assert job_id is not None

        job = await client.get(f"/api/jobs/{job_id}")
        assert job.status_code == 200
        assert job.json()["status"] == "completed"

        stream = await client.get(f"/api/jobs/{job_id}/events", headers={"Last-Event-ID": "1"})
        assert stream.status_code == 200
        assert "event: completed" in stream.text
        assert '"terminal": true' in stream.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "failed", "cancelled", "interrupted"])
@pytest.mark.parametrize("cursor_source", ["header", "query"])
async def test_sse_recovers_persisted_outcome_after_broker_restart(status: str, cursor_source: str) -> None:
    events = InMemoryJobEventBroker()
    job = SimpleNamespace(turn_run_id="run", status=status, result={"narrative": "Saved result"}, error=None)
    services = SimpleNamespace(events=events, turns=SimpleNamespace(get_job=AsyncMock(return_value=job)))
    app = create_app(Settings(), services=services)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await asyncio.wait_for(
            client.get(
                "/api/jobs/job/events",
                headers={"Last-Event-ID": "20"} if cursor_source == "header" else {},
                params={"last_event_id": "20"} if cursor_source == "query" else {},
            ),
            timeout=2,
        )
    assert response.status_code == 200
    assert f"event: {status}" in response.text
    assert '"terminal": true' in response.text
    assert "Saved result" in response.text
