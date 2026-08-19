from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from src.application.contracts.ai import WorldSeed
from src.application.services.world_drafts import WorldDraftApplicationService
from src.services.persistence.models import BeliefModel, NarrativeHookModel, RelationshipModel
from src.services.persistence.uow import make_uow_factory

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ai" / "role_outputs.json"


async def test_confirmed_world_builder_seed_round_trips_all_opening_artifacts(database) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    payload["initial_beliefs"] = [
        {
            "belief_id": "belief-alice-tea",
            "believer_id": "alice",
            "claim_id": "claim-alice-tea",
            "stance": "supports",
            "confidence": 0.9,
            "evidence_ids": ["tea-menu"],
            "counter_evidence_ids": [],
            "branch_scope": "public",
            "world_time": 0,
            "source_reliability": 0.8,
        }
    ]
    service = WorldDraftApplicationService(make_uow_factory(database))

    confirmation = await service.confirm_world_bundle(WorldSeed.model_validate(payload))

    async with make_uow_factory(database)() as uow:
        assert await uow.worlds.get(confirmation.world.id) is not None
        assert await uow.playthroughs.get(confirmation.playthrough.id) is not None
        turns = await uow.canonical.list_turns(confirmation.playthrough.id)
        events = await uow.canonical.list_visible_events(confirmation.branch.id)
        relationships = await uow.inspection.inspect_relationships(
            playthrough_id=confirmation.playthrough.id,
            branch_id=confirmation.branch.id,
        )

    assert len(turns) == 1
    assert events[0].event_type == "opening_scene"
    assert len(relationships) == 1

    async with database.session_factory() as session:
        beliefs = await session.scalar(
            select(func.count()).select_from(BeliefModel).where(BeliefModel.playthrough_id == confirmation.playthrough.id)
        )
        hooks = await session.scalar(
            select(func.count())
            .select_from(NarrativeHookModel)
            .where(NarrativeHookModel.playthrough_id == confirmation.playthrough.id)
        )
        stored_relationships = await session.scalar(
            select(func.count())
            .select_from(RelationshipModel)
            .where(RelationshipModel.playthrough_id == confirmation.playthrough.id)
        )

    assert beliefs == 1
    assert hooks == 1
    assert stored_relationships == 1
