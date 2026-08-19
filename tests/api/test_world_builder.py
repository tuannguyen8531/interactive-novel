from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from src.api.factory import create_app
from src.application.contracts.ai import WorldSeed
from src.application.contracts.persistence import BranchRecord, PlaythroughRecord, TurnRecord, WorldRecord, utc_now
from src.application.services.world_drafts import WorldConfirmation
from src.config import Settings

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ai" / "role_outputs.json"


class _WorldDraftService:
    def __init__(self, seed: WorldSeed) -> None:
        self.seed = seed
        self.confirmations = 0

    async def generate_world_draft(self, prompt: str) -> WorldSeed:
        assert prompt
        return self.seed

    def validate_world_draft(self, seed: WorldSeed) -> WorldSeed:
        assert seed.role == self.seed.role
        return seed

    async def confirm_world_bundle(self, seed: WorldSeed, *, world_id: str | None = None) -> WorldConfirmation:
        assert seed.role == self.seed.role
        self.confirmations += 1
        world = WorldRecord.new(world_id=world_id or "world-confirmed", name=seed.title)
        playthrough = PlaythroughRecord.new(world_id=world.id, player_character_id=seed.player_character.character_id)
        branch = BranchRecord.root(playthrough_id=playthrough.id, branch_id="branch-confirmed")
        playthrough = replace(playthrough, root_branch_id=branch.id, active_branch_id=branch.id)
        turn = TurnRecord(
            id="opening-turn",
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            parent_turn_id=None,
            raw_input="World Builder opening scene",
            normalized_input=None,
            base_revision=0,
            status="completed",
            final_narrative="Opening scene.",
            approved_patch={},
            world_time_start=0,
            duration_minutes=0,
            world_time_end=0,
            turn_run_id="opening-run",
            schema_version=1,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        return WorldConfirmation(
            world,
            playthrough,
            replace(branch, head_turn_id=turn.id, head_revision=1),
            seed.opening_scene,
            turn,
        )


@pytest.mark.asyncio
async def test_world_builder_endpoints_generate_review_and_confirm_without_raw_db_access() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    seed = WorldSeed.model_validate(payload)
    world_drafts = _WorldDraftService(seed)
    app = create_app(
        Settings(app_name="world-builder-api-test"),
        services=SimpleNamespace(world_drafts=world_drafts),  # type: ignore[arg-type]
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        generated = await client.post("/api/world-drafts", json={"prompt": "A gentle school romance."})
        edited = dict(generated.json())
        edited["title"] = "Edited Courtyard"
        validated = await client.post("/api/world-drafts/validate", json={"draft": edited})
        confirmed = await client.post("/api/world-drafts/confirm", json={"draft": edited, "world_id": "world-api"})

    assert generated.status_code == 200
    assert validated.status_code == 200
    assert validated.json()["title"] == "Edited Courtyard"
    assert confirmed.status_code == 201
    assert confirmed.json()["world"]["id"] == "world-api"
    assert confirmed.json()["opening_scene"]["scene_id"] == "opening-scene"
    assert world_drafts.confirmations == 1
