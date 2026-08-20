from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

import pytest
from sqlalchemy import delete, func, select, update

from src.application.contracts.persistence import (
    BeliefEvidenceRecord,
    BeliefRecord,
    BranchRecord,
    CanonFactRecord,
    CanonicalTurnBundle,
    CharacterStateRecord,
    ClaimLinkRecord,
    EmotionalTensionRecord,
    EventRecord,
    KnowledgeClaimRecord,
    NarrativeHookRecord,
    NarrativeThreadRecord,
    ObservationRecord,
    PersistenceSnapshotError,
    RelationshipChangeRecord,
    RelationshipRecord,
    SnapshotRecord,
    utc_now,
)
from src.application.contracts.retrieval import EmbeddingMetadata, EmbeddingRecord, RetrievalScope, content_hash
from src.application.errors import IdempotencyConflictError, StaleBranchRevisionError
from src.application.ports.persistence import UowFactory
from src.application.services.branches import BranchApplicationService
from src.application.services.canonical_turns import CanonicalTurnApplicationService
from src.application.services.game_states import GameStateApplicationService
from src.application.services.playthroughs import PlaythroughApplicationService
from src.application.services.replay import ReplayApplicationService
from src.application.services.worlds import WorldApplicationService
from src.domain.codec import patch_to_payload, state_from_payload, state_to_payload
from src.domain.content import ConsentRecord, ConsentState, ContentPolicy, TopicBoundary
from src.domain.patch import AdvanceClock, StatePatch
from src.domain.state import GameState
from src.services.persistence.canonical import InjectedCommitFailure
from src.services.persistence.database import Database
from src.services.persistence.models import (
    BeliefEvidenceModel,
    BeliefModel,
    CanonFactModel,
    CharacterModel,
    CharacterStateModel,
    ClaimLinkModel,
    DerivedJobModel,
    EmotionalTensionModel,
    EventModel,
    EventParticipantModel,
    KnowledgeClaimModel,
    NarrativeHookModel,
    NarrativeThreadModel,
    ObservationModel,
    OutboxEventModel,
    RelationshipChangeModel,
    RelationshipModel,
    SnapshotModel,
    TurnModel,
)
from src.services.persistence.uow import make_uow_factory


async def _setup(database: Database) -> tuple[UowFactory, str, str, BranchRecord]:
    uow_factory = make_uow_factory(database)
    world = await WorldApplicationService(uow_factory).create_world(
        name="Phase 4 Test World",
        premise="A deterministic persistence fixture.",
        genre="test",
        tone="calm",
    )
    playthrough = await PlaythroughApplicationService(uow_factory).create_playthrough(
        world_id=world.id,
        rng_seed="phase-4-seed",
    )
    root = await BranchApplicationService(uow_factory).create_root_branch(
        playthrough_id=playthrough.id,
        branch_id="root-branch",
    )
    now = utc_now()
    async with database.session_factory() as session, session.begin():
        session.add_all(
            [
                CharacterModel(
                    id="char-yuki",
                    world_id=world.id,
                    playthrough_id=playthrough.id,
                    display_name="Yuki",
                    aliases=[],
                    profile={},
                    schema_version=1,
                    created_at=now,
                    updated_at=now,
                ),
                CharacterModel(
                    id="char-akira",
                    world_id=world.id,
                    playthrough_id=playthrough.id,
                    display_name="Akira",
                    aliases=[],
                    profile={},
                    schema_version=1,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
    return uow_factory, world.id, playthrough.id, root


def _patch_payload(branch_id: str, patch_id: str, *, base_world_time: int | None, duration: int) -> dict[str, object]:
    patch = StatePatch.from_operations(
        (AdvanceClock(duration),),
        branch_id=branch_id,
        base_world_time=base_world_time,
        patch_id=patch_id,
    )
    return patch_to_payload(patch)


def _bundle(
    *,
    playthrough_id: str,
    branch_id: str,
    turn_id: str,
    turn_run_id: str,
    base_revision: int,
    world_time_start: int,
    duration: int = 1,
    parent_turn_id: str | None = None,
    event_ids: Iterable[str] = (),
    full_artifacts: bool = False,
) -> CanonicalTurnBundle:
    world_time_end = world_time_start + duration
    event_records = tuple(
        EventRecord(
            event_id=event_id,
            playthrough_id=playthrough_id,
            branch_id=branch_id,
            turn_id=turn_id,
            event_type="conversation",
            world_time=world_time_end,
            location_id="clubroom",
            actor_ids=("char-yuki",),
            witness_ids=("char-akira",),
            payload={"event_id": event_id},
            provenance={"source": "test"},
        )
        for event_id in event_ids
    )
    claims: tuple[KnowledgeClaimRecord, ...] = ()
    canon_facts: tuple[CanonFactRecord, ...] = ()
    claim_links: tuple[ClaimLinkRecord, ...] = ()
    observations: tuple[ObservationRecord, ...] = ()
    beliefs: tuple[BeliefRecord, ...] = ()
    belief_evidence: tuple[BeliefEvidenceRecord, ...] = ()
    character_states: tuple[CharacterStateRecord, ...] = ()
    relationships: tuple[RelationshipRecord, ...] = ()
    relationship_changes: tuple[RelationshipChangeRecord, ...] = ()
    tensions: tuple[EmotionalTensionRecord, ...] = ()
    threads: tuple[NarrativeThreadRecord, ...] = ()
    hooks: tuple[NarrativeHookRecord, ...] = ()
    if full_artifacts:
        claims = (
            KnowledgeClaimRecord(
                claim_id="claim-moon",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                claim_type="knowledge_claim",
                subject_id="char-yuki",
                predicate="public_fact",
                object_id=None,
                typed_value={"fact": "the moon is visible"},
                polarity="positive",
                qualifiers={},
                valid_time_start=world_time_end,
                valid_time_end=None,
                branch_scope="public",
                normalized_fingerprint="a" * 64,
                schema_version="claim-1",
                provenance={"source": "test"},
            ),
            KnowledgeClaimRecord(
                claim_id="claim-clock",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                claim_type="knowledge_claim",
                subject_id="char-akira",
                predicate="public_fact",
                object_id=None,
                typed_value={"fact": "the clock is ticking"},
                polarity="positive",
                qualifiers={},
                valid_time_start=world_time_end,
                valid_time_end=None,
                branch_scope=branch_id,
                normalized_fingerprint="b" * 64,
                schema_version="claim-1",
            ),
        )
        canon_facts = (
            CanonFactRecord(
                fact_id="fact-moon",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                claim_id="claim-moon",
                status="active",
                source_event_or_rule="event-full",
                asserted_world_time=world_time_end,
                asserted_turn=turn_id,
            ),
        )
        claim_links = (
            ClaimLinkRecord(
                link_id="link-clock",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                from_claim_id="claim-moon",
                to_claim_id="claim-clock",
                kind="supports",
            ),
        )
        observations = (
            ObservationRecord(
                observation_id="observation-moon",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                observer_id="char-yuki",
                observed_claim_id="claim-moon",
                source_event_id="event-full",
                method="direct",
                world_time=world_time_end,
                confidence=0.9,
                distortion=0.1,
            ),
        )
        beliefs = (
            BeliefRecord(
                belief_id="belief-moon",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                believer_id="char-akira",
                claim_id="claim-moon",
                stance="supports",
                confidence=0.8,
                branch_scope=branch_id,
                world_time=world_time_end,
                source_reliability=0.75,
            ),
        )
        belief_evidence = (
            BeliefEvidenceRecord(
                evidence_id="evidence-moon",
                belief_id="belief-moon",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                owner_id="char-akira",
                source_event_id="event-full",
                claim_id="claim-moon",
                world_time=world_time_end,
                method="direct",
                confidence=0.8,
            ),
        )
        character_states = (
            CharacterStateRecord(
                character_id="char-yuki",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                state={"location_id": "clubroom", "condition": "healthy"},
                last_active_turn_id=turn_id,
            ),
        )
        relationships = (
            RelationshipRecord(
                relationship_id="relationship-yuki-akira",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                source_id="char-yuki",
                target_id="char-akira",
                values={"trust": 0.6},
            ),
        )
        relationship_changes = (
            RelationshipChangeRecord(
                change_id="relationship-change-1",
                relationship_id="relationship-yuki-akira",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                dimension="trust",
                before=0.0,
                proposed_delta=0.6,
                validated_delta=0.6,
                after=0.6,
                cause_event_id="event-full",
                reason="A trustworthy conversation.",
            ),
        )
        tensions = (
            EmotionalTensionRecord(
                tension_id="tension-1",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                observer_id="char-yuki",
                rival_id="char-akira",
                focus_id="char-yuki",
                intensity=0.2,
                payload={"source": "test"},
            ),
        )
        threads = (
            NarrativeThreadRecord(
                thread_id="thread-1",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                status="active",
                progress=0.25,
                urgency=0.4,
                payload={"premise": "A quiet clue."},
            ),
        )
        hooks = (
            NarrativeHookRecord(
                hook_id="hook-1",
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                status="open",
                payload={"setup": "A bell rings."},
            ),
        )
    return CanonicalTurnBundle(
        playthrough_id=playthrough_id,
        branch_id=branch_id,
        raw_input=f"input-{turn_id}",
        base_revision=base_revision,
        world_time_start=world_time_start,
        duration_minutes=duration,
        world_time_end=world_time_end,
        turn_run_id=turn_run_id,
        final_narrative=f"Narrative for {turn_id}",
        suggested_actions=(
            {"kind": "act", "text": "I follow the sound into the hallway."},
            {"kind": "observe", "text": "I inspect the clock more closely."},
        ),
        approved_patch=_patch_payload(
            branch_id,
            f"patch-{turn_id}",
            base_world_time=world_time_start,
            duration=duration,
        ),
        turn_id=turn_id,
        parent_turn_id=parent_turn_id,
        character_states=character_states,
        events=event_records,
        claims=claims,
        canon_facts=canon_facts,
        claim_links=claim_links,
        observations=observations,
        beliefs=beliefs,
        belief_evidence=belief_evidence,
        relationships=relationships,
        relationship_changes=relationship_changes,
        tensions=tensions,
        threads=threads,
        hooks=hooks,
    )


async def test_canonical_commit_writes_all_artifacts_and_is_idempotent(database: Database) -> None:
    uow_factory, _, playthrough_id, root = await _setup(database)
    service = CanonicalTurnApplicationService(uow_factory)
    bundle = _bundle(
        playthrough_id=playthrough_id,
        branch_id=root.id,
        turn_id="turn-full",
        turn_run_id="run-full",
        base_revision=0,
        world_time_start=0,
        event_ids=("event-full",),
        full_artifacts=True,
    )

    committed = await service.commit_turn(bundle)
    repeated = await service.commit_turn(bundle)

    assert committed.id == repeated.id == "turn-full"
    assert committed.suggested_actions == (
        {"kind": "act", "text": "I follow the sound into the hallway."},
        {"kind": "observe", "text": "I inspect the clock more closely."},
    )
    assert (await service.verify_invariants(root.id)).valid
    async with uow_factory() as uow:
        branch = await uow.canonical.get_branch(root.id)
        assert branch is not None
        assert branch.head_revision == 1
        assert branch.head_turn_id == "turn-full"
        assert len(await uow.canonical.list_visible_events(root.id)) == 1
        jobs = await uow.canonical.list_derived_jobs()
        assert {job.job_type for job in jobs} == {"snapshot", "summary", "embedding"}
        assert await uow.canonical.reconcile_derived_jobs() == 0

    async with database.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(TurnModel)) == 1
        assert await session.scalar(select(func.count()).select_from(EventModel)) == 1
        assert await session.scalar(select(func.count()).select_from(EventParticipantModel)) == 2
        assert await session.scalar(select(func.count()).select_from(KnowledgeClaimModel)) == 2
        assert await session.scalar(select(func.count()).select_from(CanonFactModel)) == 1
        assert await session.scalar(select(func.count()).select_from(ClaimLinkModel)) == 1
        assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 1
        assert await session.scalar(select(func.count()).select_from(BeliefModel)) == 1
        assert await session.scalar(select(func.count()).select_from(BeliefEvidenceModel)) == 1
        assert await session.scalar(select(func.count()).select_from(CharacterStateModel)) == 1
        assert await session.scalar(select(func.count()).select_from(RelationshipModel)) == 1
        assert await session.scalar(select(func.count()).select_from(RelationshipChangeModel)) == 1
        assert await session.scalar(select(func.count()).select_from(EmotionalTensionModel)) == 1
        assert await session.scalar(select(func.count()).select_from(NarrativeThreadModel)) == 1
        assert await session.scalar(select(func.count()).select_from(NarrativeHookModel)) == 1
        assert await session.scalar(select(func.count()).select_from(DerivedJobModel)) == 3
        assert await session.scalar(select(func.count()).select_from(OutboxEventModel)) == 1

    stale = _bundle(
        playthrough_id=playthrough_id,
        branch_id=root.id,
        turn_id="turn-stale",
        turn_run_id="run-stale",
        base_revision=0,
        world_time_start=0,
    )
    with pytest.raises(StaleBranchRevisionError):
        await service.commit_turn(stale)

    conflicting = replace(bundle, raw_input="different-input")
    with pytest.raises(IdempotencyConflictError):
        await service.commit_turn(conflicting)


@pytest.mark.parametrize(
    "failure_step",
    ("head_revision", "turn", "events", "knowledge", "observations", "relationships", "narrative", "outbox", "head_update"),
)
async def test_each_canonical_commit_failure_rolls_back_cleanly(database: Database, failure_step: str) -> None:
    uow_factory, _, playthrough_id, root = await _setup(database)
    service = CanonicalTurnApplicationService(uow_factory)
    bundle = _bundle(
        playthrough_id=playthrough_id,
        branch_id=root.id,
        turn_id=f"turn-failure-{failure_step}",
        turn_run_id=f"run-failure-{failure_step}",
        base_revision=0,
        world_time_start=0,
    )

    with pytest.raises(InjectedCommitFailure):
        await service.commit_turn(bundle, fail_after_step=failure_step)

    async with uow_factory() as uow:
        branch = await uow.canonical.get_branch(root.id)
        assert branch is not None
        assert branch.head_revision == 0
        assert branch.head_turn_id is None
        assert await uow.canonical.get_turn(bundle.turn_id) is None
        assert await uow.canonical.list_visible_events(root.id) == []
        assert await uow.canonical.list_derived_jobs() == []


async def test_fork_regenerate_and_visible_history_do_not_mix_branches(database: Database) -> None:
    uow_factory, _, playthrough_id, root = await _setup(database)
    branches = BranchApplicationService(uow_factory)
    turns = CanonicalTurnApplicationService(uow_factory)

    root_turn = await turns.commit_turn(
        _bundle(
            playthrough_id=playthrough_id,
            branch_id=root.id,
            turn_id="turn-root",
            turn_run_id="run-root",
            base_revision=0,
            world_time_start=0,
            event_ids=("event-root",),
        )
    )
    child = await branches.fork_branch(parent_branch_id=root.id, fork_turn_id=root_turn.id, branch_id="child-branch")
    sibling = await branches.regenerate_branch(
        parent_branch_id=root.id,
        fork_turn_id=root_turn.id,
        branch_id="sibling-branch",
    )
    await turns.commit_turn(
        _bundle(
            playthrough_id=playthrough_id,
            branch_id=child.id,
            turn_id="turn-child",
            turn_run_id="run-child",
            base_revision=0,
            world_time_start=1,
            parent_turn_id=root_turn.id,
            event_ids=("event-child",),
        )
    )
    await turns.commit_turn(
        _bundle(
            playthrough_id=playthrough_id,
            branch_id=sibling.id,
            turn_id="turn-sibling",
            turn_run_id="run-sibling",
            base_revision=0,
            world_time_start=1,
            parent_turn_id=root_turn.id,
            event_ids=("event-sibling",),
        )
    )
    await turns.commit_turn(
        _bundle(
            playthrough_id=playthrough_id,
            branch_id=root.id,
            turn_id="turn-root-future",
            turn_run_id="run-root-future",
            base_revision=1,
            world_time_start=1,
            parent_turn_id=root_turn.id,
            event_ids=("event-root-future",),
        )
    )

    async with uow_factory() as uow:
        root_events = await uow.canonical.list_visible_events(root.id)
        child_events = await uow.canonical.list_visible_events(child.id)
        sibling_events = await uow.canonical.list_visible_events(sibling.id)
        assert {event.event_id for event in root_events} == {"event-root", "event-root-future"}
        assert {event.event_id for event in child_events} == {"event-root", "event-child"}
        assert {event.event_id for event in sibling_events} == {"event-root", "event-sibling"}
        child_candidates = await uow.retrieval.list_candidates(
            RetrievalScope(
                playthrough_id=playthrough_id,
                branch_id=child.id,
                branch_ancestry=(root.id, child.id),
                world_time=100,
            )
        )
        assert {item.source_id for item in child_candidates if item.kind == "event"} == {
            "event-root",
            "event-child",
        }
        assert [item.id for item in await uow.canonical.get_branch_ancestry(child.id)] == [root.id, child.id]
        assert (await uow.canonical.get_branch(root.id)).head_revision == 2  # type: ignore[union-attr]

    child_state = await GameStateApplicationService(uow_factory).load(
        playthrough_id=playthrough_id,
        branch_id=child.id,
    )
    assert child_state.branch_id == child.id
    assert child_state.branch_ancestry == (root.id, child.id)
    assert child_state.world_time == 2


async def test_replay_snapshot_fallback_and_derived_failure_leave_canon_intact(database: Database) -> None:
    uow_factory, world_id, playthrough_id, root = await _setup(database)
    turns = CanonicalTurnApplicationService(uow_factory)
    bundle = _bundle(
        playthrough_id=playthrough_id,
        branch_id=root.id,
        turn_id="turn-replay",
        turn_run_id="run-replay",
        base_revision=0,
        world_time_start=0,
        event_ids=("event-replay",),
    )
    turn = await turns.commit_turn(bundle)
    initial = GameState.empty(world_id=world_id, playthrough_id=playthrough_id, branch_id=root.id)
    replay = ReplayApplicationService(uow_factory)

    rebuilt = await replay.replay_branch(branch_id=root.id, initial_state=initial)
    assert rebuilt.world_time == 1

    snapshot = SnapshotRecord.from_payload(
        playthrough_id=playthrough_id,
        branch_id=root.id,
        source_turn_id=turn.id,
        source_revision=1,
        world_clock_minutes=rebuilt.world_time,
        rng_state={"position": 1},
        state_payload=state_to_payload(rebuilt),
    )
    await turns.save_snapshot(snapshot)
    from_snapshot = await replay.replay_branch(branch_id=root.id, initial_state=initial)
    assert from_snapshot.world_time == 1

    invalid = SnapshotRecord(
        playthrough_id=playthrough_id,
        branch_id=root.id,
        source_turn_id=turn.id,
        source_revision=1,
        world_clock_minutes=1,
        rng_state={},
        state_payload=state_to_payload(rebuilt),
        checksum="invalid",
    )
    with pytest.raises(PersistenceSnapshotError):
        await turns.save_snapshot(invalid)

    async with uow_factory() as uow:
        job = (await uow.canonical.list_derived_jobs())[0]
        await uow.canonical.mark_derived_job(job.id, status="failed", error="summary unavailable")
        await uow.commit()
    async with uow_factory() as uow:
        assert await uow.canonical.get_turn(turn.id) is not None
        assert (await uow.canonical.get_branch(root.id)).head_revision == 1  # type: ignore[union-attr]

    async with database.session_factory() as session, session.begin():
        await session.execute(
            update(SnapshotModel).where(SnapshotModel.id == snapshot.snapshot_id).values(state_payload={"corrupted": True})
        )
    after_corruption = await replay.replay_branch(branch_id=root.id, initial_state=initial)
    assert after_corruption.world_time == 1
    report = await turns.verify_invariants(root.id)
    assert not report.valid
    assert any("snapshot_checksum_mismatch" in violation for violation in report.violations)

    async with database.session_factory() as session, session.begin():
        await session.execute(delete(DerivedJobModel).where(DerivedJobModel.job_type == "embedding"))
    async with uow_factory() as uow:
        assert await uow.canonical.reconcile_derived_jobs() == 1


def test_snapshot_codec_round_trips_consent_and_player_policy() -> None:
    policy = ContentPolicy.from_mapping(
        {
            "schema_version": "content-1",
            "rating": "teen_14_plus",
            "topic_boundaries": {"dating": TopicBoundary.OPT_IN},
        },
        player_overrides={"adult_explicit_opt_in": True, "topic_boundaries": {"dating": TopicBoundary.EXCLUDED}},
    )
    state = GameState.empty(policy=policy)
    state.consents[("scene-1", "char-yuki", "dating")] = ConsentRecord(
        scene_id="scene-1",
        participant_id="char-yuki",
        activity_tag="dating",
        state=ConsentState.REQUESTED,
        requested_at=5,
    )

    restored = state_from_payload(state_to_payload(state))

    assert restored.consents[("scene-1", "char-yuki", "dating")].state == ConsentState.REQUESTED
    assert restored.policy == policy


async def test_embedding_store_bulk_loads_only_requested_model_and_version(database: Database) -> None:
    uow_factory, _, playthrough_id, root = await _setup(database)
    records = tuple(
        EmbeddingRecord(
            metadata=EmbeddingMetadata(
                source_id=f"memory-{index}",
                source_kind="event",
                playthrough_id=playthrough_id,
                branch_id=root.id,
                model="nomic-embed-text",
                dimensions=2,
                embedding_version="hybrid-v1",
                content_hash=content_hash(f"memory text {index}"),
            ),
            vector=(float(index), 1.0),
        )
        for index in range(2)
    )
    async with uow_factory() as uow:
        for record in records:
            await uow.retrieval.save(record)
        await uow.commit()

    async with uow_factory() as uow:
        loaded = await uow.retrieval.list_for_sources(
            ("memory-0", "memory-1", "missing"),
            model="nomic-embed-text",
            embedding_version="hybrid-v1",
        )
        wrong_version = await uow.retrieval.list_for_sources(
            ("memory-0", "memory-1"),
            model="nomic-embed-text",
            embedding_version="hybrid-v2",
        )

    assert {record.metadata.source_id for record in loaded} == {"memory-0", "memory-1"}
    assert wrong_version == ()
