from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from src.application.contracts.ai import WorldSeed
from src.application.contracts.persistence import BranchRecord, TurnRecord, utc_now
from src.application.errors import ApplicationValidationError
from src.application.ports.persistence import UowFactory
from src.application.services.world_drafts import WorldDraftApplicationService

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ai" / "role_outputs.json"


def _seed() -> WorldSeed:
    return WorldSeed.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"])


class _State:
    def __init__(self) -> None:
        self.worlds: dict[str, Any] = {}
        self.characters: dict[str, Any] = {}
        self.playthroughs: dict[str, Any] = {}
        self.branches: dict[str, BranchRecord] = {}
        self.bundle: Any | None = None


class _Worlds:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def add(self, world: Any) -> None:
        self.state.worlds[world.id] = world


class _Characters:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def add(self, character: Any) -> None:
        self.state.characters[character.id] = character


class _Playthroughs:
    def __init__(self, state: _State) -> None:
        self.state = state

    async def add(self, playthrough: Any) -> None:
        self.state.playthroughs[playthrough.id] = playthrough

    async def set_root_branch(self, playthrough_id: str, branch_id: str) -> None:
        self.state.playthroughs[playthrough_id] = replace(
            self.state.playthroughs[playthrough_id],
            root_branch_id=branch_id,
            active_branch_id=branch_id,
        )


class _Canonical:
    def __init__(self, state: _State, *, fail: bool = False) -> None:
        self.state = state
        self.fail = fail

    async def add_branch(self, branch: BranchRecord) -> None:
        self.state.branches[branch.id] = branch

    async def commit_turn(self, bundle: Any, *, fail_after_step: str | None = None) -> TurnRecord:
        del fail_after_step
        self.state.bundle = bundle
        if self.fail:
            raise RuntimeError("simulated canonical failure")
        now = utc_now()
        return TurnRecord(
            id=bundle.turn_id,
            playthrough_id=bundle.playthrough_id,
            branch_id=bundle.branch_id,
            parent_turn_id=bundle.parent_turn_id,
            raw_input=bundle.raw_input,
            normalized_input=bundle.normalized_input,
            base_revision=bundle.base_revision,
            status="completed",
            final_narrative=bundle.final_narrative,
            approved_patch=bundle.approved_patch,
            world_time_start=bundle.world_time_start,
            duration_minutes=bundle.duration_minutes,
            world_time_end=bundle.world_time_end,
            turn_run_id=bundle.turn_run_id,
            schema_version=bundle.schema_version,
            created_at=now,
            updated_at=now,
        )


class _Uow:
    def __init__(self, store: _State, *, fail: bool = False) -> None:
        self.store = store
        self.pending = _State()
        self.worlds = _Worlds(self.pending)
        self.characters = _Characters(self.pending)
        self.playthroughs = _Playthroughs(self.pending)
        self.canonical = _Canonical(self.pending, fail=fail)
        self.committed = False

    async def __aenter__(self) -> _Uow:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if exc_type is not None:
            self.pending = _State()

    async def commit(self) -> None:
        self.store.worlds.update(self.pending.worlds)
        self.store.characters.update(self.pending.characters)
        self.store.playthroughs.update(self.pending.playthroughs)
        self.store.branches.update(self.pending.branches)
        self.store.bundle = self.pending.bundle
        self.committed = True


class _Generator:
    def __init__(self, seed: WorldSeed) -> None:
        self.seed = seed

    async def generate_world_draft(self, prompt: str) -> WorldSeed:
        assert prompt
        return self.seed


def _factory(store: _State, *, fail: bool = False) -> UowFactory:
    return cast(UowFactory, lambda: _Uow(store, fail=fail))


@pytest.mark.asyncio
async def test_world_builder_keeps_generated_draft_transient_until_confirmed() -> None:
    store = _State()
    service = WorldDraftApplicationService(_factory(store), generator=_Generator(_seed()))

    draft = await service.generate_world_draft("A gentle school romance around a culture club.")

    assert draft.title == "The Quiet Courtyard"
    assert store.worlds == {}
    assert store.characters == {}
    assert store.playthroughs == {}


@pytest.mark.asyncio
async def test_confirm_creates_playable_opening_bundle_with_canonical_artifacts() -> None:
    store = _State()
    service = WorldDraftApplicationService(_factory(store), generator=_Generator(_seed()))

    result = await service.confirm_world_bundle(await service.generate_world_draft("school romance"))
    bundle = store.bundle

    assert result.world.id in store.worlds
    assert len(store.characters) == 3
    assert result.playthrough.root_branch_id == result.branch.id
    assert result.branch.head_revision == 1
    assert bundle is not None
    expected_claim_count = len(_seed().initial_claims) + len(_seed().opening_scene.participants)
    assert len(bundle.claims) == len(bundle.canon_facts) == expected_claim_count
    assert len(bundle.character_states) == len(_seed().opening_scene.participants)
    assert {
        (claim.subject_id, claim.predicate, claim.object_id) for claim in bundle.claims if claim.predicate == "located_at"
    } == {("player", "located_at", "library"), ("alice", "located_at", "library")}
    assert len(bundle.relationships) == 1
    assert len(bundle.threads) == len(bundle.hooks) == 1
    assert bundle.events[0].event_type == "opening_scene"
    assert result.opening_turn.id == bundle.turn_id


@pytest.mark.asyncio
async def test_failed_confirmation_rolls_back_staged_world_builder_records() -> None:
    store = _State()
    service = WorldDraftApplicationService(_factory(store, fail=True), generator=_Generator(_seed()))

    with pytest.raises(RuntimeError, match="simulated canonical failure"):
        await service.confirm_world_bundle(_seed())

    assert store.worlds == {}
    assert store.characters == {}
    assert store.playthroughs == {}
    assert store.branches == {}


def test_world_builder_rejects_duplicate_character_aliases_before_persistence() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    payload = copy.deepcopy(payload)
    payload["npc_profiles"][0]["aliases"] = ["player"]

    with pytest.raises(ApplicationValidationError, match="unique"):
        WorldDraftApplicationService(_factory(_State())).validate_world_draft(WorldSeed.model_validate(payload))


def test_world_builder_rejects_obvious_opposite_canon_claims() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    payload = copy.deepcopy(payload)
    opposite = copy.deepcopy(payload["initial_claims"][0])
    opposite["proposal_id"] = "claim-alice-tea-negative"
    opposite["polarity"] = "negative"
    payload["initial_claims"].append(opposite)

    with pytest.raises(ApplicationValidationError, match="opposite polarities"):
        WorldDraftApplicationService(_factory(_State())).validate_world_draft(WorldSeed.model_validate(payload))


def test_world_builder_rejects_unknown_story_template() -> None:
    seed = _seed().model_copy(update={"template_id": "not_registered"})

    with pytest.raises(ApplicationValidationError, match="Unknown story template"):
        WorldDraftApplicationService(_factory(_State())).validate_world_draft(seed)
