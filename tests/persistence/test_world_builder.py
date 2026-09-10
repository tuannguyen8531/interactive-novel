from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select

from src.application.contracts.ai import WorldSeed
from src.application.contracts.persistence import CanonicalTurnBundle
from src.application.errors import ApplicationValidationError, ResourceNotFoundError
from src.application.services.canonical_turns import CanonicalTurnApplicationService
from src.application.services.derived import DerivedJobApplicationService
from src.application.services.export import PlaythroughExportApplicationService
from src.application.services.game_states import GameStateApplicationService
from src.application.services.world_drafts import WorldDraftApplicationService
from src.application.services.worlds import WorldApplicationService
from src.domain.codec import patch_to_payload
from src.domain.language import StoryLanguage
from src.domain.patch import AdvanceClock, StatePatch
from src.services.persistence.models import (
    Base,
    BeliefModel,
    CanonFactModel,
    CharacterStateModel,
    KnowledgeClaimModel,
    NarrativeHookModel,
    RelationshipModel,
    RetrievalTraceModel,
)
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
        character_states = await session.scalar(
            select(func.count())
            .select_from(CharacterStateModel)
            .where(CharacterStateModel.playthrough_id == confirmation.playthrough.id)
        )
        claims = await session.scalar(
            select(func.count())
            .select_from(KnowledgeClaimModel)
            .where(KnowledgeClaimModel.playthrough_id == confirmation.playthrough.id)
        )
        canon_facts = await session.scalar(
            select(func.count()).select_from(CanonFactModel).where(CanonFactModel.playthrough_id == confirmation.playthrough.id)
        )

    assert beliefs == 1
    assert hooks == 1
    assert stored_relationships == 1
    assert character_states == len(payload["opening_scene"]["participants"])
    assert claims == canon_facts == len(payload["initial_claims"]) + len(payload["opening_scene"]["participants"])


async def test_two_worlds_may_share_a_name_and_character_ids_remain_globally_unique(database) -> None:
    seed = WorldSeed.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"])
    service = WorldDraftApplicationService(make_uow_factory(database))

    first = await service.confirm_world_bundle(seed)
    second = await service.confirm_world_bundle(seed)

    async with make_uow_factory(database)() as uow:
        first_characters = await uow.characters.list(world_id=first.world.id)
        second_characters = await uow.characters.list(world_id=second.world.id)

    assert first.world.name == second.world.name
    assert {character.id for character in first_characters}.isdisjoint(character.id for character in second_characters)
    assert all(UUID(character.id).version == 4 for character in (*first_characters, *second_characters))
    assert {character.role for character in first_characters} == {"player", "npc"}


async def test_confirmed_vietnamese_world_keeps_language_and_localized_opening(database) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    seed = WorldSeed.model_validate(payload).model_copy(update={"story_language": StoryLanguage.VIETNAMESE})
    confirmation = await WorldDraftApplicationService(make_uow_factory(database)).confirm_world_bundle(seed)

    assert confirmation.world.canon_rules["story_language"] == "vi"
    assert confirmation.opening_turn.final_narrative is not None
    assert "bắt đầu tại" in confirmation.opening_turn.final_narrative
    assert "Có mặt:" in confirmation.opening_turn.final_narrative


async def test_game_state_hydrates_seed_replays_turn_and_builds_snapshot(database) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    payload["tensions"] = [
        {
            "tension_id": "tension-alice-bob-player",
            "observer_id": "alice",
            "rival_id": "bob",
            "focus_id": "player",
            "appraisal": "Alice worries Bob will earn the player's trust first.",
        }
    ]
    seed = WorldSeed.model_validate(payload)
    uow_factory = make_uow_factory(database)
    confirmation = await WorldDraftApplicationService(uow_factory).confirm_world_bundle(seed)
    game_states = GameStateApplicationService(uow_factory)

    opening = await game_states.load(
        playthrough_id=confirmation.playthrough.id,
        branch_id=confirmation.branch.id,
    )
    canonical_seed = WorldSeed.model_validate(confirmation.world.canon_rules["world_seed"])
    assert opening.world_time == seed.opening_scene.world_time
    assert set(opening.characters) == {
        canonical_seed.player_character.character_id,
        *(character.character_id for character in canonical_seed.npc_profiles),
    }
    assert {claim.proposal_id for claim in canonical_seed.initial_claims}.issubset(opening.claims)
    assert {
        (claim.subject_id, claim.predicate, claim.object_id)
        for claim in opening.claims.values()
        if claim.predicate == "located_at"
    } == {
        (character_id, "located_at", canonical_seed.locations[0].location_id)
        for character_id in canonical_seed.opening_scene.participants
    }
    assert len(opening.relationships) == len(seed.initial_relationships)
    alice_id = next(
        character_id for character_id, character in opening.characters.items() if character.profile.display_name == "Alice"
    )
    assert opening.metadata["character_goals"][alice_id][0]["goal_id"] == "goal_alice"
    assert UUID(opening.metadata["emotional_tensions"][0]["tension_id"]).version == 4
    assert opening.policy is not None
    assert {event.event_type for event in opening.events.values()} == {"opening_scene"}
    assert all(
        opening.characters[character_id].state.location_id == seed.locations[0].location_id
        for character_id in canonical_seed.opening_scene.participants
    )
    assert opening.location_details[seed.locations[0].location_id].name == seed.locations[0].name
    assert opening.location_details[seed.locations[0].location_id].description == seed.locations[0].description

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


async def test_export_bundle_can_restore_a_deleted_playthrough(database) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    uow_factory = make_uow_factory(database)
    confirmation = await WorldDraftApplicationService(uow_factory).confirm_world_bundle(WorldSeed.model_validate(payload))
    exports = PlaythroughExportApplicationService(uow_factory)
    bundle = await exports.export_bundle(confirmation.playthrough.id)

    await WorldApplicationService(uow_factory).delete_world(confirmation.world.id)
    restored = await exports.import_bundle(bundle.as_bytes())
    state = await GameStateApplicationService(uow_factory).load(
        playthrough_id=restored.playthrough.id,
        branch_id=restored.playthrough.root_branch_id or "",
    )

    assert restored.world.id == confirmation.world.id
    assert restored.playthrough.id == confirmation.playthrough.id
    assert len(restored.turns) == 1
    assert state.world_time == confirmation.opening_scene.world_time
    assert set(state.characters) == {character.id for character in restored.characters}


async def test_import_rejects_non_uuid_character_ids(database) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    uow_factory = make_uow_factory(database)
    confirmation = await WorldDraftApplicationService(uow_factory).confirm_world_bundle(WorldSeed.model_validate(payload))
    exports = PlaythroughExportApplicationService(uow_factory)
    bundle = await exports.export_bundle(confirmation.playthrough.id)
    invalid_payload = deepcopy(bundle.payload)
    invalid_payload["world"]["canon_rules"]["world_seed"]["player_character"]["character_id"] = "player"
    encoded = json.dumps(invalid_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    invalid_bundle = replace(bundle, payload=invalid_payload, sha256=hashlib.sha256(encoded).hexdigest())
    await WorldApplicationService(uow_factory).delete_world(confirmation.world.id)

    with pytest.raises(ApplicationValidationError, match="UUID character IDs"):
        await exports.import_bundle(invalid_bundle.as_bytes())


async def test_delete_world_removes_the_complete_confirmed_aggregate(database) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    uow_factory = make_uow_factory(database)
    confirmation = await WorldDraftApplicationService(uow_factory).confirm_world_bundle(WorldSeed.model_validate(payload))

    async with database.session_factory() as session, session.begin():
        session.add(
            RetrievalTraceModel(
                id="trace-delete-world",
                query_id="query-delete-world",
                phase="planning",
                playthrough_id=confirmation.playthrough.id,
                branch_id=confirmation.branch.id,
                owner_id=None,
                world_time=0,
                payload={"safe": True},
                created_at=confirmation.world.created_at,
            )
        )

    worlds = WorldApplicationService(uow_factory)
    await worlds.delete_world(confirmation.world.id)

    async with database.session_factory() as session:
        remaining = {
            table.name: await session.scalar(select(func.count()).select_from(table)) for table in Base.metadata.tables.values()
        }

    assert all(count == 0 for count in remaining.values()), remaining
    with pytest.raises(ResourceNotFoundError):
        await worlds.delete_world(confirmation.world.id)
