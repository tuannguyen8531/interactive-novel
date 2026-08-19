"""Background rebuild of optional embedding indexes."""

from __future__ import annotations

from collections.abc import Sequence

from src.application.contracts.memory import EmbeddingRebuildReport
from src.application.contracts.retrieval import MemoryCandidate, RetrievalScope
from src.application.ports.providers import ProviderPort
from src.application.ports.retrieval import EmbeddingStore, MemoryCandidateSource

from .embeddings import OllamaEmbeddingIndexer


class EmbeddingRebuildService:
    """Rebuild vectors from canonical candidates without opening a gameplay write path."""

    def __init__(self, store: EmbeddingStore, *, embedding_version: str = "phase-13-embedding-1") -> None:
        self.store = store
        self.embedding_version = embedding_version

    async def rebuild(
        self,
        scope: RetrievalScope,
        source: MemoryCandidateSource,
        *,
        provider: ProviderPort,
        model: str | None = None,
        batch_size: int = 64,
    ) -> EmbeddingRebuildReport:
        if batch_size <= 0:
            raise ValueError("Embedding rebuild batch size must be positive.")
        candidates = await source.list_candidates(scope)
        indexer = OllamaEmbeddingIndexer(self.store, embedding_version=self.embedding_version, enabled=True)
        indexed = 0
        failed: list[str] = []
        for offset in range(0, len(candidates), batch_size):
            batch: Sequence[MemoryCandidate] = candidates[offset : offset + batch_size]
            try:
                records = await indexer.index(batch, provider=provider, model=model)
            except Exception:
                failed.extend(candidate.source_id for candidate in batch)
            else:
                indexed += len(records)
        return EmbeddingRebuildReport(
            playthrough_id=scope.playthrough_id,
            branch_id=scope.branch_id,
            candidate_count=len(candidates),
            indexed_count=indexed,
            model=model or getattr(provider, "model", None),
            embedding_version=self.embedding_version,
            failed_source_ids=tuple(failed),
        )


__all__ = ["EmbeddingRebuildService"]
