"""Inward-facing ports for derived retrieval artifacts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from src.application.contracts.retrieval import EmbeddingRecord, MemoryCandidate, RetrievalScope, RetrievalTrace


class MemoryCandidateSource(Protocol):
    """Read canonical/perspective records for a bounded retrieval scope."""

    async def list_candidates(self, scope: RetrievalScope) -> tuple[MemoryCandidate, ...]: ...


class EmbeddingStore(Protocol):
    """Store/query derived vectors without becoming a source of truth."""

    async def save(self, record: EmbeddingRecord) -> None: ...

    async def get(
        self,
        *,
        source_id: str,
        content_hash: str,
        model: str,
        embedding_version: str,
    ) -> EmbeddingRecord | None: ...

    async def list_for_sources(
        self,
        source_ids: Iterable[str],
        *,
        model: str,
        embedding_version: str,
    ) -> tuple[EmbeddingRecord, ...]: ...


class RetrievalTraceStore(Protocol):
    """Persist safe retrieval metadata for debugging and evaluation."""

    async def save(self, trace: RetrievalTrace) -> None: ...


class RetrievalRepository(MemoryCandidateSource, EmbeddingStore, Protocol):
    """Combined persistence adapter exposed by the application UoW."""

    async def save_trace(self, trace: RetrievalTrace) -> None: ...


__all__ = ["EmbeddingStore", "MemoryCandidateSource", "RetrievalRepository", "RetrievalTraceStore"]
