from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from src.application.contracts.ai import WorldSeed
from src.application.contracts.persistence import CanonicalTurnBundle
from src.application.services.canonical_turns import CanonicalTurnApplicationService
from src.application.services.derived import DerivedJobApplicationService
from src.application.services.game_states import GameStateApplicationService
from src.application.services.world_drafts import WorldDraftApplicationService
from src.domain.codec import patch_to_payload
from src.domain.patch import AdvanceClock, StatePatch
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


async def test_game_state_hydrates_seed_replays_turn_and_builds_snapshot(database) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    seed = WorldSeed.model_validate(payload)
    uow_factory = make_uow_factory(database)
    confirmation = await WorldDraftApplicationService(uow_factory).confirm_world_bundle(seed)
    game_states = GameStateApplicationService(uow_factory)

    opening = await game_states.load(
        playthrough_id=confirmation.playthrough.id,
        branch_id=confirmation.branch.id,
    )
    assert opening.world_time == seed.opening_scene.world_time
    assert set(opening.characters) == {
        seed.player_character.character_id,
        *(character.character_id for character in seed.npc_profiles),
    }
    assert set(opening.claims) == {claim.proposal_id for claim in seed.initial_claims}
    assert len(opening.relationships) == len(seed.initial_relationships)
    assert opening.policy is not None
    assert {event.event_type for event in opening.events.values()} == {"opening_scene"}
    assert all(
        opening.characters[character_id].state.location_id == seed.locations[0].location_id
        for character_id in seed.opening_scene.participants
    )

    duration = 5
    patch = StatePatch.from_operations(
        (AdvanceClock(duration),),
        branch_id=confirmation.branch.id,
        base_world_time=opening.world_time,
        patch_id="patch-after-opening",
    )
    turn = await CanonicalTurnApplicationService(uow_factory).commit_turn(
        CanonicalTurnBundle(
            playthrough_id=confirmation.playthrough.id,
            branch_id=confirmation.branch.id,
            raw_input="Wait five minutes",
            base_revision=1,
            world_time_start=opening.world_time,
            duration_minutes=duration,
            world_time_end=opening.world_time + duration,
            turn_run_id="run-after-opening",
            final_narrative="Five minutes pass.",
            approved_patch=patch_to_payload(patch),
            turn_id="turn-after-opening",
            parent_turn_id=confirmation.opening_turn.id,
        )
    )

    rebuilt = await game_states.load(
        playthrough_id=confirmation.playthrough.id,
        branch_id=confirmation.branch.id,
    )
    assert rebuilt.world_time == opening.world_time + duration

    processed = await DerivedJobApplicationService(uow_factory, game_states=game_states).process_pending()
    assert len(processed) == 3
    assert {job.job_type: job.status for job in processed} == {
        "snapshot": "completed",
        "summary": "completed",
        "embedding": "failed",
    }
    async with uow_factory() as uow:
        snapshot = await uow.canonical.load_latest_snapshot(confirmation.branch.id)
        jobs = await uow.canonical.list_derived_jobs()
    assert snapshot is not None
    assert snapshot.source_turn_id == turn.id
    assert snapshot.world_clock_minutes == rebuilt.world_time
    assert len(jobs) == 3
