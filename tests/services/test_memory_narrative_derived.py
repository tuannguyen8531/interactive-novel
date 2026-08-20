from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

import pytest

from src.application.contracts.persistence import (
    BeliefRecord,
    DerivedArtifactRecord,
    KnowledgeClaimRecord,
    NarrativeHookRecord,
    NarrativeThreadRecord,
    RelationshipChangeRecord,
    TurnRecord,
)
from src.application.contracts.providers import EmbeddingResponse
from src.application.contracts.retrieval import (
    MemoryCandidate,
    MemoryKind,
    RetrievalScope,
    RetrievalTrace,
    RetrievalTraceHit,
    ScoreBreakdown,
    content_hash,
)
from src.application.ports.providers import ProviderPort
from src.services.memory.analysis import (
    BeliefConflictDetector,
    HookPrioritizer,
    MemoryConsolidator,
    RelationshipTrendAnalyzer,
    RetrievalEvaluationService,
    ThreadStagnationDetector,
)
from src.services.memory.reconciliation import DerivedArtifactResolver
from src.services.retrieval.embeddings import InMemoryEmbeddingStore
from src.services.retrieval.rebuild import EmbeddingRebuildService

NOW = datetime.now(UTC)


def _turn(index: int, *, narrative: str | None = None) -> TurnRecord:
    return TurnRecord(
        id=f"turn-{index}",
        playthrough_id="playthrough-1",
        branch_id="root",
        parent_turn_id=None if index == 1 else f"turn-{index - 1}",
        raw_input=f"action {index}",
        normalized_input=None,
        base_revision=index - 1,
        status="completed",
        final_narrative=narrative or f"Routine scene {index}.",
        approved_patch={},
        world_time_start=index - 1,
        duration_minutes=1,
        world_time_end=index,
        turn_run_id=f"run-{index}",
        schema_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _candidate(source_id: str, *, time: int, text: str, salience: float = 0.5) -> MemoryCandidate:
    return MemoryCandidate(
        source_id=source_id,
        kind=MemoryKind.EVENT,
        playthrough_id="playthrough-1",
        branch_id="root",
        world_time=time,
        text=text,
        salience=salience,
        source_event_id=source_id,
    )


def _claim(claim_id: str, *, polarity: str) -> KnowledgeClaimRecord:
    return KnowledgeClaimRecord(
        claim_id=claim_id,
        playthrough_id="playthrough-1",
        branch_id="root",
        turn_id="turn-1",
        claim_type="relationship",
        subject_id="alice",
        predicate="likes",
        object_id="tea",
        typed_value=None,
        polarity=polarity,
        qualifiers={},
        valid_time_start=1,
        valid_time_end=None,
        branch_scope="public",
        normalized_fingerprint=claim_id,
        schema_version="knowledge-1",
    )


def test_consolidation_keeps_important_detail_and_canonical_provenance() -> None:
    turns = tuple(_turn(index) for index in range(1, 51))
    memories = [_candidate("event-key", time=33, text="Alice hid the brass key under the library atlas.", salience=0.99)]

    summaries = MemoryConsolidator(window_turns=10).consolidate(
        playthrough_id="playthrough-1",
        branch_id="root",
        source_revision=50,
        turns=turns,
        candidates=memories,
    )

    assert len(summaries) == 5
    matching = next(summary for summary in summaries if "brass key" in summary.text)
    assert matching.source_ids == ("event-key",)
    assert matching.derived is True
    assert matching.turn_ids == tuple(f"turn-{index}" for index in range(31, 41))


def test_belief_conflict_is_perspective_derived_not_a_canon_mutation() -> None:
    claims = (_claim("claim-positive", polarity="positive"), _claim("claim-negative", polarity="negative"))
    beliefs = (
        BeliefRecord(
            belief_id="belief-support",
            playthrough_id="playthrough-1",
            branch_id="root",
            turn_id="turn-2",
            believer_id="bob",
            claim_id="claim-positive",
            stance="supports",
            confidence=0.9,
            branch_scope="public",
            world_time=2,
            source_reliability=0.8,
        ),
        BeliefRecord(
            belief_id="belief-reject",
            playthrough_id="playthrough-1",
            branch_id="root",
            turn_id="turn-3",
            believer_id="bob",
            claim_id="claim-negative",
            stance="supports",
            confidence=0.8,
            branch_scope="public",
            world_time=3,
            source_reliability=0.7,
        ),
    )

    conflicts = BeliefConflictDetector().detect(beliefs, claims)

    assert len(conflicts) == 1
    assert set(conflicts[0].belief_ids) == {"belief-support", "belief-reject"}
    assert conflicts[0].severity > 0.0


def test_hooks_and_threads_prioritize_payoff_and_report_stagnation() -> None:
    threads = (
        NarrativeThreadRecord(
            thread_id="thread-festival",
            playthrough_id="playthrough-1",
            branch_id="root",
            turn_id="turn-1",
            status="active",
            progress=0.1,
            urgency=0.9,
            payload={"last_advanced_turn": 1, "last_advanced_world_time": 2},
        ),
    )
    hooks = (
        NarrativeHookRecord(
            hook_id="hook-festival",
            playthrough_id="playthrough-1",
            branch_id="root",
            turn_id="turn-1",
            status="active",
            payload={"thread_id": "thread-festival", "payoff_window_end": 90},
        ),
    )

    prioritized = HookPrioritizer().prioritize(hooks, threads, current_world_time=80)
    health = ThreadStagnationDetector(turn_threshold=5, world_time_threshold=60).analyze(
        threads,
        current_turn_index=12,
        current_world_time=80,
    )

    assert prioritized[0].hook_id == "hook-festival"
    assert "payoff_window_near" in prioritized[0].reasons
    assert health[0].stagnating is True
    assert "urgent_thread_stagnating" in health[0].reasons


def test_relationship_trend_and_retrieval_dashboard_are_rebuildable() -> None:
    changes = tuple(
        RelationshipChangeRecord(
            change_id=f"change-{index}",
            relationship_id="relationship:alice:bob",
            playthrough_id="playthrough-1",
            branch_id="root",
            turn_id=f"turn-{index}",
            dimension="trust",
            before=0.2 + index * 0.1,
            proposed_delta=0.1,
            validated_delta=0.1,
            after=0.3 + index * 0.1,
            cause_event_id=f"event-{index}",
            reason="shared secret",
            provenance={},
        )
        for index in range(3)
    )
    scope = RetrievalScope(
        playthrough_id="playthrough-1",
        branch_id="root",
        branch_ancestry=("root",),
        world_time=10,
    )
    score = ScoreBreakdown(0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.5)
    trace = RetrievalTrace(
        trace_id="trace-1",
        query_id="query-1",
        phase="initial",
        scope=scope,
        candidate_count=4,
        hard_filtered_count=2,
        hits=(RetrievalTraceHit(source_id="event-key", score=score, selected=True),),
        token_budget=100,
        estimated_tokens=20,
    )

    trends = RelationshipTrendAnalyzer().analyze(changes)
    dashboard = RetrievalEvaluationService().evaluate([trace], relevant_source_ids={"query-1": {"event-key"}})

    assert trends[0].direction == "rising"
    assert trends[0].sample_count == 3
    assert dashboard.recall_at_k == 1.0
    assert dashboard.hard_filter_rate == 0.5


class _CandidateSource:
    def __init__(self, candidates: Sequence[MemoryCandidate]) -> None:
        self.candidates = tuple(candidates)

    async def list_candidates(self, scope: RetrievalScope) -> tuple[MemoryCandidate, ...]:
        del scope
        return self.candidates


class _EmbeddingProvider:
    provider_name = "fake"
    model = "fake-embedding"

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> EmbeddingResponse:
        self.calls.append(tuple(texts))
        return EmbeddingResponse(
            provider=self.provider_name,
            model=model or self.model,
            embeddings=tuple((float(len(text)), 1.0) for text in texts),
        )


@pytest.mark.asyncio
async def test_embedding_rebuild_only_writes_derived_vectors() -> None:
    candidates = (_candidate("event-1", time=1, text="A canonical event."),)
    store = InMemoryEmbeddingStore()
    scope = RetrievalScope(playthrough_id="playthrough-1", branch_id="root", world_time=2)

    provider = _EmbeddingProvider()
    service = EmbeddingRebuildService(store)
    report = await service.rebuild(
        scope,
        _CandidateSource(candidates),
        provider=cast(ProviderPort, provider),
    )
    repeated = await service.rebuild(
        scope,
        _CandidateSource(candidates),
        provider=cast(ProviderPort, provider),
    )

    assert report.candidate_count == report.indexed_count == 1
    assert repeated.candidate_count == repeated.indexed_count == 1
    assert report.failed_source_ids == ()
    assert provider.calls == [("A canonical event.",)]
    assert (
        await store.get(
            source_id="event-1",
            content_hash=content_hash("A canonical event."),
            model="fake-embedding",
            embedding_version="phase-13-embedding-1",
        )
        is not None
    )


def test_missing_or_stale_artifact_falls_back_to_canonical_payload() -> None:
    artifact = DerivedArtifactRecord.new(
        artifact_type="episodic_summary",
        playthrough_id="playthrough-1",
        branch_id="root",
        source_turn_id="turn-2",
        source_revision=2,
        artifact_version="episodic-summary-1",
        payload={"text": "derived"},
    )
    resolver = DerivedArtifactResolver()

    fresh = resolver.resolve(artifact, source_revision=2, fallback=lambda: {"text": "canonical"})
    stale = resolver.resolve(artifact, source_revision=3, fallback=lambda: {"text": "canonical"})

    assert fresh.used_fallback is False
    assert cast(dict[str, object], fresh.value)["text"] == "derived"
    assert stale.used_fallback is True
    assert stale.value == {"text": "canonical"}
