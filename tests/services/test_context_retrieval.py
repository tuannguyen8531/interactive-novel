from __future__ import annotations

from typing import cast

import pytest

from src.application.contracts.ai import (
    AIPromptRole,
    AIProvenance,
    KnowledgeClaimProposal,
    NPCReaction,
    SimulationResult,
    ValidationQuery,
)
from src.application.contracts.providers import EmbeddingResponse, ProviderCapability
from src.application.contracts.retrieval import (
    InitialContextRequest,
    MemoryCandidate,
    MemoryKind,
    RetrievalScope,
)
from src.application.ports.providers import ProviderPort
from src.services.retrieval.claims import ClaimExtractor
from src.services.retrieval.context import ContextAssembler
from src.services.retrieval.embeddings import InMemoryEmbeddingStore, OllamaEmbeddingIndexer, cosine_similarity
from src.services.retrieval.tracing import InMemoryRetrievalTraceStore


def _scope(*, branch: str = "child", time: int = 20, owner: str | None = "bob") -> RetrievalScope:
    return RetrievalScope(
        playthrough_id="playthrough-1",
        branch_id=branch,
        branch_ancestry=("root", branch),
        world_time=time,
        owner_id=owner,
    )


def _candidate(
    source_id: str,
    *,
    kind: MemoryKind = MemoryKind.EVENT,
    branch: str = "root",
    time: int = 2,
    text: str = "A quiet school event.",
    owner: str | None = "public",
    visibility: str = "public",
    claim_id: str | None = None,
    source_event_id: str | None = None,
    fingerprint: str | None = None,
    salience: float = 0.5,
    entities: tuple[str, ...] = (),
) -> MemoryCandidate:
    return MemoryCandidate(
        source_id=source_id,
        kind=kind,
        playthrough_id="playthrough-1",
        branch_id=branch,
        world_time=time,
        text=text,
        owner_id=owner,
        visibility=visibility,
        branch_scope=branch,
        claim_id=claim_id,
        source_event_id=source_event_id,
        normalized_fingerprint=fingerprint,
        salience=salience,
        entity_ids=entities,
    )


@pytest.mark.asyncio
async def test_initial_context_hard_filters_owner_branch_and_future() -> None:
    candidates = [
        _candidate("public-root"),
        _candidate("alice-secret", owner="alice", visibility="private", text="Alice's secret letter."),
        _candidate("sibling-event", branch="sibling", text="A sibling future."),
        _candidate("future-event", time=21, text="Tomorrow's event."),
    ]
    traces = InMemoryRetrievalTraceStore()
    assembler = ContextAssembler(trace_store=traces)

    manifest = await assembler.build_initial_context(
        InitialContextRequest(
            run_id="run-1",
            role="planner",
            scope=_scope(),
            query_text="school event",
            token_budget=500,
        ),
        candidates,
    )

    ids = {entry.source_id for entry in manifest.entries}
    assert ids == {"public-root"}
    trace = (await traces.list())[0]
    assert trace.hard_filtered_count == 3
    assert "alice-secret" not in manifest.as_context()["entries"]


@pytest.mark.asyncio
async def test_coffee_memory_survives_noise_without_embeddings() -> None:
    coffee = _candidate(
        "coffee-preference",
        kind=MemoryKind.CLAIM,
        text="Yuki prefers tea over bitter coffee.",
        time=2,
        claim_id="coffee-preference",
        source_event_id="event-coffee-2",
        salience=0.95,
        entities=("yuki",),
    )
    noise = [
        _candidate(
            f"noise-{turn}",
            time=turn,
            text=f"Yuki attends a routine club activity at turn {turn}.",
            entities=("yuki",),
        )
        for turn in range(3, 21)
    ]
    assembler = ContextAssembler(trace_store=InMemoryRetrievalTraceStore())

    manifest = await assembler.build_initial_context(
        InitialContextRequest(
            run_id="run-coffee",
            role="simulator",
            scope=_scope(time=20, owner=None),
            query_text="Yuki receives very bitter coffee",
            entity_ids=("yuki",),
            token_budget=250,
            max_items=5,
        ),
        [coffee, *noise],
    )

    assert manifest.entries
    assert manifest.entries[0].source_id == "coffee-preference"
    assert "entity_match" in manifest.entries[0].match_reasons
    assert manifest.embedding_model is None


@pytest.mark.asyncio
async def test_targeted_retrieval_uses_exact_claim_before_semantic_fallback() -> None:
    exact = _candidate(
        "location-claim",
        kind=MemoryKind.CLAIM,
        branch="root",
        time=37,
        text="Yuki located at library.",
        claim_id="yuki_location_37",
        source_event_id="event-location-37",
        entities=("yuki", "library"),
    )
    unrelated = _candidate(
        "unrelated",
        kind=MemoryKind.CLAIM,
        branch="root",
        time=37,
        text="Yuki visited the gym.",
        claim_id="yuki_location_gym",
        source_event_id="event-gym-37",
        entities=("yuki", "gym"),
    )
    query = ValidationQuery(
        query_id="query-location",
        requirement_id="requirement-location",
        actor_id="yuki",
        query_type="authorization",
        question="Can Yuki use the library location?",
        branch_scope="root",
        world_time=40,
        target_claim_ids=("yuki_location_37",),
    )
    assembler = ContextAssembler(trace_store=InMemoryRetrievalTraceStore())

    manifest = await assembler.targeted_evidence(
        query,
        [exact, unrelated],
        scope=_scope(time=40, owner="yuki"),
        limit=5,
    )

    assert not manifest.insufficient_evidence
    assert [item.claim_id for item in manifest.evidence] == ["yuki_location_37"]
    assert manifest.evidence[0].source_event_id == "event-location-37"


@pytest.mark.asyncio
async def test_targeted_retrieval_reports_insufficient_evidence_after_scope_filter() -> None:
    sibling = _candidate(
        "sibling-location",
        kind=MemoryKind.CLAIM,
        branch="sibling",
        time=37,
        text="Yuki located at library.",
        claim_id="yuki_location_37",
        source_event_id="event-sibling-location",
    )
    query = ValidationQuery(
        query_id="query-missing",
        requirement_id="requirement-missing",
        actor_id="yuki",
        query_type="authorization",
        question="Can Yuki use the library location?",
        branch_scope="child",
        world_time=40,
        target_claim_ids=("yuki_location_37",),
    )

    manifest = await ContextAssembler().targeted_evidence(query, [sibling], scope=_scope(time=40, owner="yuki"))

    assert manifest.insufficient_evidence
    assert not manifest.evidence


@pytest.mark.asyncio
async def test_targeted_retrieval_uses_exact_fingerprint_before_semantic_fallback() -> None:
    exact = _candidate(
        "age-claim",
        kind=MemoryKind.CLAIM,
        branch="root",
        time=12,
        text="Yuki is eighteen years old.",
        claim_id="yuki-age",
        source_event_id="event-age-12",
        fingerprint="yuki|age_is|18",
    )
    query = ValidationQuery(
        query_id="query-age",
        requirement_id="requirement-age",
        actor_id="yuki",
        query_type="consistency",
        question="What is Yuki's age?",
        branch_scope="child",
        world_time=20,
    )

    manifest = await ContextAssembler().targeted_evidence(
        query,
        [exact],
        scope=_scope(time=20, owner="yuki"),
        fingerprint="yuki|age_is|18",
    )

    assert not manifest.insufficient_evidence
    assert manifest.evidence[0].claim_id == "yuki-age"
    assert "exact_claim_match" in manifest.evidence[0].match_reason


def test_claim_extractor_emits_typed_requirement_and_validation_query() -> None:
    claim = KnowledgeClaimProposal(
        proposal_id="location-proposal",
        source_role=AIPromptRole.SIMULATOR,
        source_run_id="sim-run",
        subject_id="yuki",
        predicate="located_at",
        object_id="library",
        branch_scope="root",
        provenance=AIProvenance(
            source_type="simulation",
            source_id="sim-run",
            run_id="sim-run",
            prompt_version="simulator@1.0.0",
        ),
    )
    simulation = SimulationResult(
        schema_version="simulation-result-1",
        role=AIPromptRole.SIMULATOR,
        run_id="sim-run",
        prompt_version="simulator@1.0.0",
        npc_reactions=(
            NPCReaction(
                character_id="yuki",
                immediate_reaction="checks the library",
                agency_goal="find a quiet place",
                resistance_or_agreement="agrees",
                confidence=0.8,
            ),
        ),
        proposed_outcome="Yuki reaches the library.",
        claim_proposals=(claim,),
    )

    result = ClaimExtractor().extract(simulation)

    assert result.proposed_claims == (claim,)
    assert len(result.knowledge_requirements) == 1
    assert result.validation_queries[0].target_claim_ids == ("location-proposal",)
    assert result.validation_queries[0].query_type == "authorization"


def test_cosine_similarity_is_exact_and_zero_safe() -> None:
    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    assert cosine_similarity((0.0, 0.0), (1.0, 0.0)) == 0.0


class _FakeEmbeddingProvider:
    provider_name = "ollama"
    model = "nomic-embed-text"
    capabilities = frozenset({ProviderCapability.EMBEDDING})

    async def embed(self, texts: tuple[str, ...], *, model: str | None = None) -> EmbeddingResponse:
        return EmbeddingResponse(
            provider="ollama",
            model=model or self.model,
            embeddings=tuple((float(len(text)), 1.0) for text in texts),
        )


@pytest.mark.asyncio
async def test_embedding_metadata_contains_content_hash_and_version() -> None:
    store = InMemoryEmbeddingStore()
    indexer = OllamaEmbeddingIndexer(store, enabled=True, embedding_version="ollama-v1")
    candidate = _candidate("memory-1", text="tea preference")

    records = await indexer.index(
        [candidate],
        provider=cast(ProviderPort, _FakeEmbeddingProvider()),
        model="nomic-embed-text",
    )

    assert len(records) == 1
    assert records[0].metadata.embedding_version == "ollama-v1"
    assert records[0].metadata.content_hash
    assert records[0].metadata.dimensions == 2
