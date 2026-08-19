"""In-memory sink for safe retrieval traces."""

from __future__ import annotations

from src.application.contracts.retrieval import RetrievalTrace


class InMemoryRetrievalTraceStore:
    """Test/local sink; a SQL adapter may implement the same inward port."""

    def __init__(self) -> None:
        self._traces: dict[str, RetrievalTrace] = {}

    async def save(self, trace: RetrievalTrace) -> None:
        self._traces[trace.trace_id] = trace

    async def get(self, trace_id: str) -> RetrievalTrace | None:
        return self._traces.get(trace_id)

    async def list(self) -> tuple[RetrievalTrace, ...]:
        return tuple(self._traces.values())


__all__ = ["InMemoryRetrievalTraceStore"]
