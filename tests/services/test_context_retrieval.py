from __future__ import annotations

from typing import cast

import pytest

from src.application.contracts.ai import (
    AIPromptRole,
    AIProvenance,
    KnowledgeClaimProposal,
    NPCReaction,
    SetCharacterLocationOperation,
    SimulationResult,
    StatePatchProposal,
    ValidationQuery,
)
from src.application.contracts.providers import EmbeddingResponse, ProviderCapability, ProviderError
from src.application.contracts.retrieval import (
    EmbeddingMetadata,
    EmbeddingRecord,
    InitialContextRequest,
    MemoryCandidate,
    MemoryKind,
    RetrievalScope,
    content_hash,
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
    branch_scope: str | None = None,
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
        branch_scope=branch if branch_scope is None else branch_scope,
        claim_id=claim_id,
        source_event_id=source_event_id,
        normalized_fingerprint=fingerprint,
        salience=salience,
        entity_ids=entities,
    )


@pytest.mark.asyncio
async def test_owner_scoped_private_memory_is_visible_only_to_its_owner() -> None:
    private = _candidate(
        "alice-private-claim",
        kind=MemoryKind.CLAIM,
        owner="alice",
        visibility="private",
        branch_scope="alice",
        text="Alice has drafted a private letter.",
    )
    assembler = ContextAssembler(trace_store=InMemoryRetrievalTraceStore())

    alice_manifest = await assembler.build_initial_context(
        InitialContextRequest(
            run_id="run-alice-private",
            role="planner",
            scope=_scope(owner="alice"),
            query_text="private letter",
            token_budget=500,
        ),
        [private],
    )
    bob_manifest = await assembler.build_initial_context(
        InitialContextRequest(
            run_id="run-bob-private",
            role="planner",
            scope=_scope(owner="bob"),
            query_text="private letter",
            token_budget=500,
        ),
        [private],
    )

    assert [entry.source_id for entry in alice_manifest.entries] == ["alice-private-claim"]
    assert bob_manifest.entries == ()


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
async def test_100_turn_critical_memory_recall_at_five_gate() -> None:
    critical = (
        _candidate(
            "critical-key-13",
            kind=MemoryKind.CLAIM,
            time=13,
            text="Alice hid the brass key under the library atlas.",
            salience=0.99,
            entities=("alice", "library"),
        ),
        _candidate(
            "critical-promise-55",
            kind=MemoryKind.CLAIM,
            time=55,
            text="Bob promised Mina they would meet beside the old clock.",
            salience=0.98,
            entities=("bob", "mina"),
        ),
        _candidate(
            "critical-letter-92",
            kind=MemoryKind.CLAIM,
            time=92,
            text="The sealed letter bears a silver fox crest.",
            salience=0.97,
            entities=("mina", "letter"),
        ),
    )
    noise = [
        _candidate(
            f"noise-{turn}",
            time=turn,
            text=f"A routine club task was completed at turn {turn}.",
            entities=("club",),
        )
        for turn in range(1, 101)
    ]
    queries = (
        ("Where did Alice hide the brass key?", ("alice", "library"), "critical-key-13"),
        ("Where did Bob promise to meet Mina?", ("bob", "mina"), "critical-promise-55"),
        ("What crest is on Mina's sealed letter?", ("mina", "letter"), "critical-letter-92"),
    )
    assembler = ContextAssembler(trace_store=InMemoryRetrievalTraceStore())

    recalled = 0
    for index, (query_text, entity_ids, expected_id) in enumerate(queries, start=1):
        manifest = await assembler.build_initial_context(
            InitialContextRequest(
                run_id=f"run-recall-{index}",
                role="simulator",
                scope=_scope(time=100, owner=None),
                query_text=query_text,
                entity_ids=entity_ids,
                token_budget=500,
                max_items=5,
            ),
            [*critical, *noise],
        )
        recalled += expected_id in {entry.source_id for entry in manifest.entries}

    assert recalled / len(queries) == 1.0


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
        schema_version="simulation-result",
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


def test_claim_extractor_skips_new_claim_checks_and_idempotent_locations_for_live_turn() -> None:
    claim = KnowledgeClaimProposal(
        proposal_id="new-goal-proposal",
        source_role=AIPromptRole.SIMULATOR,
        source_run_id="sim-run",
        subject_id="yuki",
        predicate="goal_active",
        object_id="festival-planning",
        branch_scope="root",
        provenance=AIProvenance(
            source_type="simulation",
            source_id="sim-run",
            run_id="sim-run",
            prompt_version="simulator@1.0.0",
        ),
    )
    simulation = SimulationResult(
        schema_version="simulation-result",
        role=AIPromptRole.SIMULATOR,
        run_id="sim-run",
        prompt_version="simulator@1.0.0",
        npc_reactions=(
            NPCReaction(
                character_id="yuki",
                immediate_reaction="offers a task",
                agency_goal="prepare for the festival",
                resistance_or_agreement="agrees",
                confidence=0.8,
            ),
        ),
        proposed_outcome="Yuki offers a festival task.",
        claim_proposals=(claim,),
        state_patch=StatePatchProposal(
            patch_id="patch-idempotent-location",
            branch_id="root",
            base_world_time=0,
            operations=(SetCharacterLocationOperation(character_id="yuki", location_id="library"),),
            provenance=claim.provenance,
        ),
    )

    result = ClaimExtractor().extract(
        simulation,
        include_implicit_claim_requirements=False,
        current_locations={"yuki": "library"},
    )

    assert result.proposed_claims == (claim,)
    assert simulation.state_patch is not None
    assert result.proposed_mutations == simulation.state_patch.operations
    assert result.knowledge_requirements == ()
    assert result.validation_queries == ()


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


class _QueryOnlyEmbeddingProvider:
    provider_name = "ollama"
    model = "nomic-embed-text"
    capabilities = frozenset({ProviderCapability.EMBEDDING})

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def embed(self, texts: tuple[str, ...], *, model: str | None = None) -> EmbeddingResponse:
        self.calls.append(tuple(texts))
        return EmbeddingResponse(
            provider=self.provider_name,
            model=model or self.model,
            embeddings=tuple((1.0, 0.0) for _ in texts),
        )


class _UnavailableEmbeddingProvider(_QueryOnlyEmbeddingProvider):
    async def embed(self, texts: tuple[str, ...], *, model: str | None = None) -> EmbeddingResponse:
        del texts, model
        raise ProviderError("embedding unavailable", provider=self.provider_name)


@pytest.mark.asyncio
async def test_hybrid_search_recovers_semantic_memory_without_reembedding_candidates() -> None:
    semantic = _candidate(
        "semantic-memory",
        time=20,
        text="A silver locket rests beneath the loose floorboard.",
    )
    lexical_decoy = _candidate(
        "lexical-decoy",
        time=20,
        text="The club reviews its lost keepsake policy.",
    )
    store = InMemoryEmbeddingStore()
    for candidate, vector in ((semantic, (1.0, 0.0)), (lexical_decoy, (0.0, 1.0))):
        await store.save(
            EmbeddingRecord(
                metadata=EmbeddingMetadata(
                    source_id=candidate.source_id,
                    source_kind=candidate.kind,
                    playthrough_id=candidate.playthrough_id,
                    branch_id=candidate.branch_id,
                    model="nomic-embed-text",
                    dimensions=2,
                    embedding_version="hybrid-v1",
                    content_hash=content_hash(candidate.text),
                ),
                vector=vector,
            )
        )
    provider = _QueryOnlyEmbeddingProvider()
    traces = InMemoryRetrievalTraceStore()
    assembler = ContextAssembler(
        embedding_store=store,
        embedding_indexer=OllamaEmbeddingIndexer(store, enabled=True, embedding_version="hybrid-v1"),
        trace_store=traces,
    )

    manifest = await assembler.build_initial_context(
        InitialContextRequest(
            run_id="run-hybrid",
            role="planner",
            scope=_scope(time=20, owner=None),
            query_text="lost keepsake",
            token_budget=100,
            max_items=1,
        ),
        [lexical_decoy, semantic],
        provider=cast(ProviderPort, provider),
    )

    assert manifest.entries[0].source_id == "semantic-memory"
    assert "semantic_match" in manifest.entries[0].match_reasons
    assert manifest.embedding_model == "nomic-embed-text"
    assert provider.calls == [("lost keepsake",)]
    trace = (await traces.list())[0]
    assert trace.embedding_enabled is True
    assert {hit.source_id: hit.embedding_score for hit in trace.hits} == {
        "semantic-memory": pytest.approx(1.0),
        "lexical-decoy": pytest.approx(0.0),
    }


@pytest.mark.asyncio
async def test_hybrid_search_falls_back_to_deterministic_ranking_when_provider_is_unavailable() -> None:
    lexical = _candidate("lexical", text="Mina searches for a lost keepsake.", time=20)
    store = InMemoryEmbeddingStore()
    await store.save(
        EmbeddingRecord(
            metadata=EmbeddingMetadata(
                source_id=lexical.source_id,
                source_kind=lexical.kind,
                playthrough_id=lexical.playthrough_id,
                branch_id=lexical.branch_id,
                model="nomic-embed-text",
                dimensions=2,
                embedding_version="hybrid-v1",
                content_hash=content_hash(lexical.text),
            ),
            vector=(1.0, 0.0),
        )
    )
    traces = InMemoryRetrievalTraceStore()
    assembler = ContextAssembler(
        embedding_store=store,
        embedding_indexer=OllamaEmbeddingIndexer(store, enabled=True, embedding_version="hybrid-v1"),
        trace_store=traces,
    )

    manifest = await assembler.build_initial_context(
        InitialContextRequest(
            run_id="run-fallback",
            role="planner",
            scope=_scope(time=20, owner=None),
            query_text="lost keepsake",
            token_budget=100,
            max_items=1,
        ),
        [lexical],
        provider=cast(ProviderPort, _UnavailableEmbeddingProvider()),
    )

    assert manifest.entries[0].source_id == "lexical"
    assert manifest.embedding_model is None
    assert (await traces.list())[0].embedding_enabled is False


@pytest.mark.asyncio
async def test_hybrid_search_does_not_reuse_embedding_after_candidate_text_changes() -> None:
    candidate = _candidate("changed-memory", text="The corrected memory text.", time=20)
    store = InMemoryEmbeddingStore()
    await store.save(
        EmbeddingRecord(
            metadata=EmbeddingMetadata(
                source_id=candidate.source_id,
                source_kind=candidate.kind,
                playthrough_id=candidate.playthrough_id,
                branch_id=candidate.branch_id,
                model="nomic-embed-text",
                dimensions=2,
                embedding_version="hybrid-v1",
                content_hash=content_hash("The old memory text."),
            ),
            vector=(1.0, 0.0),
        )
    )
    traces = InMemoryRetrievalTraceStore()
    assembler = ContextAssembler(
        embedding_store=store,
        embedding_indexer=OllamaEmbeddingIndexer(store, enabled=True, embedding_version="hybrid-v1"),
        trace_store=traces,
    )

    manifest = await assembler.build_initial_context(
        InitialContextRequest(
            run_id="run-stale",
            role="planner",
            scope=_scope(time=20, owner=None),
            query_text="corrected memory",
            token_budget=100,
            max_items=1,
        ),
        [candidate],
        provider=cast(ProviderPort, _QueryOnlyEmbeddingProvider()),
    )

    assert manifest.entries[0].source_id == candidate.source_id
    assert manifest.embedding_model is None
    assert (await traces.list())[0].embedding_enabled is False


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
