"""Background rebuild of optional embedding indexes."""

from __future__ import annotations

from collections.abc import Sequence

from src.application.contracts.memory import EmbeddingRebuildReport
from src.application.contracts.retrieval import MemoryCandidate, RetrievalScope, content_hash
from src.application.ports.providers import ProviderPort
from src.application.ports.retrieval import EmbeddingStore, MemoryCandidateSource

from .embeddings import DEFAULT_EMBEDDING_VERSION, OllamaEmbeddingIndexer


class EmbeddingRebuildService:
    """Rebuild vectors from canonical candidates without opening a gameplay write path."""

    def __init__(self, store: EmbeddingStore, *, embedding_version: str = DEFAULT_EMBEDDING_VERSION) -> None:
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
        resolved_model = model or getattr(provider, "embedding_model", None) or getattr(provider, "model", None)
        existing_keys: set[tuple[str, str]] = set()
        if resolved_model:
            existing = await self.store.list_for_sources(
                (candidate.source_id for candidate in candidates),
                model=resolved_model,
                embedding_version=self.embedding_version,
            )
            existing_keys = {(record.metadata.source_id, record.metadata.content_hash) for record in existing}
        pending = tuple(
            candidate for candidate in candidates if (candidate.source_id, content_hash(candidate.text)) not in existing_keys
        )
        indexed = len(candidates) - len(pending)
        failed: list[str] = []
        for offset in range(0, len(pending), batch_size):
            batch: Sequence[MemoryCandidate] = pending[offset : offset + batch_size]
            try:
                records = await indexer.index(batch, provider=provider, model=resolved_model)
            except Exception:
                failed.extend(candidate.source_id for candidate in batch)
            else:
                indexed += len(records)
        return EmbeddingRebuildReport(
            playthrough_id=scope.playthrough_id,
            branch_id=scope.branch_id,
            candidate_count=len(candidates),
            indexed_count=indexed,
            model=resolved_model,
            embedding_version=self.embedding_version,
            failed_source_ids=tuple(failed),
        )


__all__ = ["EmbeddingRebuildService"]
