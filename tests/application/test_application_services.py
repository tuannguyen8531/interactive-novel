from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from src.application.contracts.ai import WorldSeed
from src.application.contracts.persistence import (
    BranchRecord,
    CharacterRecord,
    DerivedJobRecord,
    EventRecord,
    InvariantReport,
    PlaythroughRecord,
    TurnRecord,
    WorldRecord,
    utc_now,
)
from src.application.contracts.providers import (
    ConnectivityResult,
    ExecutionMode,
    LogicalRole,
    ProviderName,
    ProviderRoute,
    ProviderRoutingConfig,
    ProviderTarget,
)
from src.application.contracts.queries import CharacterView, MemoryView, RelationshipView
from src.application.contracts.turns import SubmitTurnCommand
from src.application.errors import IdempotencyConflictError, ResourceConflictError
from src.application.ports.persistence import UowFactory
from src.application.ports.providers import ProviderGateway
from src.application.services.branches import BranchApplicationService
from src.application.services.export import PlaythroughExportApplicationService
from src.application.services.playthroughs import PlaythroughApplicationService
from src.application.services.provider_settings import (
    InMemoryProviderSettingsStore,
    ProviderSettingsApplicationService,
)
from src.application.services.queries import CharacterQueryApplicationService
from src.application.services.turns import TurnApplicationService
from src.application.services.world_drafts import WorldDraftApplicationService
from src.application.services.worlds import WorldApplicationService
from src.domain.state import GameState
from src.services.provider_settings import JsonProviderSettingsStore


class Store:
    def __init__(self) -> None:
        self.worlds: dict[str, WorldRecord] = {}
        self.character_records: dict[str, CharacterRecord] = {}
        self.playthroughs: dict[str, PlaythroughRecord] = {}
        self.branches: dict[str, BranchRecord] = {}
        self.turns: dict[str, TurnRecord] = {}
        self.events: dict[str, list[EventRecord]] = {}
        self.characters: list[CharacterView] = []
        self.memories: list[MemoryView] = []
        self.relationships: list[RelationshipView] = []
        self.jobs: list[DerivedJobRecord] = []


class FakeWorlds:
    def __init__(self, store: Store) -> None:
        self.store = store

    async def add(self, world: WorldRecord) -> None:
        self.store.worlds[world.id] = world

    async def get(self, world_id: str) -> WorldRecord | None:
        return self.store.worlds.get(world_id)

    async def list(self) -> list[WorldRecord]:
        return list(self.store.worlds.values())

    async def delete(self, world_id: str) -> bool:
        return self.store.worlds.pop(world_id, None) is not None


class FakeCharacters:
    def __init__(self, store: Store) -> None:
        self.store = store

    async def add(self, character: CharacterRecord) -> None:
        self.store.character_records[character.id] = character

    async def get(self, character_id: str) -> CharacterRecord | None:
        return self.store.character_records.get(character_id)

    async def list(self, *, world_id: str, playthrough_id: str | None = None) -> list[CharacterRecord]:
        return [
            item
            for item in self.store.character_records.values()
            if item.world_id == world_id and (playthrough_id is None or item.playthrough_id in {None, playthrough_id})
        ]


class FakePlaythroughs:
    def __init__(self, store: Store) -> None:
        self.store = store

    async def add(self, playthrough: PlaythroughRecord) -> None:
        self.store.playthroughs[playthrough.id] = playthrough

    async def get(self, playthrough_id: str) -> PlaythroughRecord | None:
        return self.store.playthroughs.get(playthrough_id)

    async def list(self, *, world_id: str | None = None) -> list[PlaythroughRecord]:
        values = list(self.store.playthroughs.values())
        return [item for item in values if world_id is None or item.world_id == world_id]

    async def set_root_branch(self, playthrough_id: str, branch_id: str) -> None:
        playthrough = self.store.playthroughs[playthrough_id]
        self.store.playthroughs[playthrough_id] = replace(
            playthrough,
            root_branch_id=branch_id,
            active_branch_id=branch_id,
            updated_at=datetime.now(UTC),
        )

    async def set_active_branch(self, playthrough_id: str, branch_id: str) -> None:
        playthrough = self.store.playthroughs[playthrough_id]
        self.store.playthroughs[playthrough_id] = replace(
            playthrough,
            active_branch_id=branch_id,
            updated_at=datetime.now(UTC),
        )

    async def update_provider_config_snapshot(self, playthrough_id: str, snapshot: dict[str, object]) -> None:
        playthrough = self.store.playthroughs[playthrough_id]
        self.store.playthroughs[playthrough_id] = replace(
            playthrough,
            provider_config_snapshot=dict(snapshot),
            updated_at=datetime.now(UTC),
        )


class FakeCanonical:
    def __init__(self, store: Store) -> None:
        self.store = store

    async def add_branch(self, branch: BranchRecord) -> None:
        self.store.branches[branch.id] = branch

    async def get_branch(self, branch_id: str) -> BranchRecord | None:
        return self.store.branches.get(branch_id)

    async def get_turn(self, turn_id: str) -> TurnRecord | None:
        return self.store.turns.get(turn_id)

    async def get_turn_by_run_id(self, turn_run_id: str) -> TurnRecord | None:
        return next((item for item in self.store.turns.values() if item.turn_run_id == turn_run_id), None)

    async def list_branches(self, playthrough_id: str) -> list[BranchRecord]:
        return [item for item in self.store.branches.values() if item.playthrough_id == playthrough_id]

    async def list_turns(self, playthrough_id: str, *, branch_id: str | None = None) -> list[TurnRecord]:
        return [
            item
            for item in self.store.turns.values()
            if item.playthrough_id == playthrough_id and (branch_id is None or item.branch_id == branch_id)
        ]

    async def get_branch_ancestry(self, branch_id: str) -> list[BranchRecord]:
        result: list[BranchRecord] = []
        current = self.store.branches[branch_id]
        while True:
            result.append(current)
            if current.parent_branch_id is None:
                return list(reversed(result))
            current = self.store.branches[current.parent_branch_id]

    async def verify_invariants(self, branch_id: str) -> InvariantReport:
        return InvariantReport(branch_id=branch_id, valid=True)

    async def commit_turn(self, bundle: Any, *, fail_after_step: str | None = None) -> TurnRecord:
        raise NotImplementedError

    async def list_visible_events(self, branch_id: str) -> list[EventRecord]:
        return list(self.store.events.get(branch_id, ()))

    async def list_approved_patches(self, branch_id: str, *, after_revision: int = 0) -> list[tuple[int, dict[str, object]]]:
        return []

    async def save_snapshot(self, snapshot: Any) -> None:
        raise NotImplementedError

    async def load_latest_snapshot(self, branch_id: str) -> Any | None:
        return None

    async def enqueue_derived_job(self, job: DerivedJobRecord) -> DerivedJobRecord:
        self.store.jobs.append(job)
        return job

    async def list_derived_jobs(self, *, status: str | None = None) -> list[DerivedJobRecord]:
        return [item for item in self.store.jobs if status is None or item.status == status]

    async def mark_derived_job(self, job_id: str, *, status: str, error: str | None = None) -> None:
        raise NotImplementedError

    async def reconcile_derived_jobs(self) -> int:
        return 0


class FakeInspection:
    def __init__(self, store: Store) -> None:
        self.store = store

    async def list_characters(self, *, playthrough_id: str, world_id: str, branch_id: str | None = None) -> list[CharacterView]:
        return list(self.store.characters)

    async def get_character_public_profile(
        self,
        *,
        playthrough_id: str,
        world_id: str,
        character_id: str,
        branch_id: str | None = None,
    ) -> CharacterView | None:
        return next((item for item in self.store.characters if item.id == character_id), None)

    async def inspect_character_memory(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        character_id: str,
        limit: int = 100,
    ) -> list[MemoryView]:
        return list(self.store.memories)[:limit]

    async def inspect_relationships(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        character_id: str | None = None,
    ) -> list[RelationshipView]:
        return [
            item
            for item in self.store.relationships
            if character_id is None or item.source_id == character_id or item.target_id == character_id
        ]


class FakeUow:
    def __init__(self, store: Store) -> None:
        self.worlds = FakeWorlds(store)
        self.characters = FakeCharacters(store)
        self.playthroughs = FakePlaythroughs(store)
        self.canonical = FakeCanonical(store)
        self.inspection = FakeInspection(store)
        self.retrieval = object()

    async def __aenter__(self) -> FakeUow:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _factory(store: Store) -> UowFactory:
    return cast(UowFactory, lambda: FakeUow(store))


async def _setup() -> tuple[Store, WorldRecord, PlaythroughRecord, BranchRecord]:
    store = Store()
    factory = _factory(store)
    world = await WorldApplicationService(factory).create_world(name="Moonlight School")
    playthrough = await PlaythroughApplicationService(factory).create_playthrough(world_id=world.id)
    branch = await BranchApplicationService(factory).create_root_branch(playthrough_id=playthrough.id, branch_id="root")
    return store, world, store.playthroughs[playthrough.id], branch


async def test_world_playthrough_and_branch_use_cases_keep_active_branch_selection() -> None:
    store, world, playthrough, root = await _setup()
    worlds = WorldApplicationService(_factory(store))
    playthroughs = PlaythroughApplicationService(_factory(store))
    branches = BranchApplicationService(_factory(store))

    assert (await worlds.list_worlds())[0].id == world.id
    assert (await playthroughs.list_playthroughs(world_id=world.id))[0].id == playthrough.id
    assert store.playthroughs[playthrough.id].active_branch_id == root.id

    first_turn = TurnRecord(
        id="turn-1",
        playthrough_id=playthrough.id,
        branch_id=root.id,
        parent_turn_id=None,
        raw_input="look around",
        normalized_input="look around",
        base_revision=0,
        status="completed",
        final_narrative="The room glows.",
        approved_patch={},
        world_time_start=0,
        duration_minutes=1,
        world_time_end=1,
        turn_run_id="run-1",
        schema_version=1,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    store.turns[first_turn.id] = first_turn
    store.branches[root.id] = replace(root, head_turn_id=first_turn.id, head_revision=1)
    child = await branches.fork_branch(parent_branch_id=root.id, fork_turn_id=first_turn.id, branch_id="child")
    sibling = await branches.regenerate_branch(parent_branch_id=root.id, fork_turn_id=first_turn.id, branch_id="sibling")
    await branches.switch_branch(playthrough_id=playthrough.id, branch_id=child.id)

    assert child.parent_branch_id == root.id
    assert sibling.parent_branch_id == root.id
    assert store.playthroughs[playthrough.id].active_branch_id == child.id


class FakeWorldGenerator:
    def __init__(self, seed: WorldSeed) -> None:
        self.seed = seed

    async def generate_world_draft(self, prompt: str) -> WorldSeed:
        return self.seed


async def test_world_draft_generation_validation_and_confirmation_are_explicit() -> None:
    payload = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "ai" / "role_outputs.json").read_text(encoding="utf-8")
    )["world_builder"]
    seed = WorldSeed.model_validate(payload)
    store = Store()
    service = WorldDraftApplicationService(_factory(store), generator=FakeWorldGenerator(seed))

    generated = await service.generate_world_draft("A warm school romance under a changing sky.")
    world = await service.confirm_world(generated, world_id="confirmed-world")

    assert generated.title == world.name
    assert world.id == "confirmed-world"
    assert {item.display_name for item in store.character_records.values()} == {
        generated.player_character.name,
        *(item.name for item in generated.npc_profiles),
    }


async def test_character_memory_relationship_and_timeline_queries_are_scoped() -> None:
    store, _, playthrough, branch = await _setup()
    store.characters.append(
        CharacterView(
            id="yuki",
            world_id=playthrough.world_id,
            playthrough_id=playthrough.id,
            display_name="Yuki",
            aliases=("Yu",),
            public_profile={"role": "student"},
        )
    )
    store.memories.append(
        MemoryView(
            memory_id="belief:1",
            kind="belief",
            owner_id="yuki",
            branch_id=branch.id,
            turn_id="turn-1",
            world_time=2,
            payload={"stance": "supports"},
            confidence=0.8,
        )
    )
    store.relationships.append(
        RelationshipView(
            relationship_id="rel-1",
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            source_id="yuki",
            target_id="akira",
            values={"trust": 0.4},
        )
    )
    store.events[branch.id] = [
        EventRecord(
            event_id="event-1",
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            turn_id="turn-1",
            event_type="conversation",
            world_time=2,
            actor_ids=("yuki",),
        )
    ]
    service = CharacterQueryApplicationService(_factory(store))

    assert (await service.list_characters(playthrough_id=playthrough.id, branch_id=branch.id))[0].display_name == "Yuki"
    assert (await service.get_character_public_profile(playthrough_id=playthrough.id, character_id="yuki")).id == "yuki"
    assert (
        await service.inspect_character_memory(
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            character_id="yuki",
        )
    )[0].kind == "belief"
    assert (
        await service.inspect_relationships(
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            character_id="yuki",
        )
    )[0].values["trust"] == 0.4
    assert (await service.inspect_timeline(playthrough_id=playthrough.id, branch_id=branch.id))[0].event_id == "event-1"


class FakeRunner:
    def __init__(self) -> None:
        self.releases: dict[str, asyncio.Event] = {}
        self.cancelled: set[str] = set()
        self.calls: list[str] = []

    async def run(self, request: Any) -> dict[str, Any]:
        self.calls.append(request.turn_run_id)
        release = self.releases.setdefault(request.turn_run_id, asyncio.Event())
        if request.turn_run_id not in self.cancelled:
            await release.wait()
        if request.turn_run_id in self.cancelled:
            return {"status": "cancelled"}
        return {"status": "completed", "commit_done": True, "result": request.turn_run_id}

    def cancel(self, turn_run_id: str) -> None:
        self.cancelled.add(turn_run_id)
        self.releases.setdefault(turn_run_id, asyncio.Event()).set()


def _turn_command(playthrough: PlaythroughRecord, *, key: str, run_id: str, raw_input: str = "say hello") -> SubmitTurnCommand:
    return SubmitTurnCommand(
        idempotency_key=key,
        turn_run_id=run_id,
        playthrough_id=playthrough.id,
        branch_id="root",
        base_revision=0,
        raw_input=raw_input,
        actor_id="player",
        game_state=GameState.empty(
            world_id=playthrough.world_id,
            playthrough_id=playthrough.id,
            branch_id="root",
        ),
    )


async def test_turn_submit_get_cancel_and_policy_are_idempotent() -> None:
    store, _, playthrough, _ = await _setup()
    runner = FakeRunner()
    service = TurnApplicationService(_factory(store), runner)
    first = await service.submit_turn(_turn_command(playthrough, key="key-1", run_id="run-1"))
    duplicate = await service.submit_turn(_turn_command(playthrough, key="key-1", run_id="run-1"))
    assert duplicate.turn_run_id == first.turn_run_id
    with pytest.raises(IdempotencyConflictError):
        await service.submit_turn(_turn_command(playthrough, key="key-1", run_id="run-1", raw_input="different"))
    with pytest.raises(ResourceConflictError):
        await service.submit_turn(_turn_command(playthrough, key="key-2", run_id="run-2"))

    await asyncio.sleep(0)
    runner.releases["run-1"].set()
    completed = await service.wait_for_turn("run-1")
    assert completed.status == "completed"
    assert (await service.get_turn("run-1")).status == "completed"  # type: ignore[union-attr]

    cancelled = await service.submit_turn(_turn_command(playthrough, key="key-3", run_id="run-3"))
    assert cancelled.status == "queued"
    assert (await service.cancel_turn("run-3")).status == "cancelling"
    assert (await service.wait_for_turn("run-3")).status == "cancelled"
    assert runner.calls == ["run-1", "run-3"]


class FakeGateway:
    def __init__(self) -> None:
        self.config: ProviderRoutingConfig | None = None

    async def reconfigure(self, config: ProviderRoutingConfig) -> None:
        self.config = config

    async def check_connectivity(self) -> tuple[ConnectivityResult, ...]:
        return (ConnectivityResult(provider="ollama", model="test", reachable=True, latency_ms=1.0),)


async def test_provider_settings_store_secret_free_snapshot_and_connection_check() -> None:
    store = InMemoryProviderSettingsStore()
    gateway = FakeGateway()
    service = ProviderSettingsApplicationService(store, gateway=cast(ProviderGateway, gateway))
    config = ProviderRoutingConfig(
        targets={
            "local": ProviderTarget(
                name="local",
                provider=ProviderName.OLLAMA,
                model="fixture-model",
                api_key="do-not-store",
            )
        },
        role_routes={LogicalRole.PLANNER: ProviderRoute("local")},
    )

    snapshot = await service.update_provider_settings(config)
    saved = await service.get_provider_settings()
    connectivity = await service.test_provider_connection()

    assert snapshot.as_dict()["targets"]["local"]["model"] == "fixture-model"
    assert saved is not None
    assert "do-not-store" not in str(saved)
    assert gateway.config == config
    assert connectivity[0].reachable is True


async def test_provider_settings_survive_restart_and_reconfigure_gateway(tmp_path: Path) -> None:
    path = tmp_path / "provider-settings.json"
    config = ProviderRoutingConfig(
        targets={
            "fast-local": ProviderTarget(
                name="fast-local",
                provider=ProviderName.OLLAMA,
                model="small-model",
            )
        },
        role_routes={LogicalRole.PLANNER: ProviderRoute("fast-local")},
        mode=ExecutionMode.FAST,
    )
    first_gateway = FakeGateway()
    await ProviderSettingsApplicationService(
        JsonProviderSettingsStore(path),
        gateway=cast(ProviderGateway, first_gateway),
    ).update_provider_settings(config)

    restarted_gateway = FakeGateway()
    restored = await ProviderSettingsApplicationService(
        JsonProviderSettingsStore(path),
        gateway=cast(ProviderGateway, restarted_gateway),
    ).initialize(
        ProviderRoutingConfig(
            targets={"default": ProviderTarget(name="default", provider=ProviderName.OLLAMA, model="default")},
            role_routes={LogicalRole.PLANNER: ProviderRoute("default")},
        )
    )

    assert restored.mode == ExecutionMode.FAST
    assert restored.targets["fast-local"]["model"] == "small-model"
    assert restarted_gateway.config is not None
    assert restarted_gateway.config.mode == ExecutionMode.FAST


async def test_playthrough_export_contains_canonical_records_and_is_json_safe() -> None:
    store, world, playthrough, branch = await _setup()
    store.characters.append(
        CharacterView(
            id="yuki",
            world_id=world.id,
            playthrough_id=playthrough.id,
            display_name="Yuki",
            aliases=(),
            public_profile={"role": "student"},
        )
    )
    store.events[branch.id] = [
        EventRecord(
            event_id="event-export",
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            turn_id="turn-export",
            event_type="arrival",
            world_time=1,
        )
    ]
    store.jobs.append(
        DerivedJobRecord(
            id="job-1",
            idempotency_key="summary:turn-export",
            job_type="summary",
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            source_turn_id="turn-export",
            source_revision=1,
        )
    )
    export = await PlaythroughExportApplicationService(_factory(store)).export_playthrough(playthrough.id)

    payload = export.as_dict()
    assert payload["format_version"] == "playthrough-export-1"
    assert payload["world"]["id"] == world.id
    assert payload["events"][0]["event_id"] == "event-export"
    assert isinstance(payload["exported_at"], str)
