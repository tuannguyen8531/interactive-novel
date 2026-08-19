"""Optional local embeddings and exact cosine re-ranking."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import sqrt

from src.application.contracts.providers import EmbeddingResponse
from src.application.contracts.retrieval import (
    EmbeddingMetadata,
    EmbeddingRecord,
    MemoryCandidate,
    content_hash,
)
from src.application.ports.providers import ProviderPort
from src.application.ports.retrieval import EmbeddingStore


class InMemoryEmbeddingStore:
    """Small derived store used by tests and the local MVP runner.

    A later derived-data adapter can replace this store without changing the
    retrieval contract.  Content hash, model and embedding version are part of
    the key so stale vectors are never silently reused.
    """

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], EmbeddingRecord] = {}

    async def save(self, record: EmbeddingRecord) -> None:
        metadata = record.metadata
        key = (metadata.source_id, metadata.content_hash, metadata.model, metadata.embedding_version)
        self._records[key] = record

    async def get(
        self,
        *,
        source_id: str,
        content_hash: str,
        model: str,
        embedding_version: str,
    ) -> EmbeddingRecord | None:
        return self._records.get((source_id, content_hash, model, embedding_version))

    async def list_for_sources(self, source_ids: Iterable[str]) -> tuple[EmbeddingRecord, ...]:
        wanted = set(source_ids)
        return tuple(record for record in self._records.values() if record.metadata.source_id in wanted)


def _validate_embedding_response(response: EmbeddingResponse, expected_count: int) -> int:
    if len(response.embeddings) != expected_count:
        raise ValueError("Embedding provider returned a different number of vectors than requested.")
    dimensions = {len(vector) for vector in response.embeddings}
    if len(dimensions) != 1 or not dimensions or next(iter(dimensions)) == 0:
        raise ValueError("Embedding provider returned vectors with inconsistent dimensions.")
    return next(iter(dimensions))


class OllamaEmbeddingIndexer:
    """Create derived vectors through the provider embedding port.

    The provider is normally an Ollama adapter in local-first mode, but the
    port accepts a scripted fake for tests and a future routed embedding
    adapter.  No provider call is made when ``enabled`` is false.
    """

    def __init__(
        self,
        store: EmbeddingStore,
        *,
        embedding_version: str = "embedding-1",
        enabled: bool = False,
    ) -> None:
        if not embedding_version.strip():
            raise ValueError("Embedding version cannot be blank.")
        self.store = store
        self.embedding_version = embedding_version
        self.enabled = enabled

    async def index(
        self,
        candidates: Sequence[MemoryCandidate],
        *,
        provider: ProviderPort | None = None,
        model: str | None = None,
    ) -> tuple[EmbeddingRecord, ...]:
        if not self.enabled or provider is None or not candidates:
            return ()
        texts = tuple(candidate.text for candidate in candidates)
        response = await provider.embed(texts, model=model)
        dimensions = _validate_embedding_response(response, len(candidates))
        records: list[EmbeddingRecord] = []
        for candidate, vector in zip(candidates, response.embeddings, strict=True):
            metadata = EmbeddingMetadata(
                source_id=candidate.source_id,
                source_kind=candidate.kind,
                playthrough_id=candidate.playthrough_id,
                branch_id=candidate.branch_id,
                model=response.model,
                dimensions=dimensions,
                embedding_version=self.embedding_version,
                content_hash=content_hash(candidate.text),
            )
            record = EmbeddingRecord(metadata=metadata, vector=tuple(vector))
            await self.store.save(record)
            records.append(record)
        return tuple(records)

    async def ensure_query_embedding(
        self,
        query_text: str,
        *,
        provider: ProviderPort | None,
        model: str | None = None,
    ) -> tuple[float, ...] | None:
        if not self.enabled or provider is None or not query_text.strip():
            return None
        response = await provider.embed((query_text,), model=model)
        _validate_embedding_response(response, 1)
        return tuple(response.embeddings[0])


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Calculate exact cosine similarity, using NumPy when installed.

    NumPy remains optional so local retrieval still works on a minimal install;
    the small pure-Python fallback preserves the same semantics for tests and
    for embeddings-disabled deployments.
    """
    if len(left) != len(right) or not left:
        return 0.0
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    left_norm = float(np.linalg.norm(left_array))
    right_norm = float(np.linalg.norm(right_array))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(np.dot(left_array, right_array) / (left_norm * right_norm))


__all__ = ["InMemoryEmbeddingStore", "OllamaEmbeddingIndexer", "cosine_similarity"]
