"""Initial context assembly and targeted consistency retrieval."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from src.application.contracts.ai import EvidenceReference, KnowledgeRequirement, TargetedEvidenceManifest, ValidationQuery
from src.application.contracts.providers import ProviderError
from src.application.contracts.retrieval import (
    ContextEntry,
    InitialContextManifest,
    InitialContextRequest,
    MemoryCandidate,
    RetrievalHit,
    RetrievalPhase,
    RetrievalQuery,
    RetrievalScope,
    RetrievalTrace,
    RetrievalTraceHit,
    content_hash,
)
from src.application.ports.providers import ProviderPort
from src.application.ports.retrieval import EmbeddingStore, MemoryCandidateSource, RetrievalTraceStore

from .budget import TokenBudgetAllocator, estimate_tokens
from .embeddings import InMemoryEmbeddingStore, OllamaEmbeddingIndexer, cosine_similarity
from .scope import HardScopeFilter
from .scoring import RetrievalScorer
from .tracing import InMemoryRetrievalTraceStore


class ContextAssembler:
    """Build context only after hard scope filtering has completed."""

    def __init__(
        self,
        *,
        scope_filter: HardScopeFilter | None = None,
        scorer: RetrievalScorer | None = None,
        budget_allocator: TokenBudgetAllocator | None = None,
        embedding_indexer: OllamaEmbeddingIndexer | None = None,
        embedding_store: EmbeddingStore | None = None,
        trace_store: RetrievalTraceStore | None = None,
    ) -> None:
        self.scope_filter = scope_filter or HardScopeFilter()
        self.scorer = scorer or RetrievalScorer()
        self.budget_allocator = budget_allocator or TokenBudgetAllocator()
        self.embedding_store = embedding_store or (
            embedding_indexer.store if embedding_indexer is not None else InMemoryEmbeddingStore()
        )
        self.embedding_indexer = embedding_indexer
        self.trace_store = trace_store or InMemoryRetrievalTraceStore()

    async def build_initial_context(
        self,
        request: InitialContextRequest,
        candidates: tuple[MemoryCandidate, ...] | list[MemoryCandidate],
        *,
        provider: ProviderPort | None = None,
        embedding_model: str | None = None,
    ) -> InitialContextManifest:
        effective_embedding_model = embedding_model or (provider.model if provider is not None else None)
        query = RetrievalQuery(
            phase=RetrievalPhase.INITIAL,
            query_text=request.query_text,
            entity_ids=request.entity_ids,
            goal_ids=request.goal_ids,
            thread_ids=request.thread_ids,
            limit=request.max_items,
            scope=request.scope,
        )
        eligible, rejected = self._eligible(candidates, request.scope, request.include_kinds)
        hits = self._rank(eligible, query, recent_event_limit=request.recent_event_limit)
        hits, embedding_enabled, embedding_version = await self._maybe_embedding_rerank(
            hits,
            query_text=request.query_text,
            provider=provider,
            model=effective_embedding_model,
        )
        selected, dropped, used = self.budget_allocator.select(
            hits,
            role=request.role,
            token_budget=request.token_budget,
            max_items=request.max_items,
        )
        entries = tuple(ContextEntry.from_hit(hit, token_estimate=estimate_tokens(hit.candidate.text)) for hit in selected)
        trace = self._trace(
            query=query,
            scope=request.scope,
            candidate_count=len(candidates),
            rejected_count=rejected,
            hits=hits,
            selected_ids={hit.source_id for hit in selected},
            dropped_ids={source_id: "token_budget" for source_id, _ in dropped},
            token_budget=request.token_budget,
            estimated_tokens=used,
            embedding_enabled=embedding_enabled,
            embedding_model=effective_embedding_model if embedding_enabled else None,
            embedding_version=embedding_version,
        )
        await self.trace_store.save(trace)
        return InitialContextManifest.new(
            run_id=request.run_id,
            role=request.role,
            scope=request.scope,
            entries=entries,
            token_budget=request.token_budget,
            estimated_tokens=used,
            retrieval_trace_ids=(trace.trace_id,),
            embedding_model=embedding_model if embedding_enabled else None,
            embedding_version=embedding_version,
        )

    async def build_initial_context_from_source(
        self,
        request: InitialContextRequest,
        source: MemoryCandidateSource,
        *,
        provider: ProviderPort | None = None,
        embedding_model: str | None = None,
    ) -> InitialContextManifest:
        """Load bounded canonical candidates, then use the same safe assembler."""
        candidates = await source.list_candidates(request.scope)
        return await self.build_initial_context(
            request,
            candidates,
            provider=provider,
            embedding_model=embedding_model,
        )

    async def targeted_evidence(
        self,
        query: ValidationQuery,
        candidates: tuple[MemoryCandidate, ...] | list[MemoryCandidate],
        *,
        scope: RetrievalScope,
        requirement: KnowledgeRequirement | None = None,
        run_id: str | None = None,
        provider: ProviderPort | None = None,
        embedding_model: str | None = None,
        fingerprint: str | None = None,
        limit: int = 20,
    ) -> TargetedEvidenceManifest:
        if limit <= 0:
            raise ValueError("Targeted evidence limit must be positive.")
        effective_embedding_model = embedding_model or (provider.model if provider is not None else None)
        retrieval_query = RetrievalQuery(
            query_id=query.query_id,
            phase=RetrievalPhase.TARGETED,
            query_text=query.question,
            target_claim_ids=query.target_claim_ids,
            fingerprint=fingerprint,
            subject_id=requirement.subject_id if requirement else None,
            predicate=requirement.predicate if requirement else None,
            object_id=requirement.object_id if requirement else None,
            typed_value=requirement.typed_value if requirement else None,
            limit=limit,
            scope=scope,
        )
        eligible, rejected = self._eligible(candidates, scope, ())
        hits = self._rank_targeted(eligible, retrieval_query)
        exact_hits = tuple(hit for hit in hits if hit.score.exact_match)
        # Exact claim/fingerprint lookup is authoritative for targeted
        # validation.  Semantic fallback is used only when no exact candidate
        # survived the hard scope boundary.
        embedding_enabled = False
        embedding_version: str | None = None
        if exact_hits:
            selected_hits = exact_hits
        else:
            hits, embedding_enabled, embedding_version = await self._maybe_embedding_rerank(
                hits,
                query_text=query.question,
                provider=provider,
                model=effective_embedding_model,
            )
            selected_hits = hits
        selected_hits = selected_hits[:limit]
        selected_ids = {hit.source_id for hit in selected_hits}
        trace = self._trace(
            query=retrieval_query,
            scope=scope,
            candidate_count=len(candidates),
            rejected_count=rejected,
            hits=hits,
            selected_ids=selected_ids,
            dropped_ids={hit.source_id: "targeted_limit" for hit in hits if hit.source_id not in selected_ids},
            token_budget=0,
            estimated_tokens=0,
            embedding_enabled=embedding_enabled,
            embedding_model=effective_embedding_model if embedding_enabled else None,
            embedding_version=embedding_version,
        )
        await self.trace_store.save(trace)

        evidence: list[EvidenceReference] = []
        for hit in selected_hits:
            candidate = hit.candidate
            source_event_id = candidate.effective_source_event_id
            if source_event_id is None or candidate.claim_id is None:
                continue
            evidence.append(
                EvidenceReference(
                    evidence_id=candidate.source_id,
                    claim_id=candidate.claim_id,
                    source_event_id=source_event_id,
                    owner_id=candidate.owner_id or "public",
                    branch_scope=candidate.branch_scope,
                    world_time=candidate.world_time,
                    score=hit.score.total,
                    match_reason=";".join(hit.match_reasons) or "semantic_match",
                )
            )
        return TargetedEvidenceManifest(
            query_id=query.query_id,
            branch_scope=query.branch_scope,
            world_time=query.world_time,
            evidence=tuple(evidence),
            insufficient_evidence=not evidence,
            retrieval_trace_id=trace.trace_id,
        )

    async def targeted_evidence_from_source(
        self,
        query: ValidationQuery,
        source: MemoryCandidateSource,
        *,
        scope: RetrievalScope,
        requirement: KnowledgeRequirement | None = None,
        run_id: str | None = None,
        limit: int = 20,
        fingerprint: str | None = None,
        provider: ProviderPort | None = None,
        embedding_model: str | None = None,
    ) -> TargetedEvidenceManifest:
        candidates = await source.list_candidates(scope)
        return await self.targeted_evidence(
            query,
            candidates,
            scope=scope,
            requirement=requirement,
            run_id=run_id,
            provider=provider,
            embedding_model=embedding_model,
            fingerprint=fingerprint,
            limit=limit,
        )

    def rank(
        self,
        query: RetrievalQuery,
        candidates: tuple[MemoryCandidate, ...] | list[MemoryCandidate],
        *,
        include_kinds: tuple[object, ...] = (),
    ) -> tuple[RetrievalHit, ...]:
        if query.scope is None:
            raise ValueError("RetrievalQuery ranking requires a RetrievalScope.")
        eligible, _ = self._eligible(candidates, query.scope, include_kinds)
        return self._rank_targeted(eligible, query) if query.phase == RetrievalPhase.TARGETED else self._rank(eligible, query)

    def _eligible(
        self,
        candidates: tuple[MemoryCandidate, ...] | list[MemoryCandidate],
        scope: RetrievalScope,
        include_kinds: tuple[object, ...],
    ) -> tuple[tuple[MemoryCandidate, ...], int]:
        allowed: list[MemoryCandidate] = []
        seen_source_ids: set[str] = set()
        for candidate in candidates:
            if (include_kinds and candidate.kind not in include_kinds) or not self.scope_filter.allows(candidate, scope):
                continue
            if candidate.source_id in seen_source_ids:
                continue
            seen_source_ids.add(candidate.source_id)
            allowed.append(candidate)
        return tuple(allowed), len(candidates) - len(allowed)

    def _rank(
        self,
        candidates: tuple[MemoryCandidate, ...],
        query: RetrievalQuery,
        *,
        recent_event_limit: int = 0,
    ) -> tuple[RetrievalHit, ...]:
        recent_ids = {
            candidate.source_id
            for candidate in sorted(
                (item for item in candidates if str(item.kind) == "event"),
                key=lambda item: (item.world_time, item.source_id),
                reverse=True,
            )[:recent_event_limit]
        }
        hits: list[RetrievalHit] = []
        for candidate in candidates:
            reasons = list(self.scorer.reasons(candidate, query))
            if candidate.source_id in recent_ids and "recent_event" not in reasons:
                reasons.append("recent_event")
            hits.append(
                RetrievalHit(
                    candidate=candidate,
                    score=self.scorer.score(candidate, query),
                    match_reasons=tuple(reasons),
                )
            )
        hits.sort(key=lambda hit: (hit.score.total, hit.candidate.world_time, hit.source_id), reverse=True)
        return tuple(hits[: query.limit])

    def _rank_targeted(self, candidates: tuple[MemoryCandidate, ...], query: RetrievalQuery) -> tuple[RetrievalHit, ...]:
        hits = [
            RetrievalHit(
                candidate=candidate,
                score=self.scorer.score(candidate, query),
                match_reasons=self.scorer.reasons(candidate, query),
            )
            for candidate in candidates
        ]
        hits.sort(key=lambda hit: (hit.score.exact_match, hit.score.total, hit.candidate.world_time, hit.source_id), reverse=True)
        return tuple(hits[: query.limit])

    async def _maybe_embedding_rerank(
        self,
        hits: tuple[RetrievalHit, ...],
        *,
        query_text: str,
        provider: ProviderPort | None,
        model: str | None,
    ) -> tuple[tuple[RetrievalHit, ...], bool, str | None]:
        indexer = self.embedding_indexer
        if indexer is None or not indexer.enabled or provider is None or not query_text.strip() or not hits:
            return hits, False, None
        try:
            await indexer.index(tuple(hit.candidate for hit in hits), provider=provider, model=model)
            query_vector = await indexer.ensure_query_embedding(query_text, provider=provider, model=model)
        except ProviderError, ValueError, TypeError:
            # Embeddings are derived and optional; lexical/entity retrieval is
            # the required fallback when Ollama is unavailable or malformed.
            return hits, False, None
        if query_vector is None:
            return hits, False, None
        reranked: list[RetrievalHit] = []
        for hit in hits:
            record = await self.embedding_store.get(
                source_id=hit.candidate.source_id,
                content_hash=content_hash(hit.candidate.text),
                model=model or getattr(provider, "model", ""),
                embedding_version=indexer.embedding_version,
            )
            if record is None:
                reranked.append(hit)
                continue
            semantic = max(0.0, min(1.0, (cosine_similarity(query_vector, record.vector) + 1.0) / 2.0))
            blended = max(hit.score.total, 0.7 * hit.score.total + 0.3 * semantic)
            reranked.append(
                replace(
                    hit,
                    score=replace(hit.score, total=blended),
                    embedding_score=semantic,
                    match_reasons=(*hit.match_reasons, "embedding_rerank"),
                )
            )
        reranked.sort(key=lambda hit: (hit.score.total, hit.candidate.world_time, hit.source_id), reverse=True)
        return tuple(reranked), True, indexer.embedding_version

    @staticmethod
    def _trace(
        *,
        query: RetrievalQuery,
        scope: RetrievalScope,
        candidate_count: int,
        rejected_count: int,
        hits: tuple[RetrievalHit, ...],
        selected_ids: set[str],
        dropped_ids: dict[str, str],
        token_budget: int,
        estimated_tokens: int,
        embedding_enabled: bool,
        embedding_model: str | None,
        embedding_version: str | None,
    ) -> RetrievalTrace:
        return RetrievalTrace(
            trace_id=str(uuid4()),
            query_id=query.query_id,
            phase=query.phase,
            scope=scope,
            candidate_count=candidate_count,
            hard_filtered_count=rejected_count,
            hits=tuple(
                RetrievalTraceHit(
                    source_id=hit.source_id,
                    score=hit.score,
                    selected=hit.source_id in selected_ids,
                    dropped_reason=dropped_ids.get(hit.source_id),
                    embedding_score=hit.embedding_score,
                )
                for hit in hits
            ),
            token_budget=token_budget,
            estimated_tokens=estimated_tokens,
            embedding_enabled=embedding_enabled,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )


class TargetedConsistencyRetriever:
    """Named facade for the targeted phase used by the future graph."""

    def __init__(self, assembler: ContextAssembler | None = None) -> None:
        self.assembler = assembler or ContextAssembler()

    async def retrieve(
        self,
        query: ValidationQuery,
        candidates: tuple[MemoryCandidate, ...] | list[MemoryCandidate],
        *,
        scope: RetrievalScope,
        requirement: KnowledgeRequirement | None = None,
        run_id: str | None = None,
        limit: int = 20,
        fingerprint: str | None = None,
        provider: ProviderPort | None = None,
        embedding_model: str | None = None,
    ) -> TargetedEvidenceManifest:
        return await self.assembler.targeted_evidence(
            query,
            candidates,
            scope=scope,
            requirement=requirement,
            run_id=run_id,
            provider=provider,
            embedding_model=embedding_model,
            fingerprint=fingerprint,
            limit=limit,
        )


__all__ = ["ContextAssembler", "TargetedConsistencyRetriever"]
