"""Application-facing LangGraph runner adapter."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from src.application.contracts.persistence import CanonicalTurnBundle
from src.application.contracts.providers import CancellationToken, ExecutionMode
from src.application.contracts.retrieval import EmbeddingRecord, RetrievalScope, RetrievalTrace
from src.application.contracts.turns import TurnRunRequest
from src.application.ports.persistence import UowFactory
from src.application.ports.providers import ProviderPort
from src.application.ports.telemetry import TelemetryRecorderPort

from .checkpoint import build_in_memory_checkpointer, sqlite_checkpointer
from .pipeline import TurnPipeline, TurnPipelineDependencies, TurnPipelineRequest


class UowTurnCommitter:
    """Commit canonical graph bundles in one short-lived application UoW."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def commit_turn(self, bundle: CanonicalTurnBundle) -> Any:
        async with self._uow_factory() as uow:
            record = await uow.canonical.commit_turn(bundle)
            await uow.commit()
            return record


class UowCandidateSource:
    """Open a read transaction per retrieval call instead of leaking a session."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def list_candidates(self, scope: RetrievalScope):
        async with self._uow_factory() as uow:
            return await uow.retrieval.list_candidates(scope)


class UowEmbeddingStore:
    """Read durable vectors with short-lived sessions; writes remain derived."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def save(self, record: EmbeddingRecord) -> None:
        async with self._uow_factory() as uow:
            await uow.retrieval.save(record)
            await uow.commit()

    async def get(
        self,
        *,
        source_id: str,
        content_hash: str,
        model: str,
        embedding_version: str,
    ) -> EmbeddingRecord | None:
        async with self._uow_factory() as uow:
            return await uow.retrieval.get(
                source_id=source_id,
                content_hash=content_hash,
                model=model,
                embedding_version=embedding_version,
            )

    async def list_for_sources(
        self,
        source_ids: Iterable[str],
        *,
        model: str,
        embedding_version: str,
    ) -> tuple[EmbeddingRecord, ...]:
        async with self._uow_factory() as uow:
            return await uow.retrieval.list_for_sources(
                source_ids,
                model=model,
                embedding_version=embedding_version,
            )


class UowRetrievalTraceStore:
    """Persist retrieval diagnostics without extending the graph transaction."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def save(self, trace: RetrievalTrace) -> None:
        async with self._uow_factory() as uow:
            await uow.retrieval.save_trace(trace)
            await uow.commit()


class GraphTurnRunner:
    """Run one application request through the bounded graph boundary."""

    def __init__(
        self,
        *,
        uow_factory: UowFactory,
        provider: ProviderPort,
        event_sink: Any | None = None,
        execution_mode: ExecutionMode = ExecutionMode.QUALITY,
        checkpoint_path: Path | None = None,
        max_repair_attempts: int = 1,
        max_revision_attempts: int = 1,
        max_contract_retries: int = 1,
        telemetry: TelemetryRecorderPort | None = None,
        input_max_chars: int = 20_000,
    ) -> None:
        self._uow_factory = uow_factory
        self._provider = provider
        self._event_sink = event_sink
        self._execution_mode = execution_mode
        self._checkpoint_path = checkpoint_path
        self._max_repair_attempts = max_repair_attempts
        self._max_revision_attempts = max_revision_attempts
        self._max_contract_retries = max_contract_retries
        self._telemetry = telemetry
        self._input_max_chars = input_max_chars
        self._tokens: dict[str, CancellationToken] = {}
        self._cancel_before_start: set[str] = set()

    async def run(self, request: TurnRunRequest) -> Mapping[str, Any]:
        token = CancellationToken()
        if request.turn_run_id in self._cancel_before_start:
            token.cancel()
            self._cancel_before_start.discard(request.turn_run_id)
        self._tokens[request.turn_run_id] = token
        dependencies = TurnPipelineDependencies(
            provider=self._provider,
            committer=UowTurnCommitter(self._uow_factory),
            candidate_source=UowCandidateSource(self._uow_factory),
            embedding_store=UowEmbeddingStore(self._uow_factory),
            retrieval_trace_store=UowRetrievalTraceStore(self._uow_factory),
            cancellation=token,
            execution_mode=getattr(getattr(self._provider, "config", None), "mode", self._execution_mode),
            event_sink=self._event_sink,
            # Canonical persistence writes derived intents in the same
            # transaction as the turn; the background worker consumes them.
            derived_job_handler=None,
            max_repair_attempts=self._max_repair_attempts,
            max_revision_attempts=self._max_revision_attempts,
            max_contract_retries=self._max_contract_retries,
            telemetry=self._telemetry,
            input_max_chars=self._input_max_chars,
        )
        graph_request = TurnPipelineRequest(
            turn_run_id=request.turn_run_id,
            playthrough_id=request.playthrough_id,
            branch_id=request.branch_id,
            base_revision=request.base_revision,
            raw_input=request.raw_input,
            actor_id=request.actor_id,
            game_state=request.game_state,
            parent_turn_id=request.parent_turn_id,
            config_snapshot_id=request.config_snapshot_id,
        )
        try:
            if self._checkpoint_path is None:
                pipeline = TurnPipeline(dependencies, checkpointer=build_in_memory_checkpointer())
                return await pipeline.run(graph_request)
            self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            async with sqlite_checkpointer(self._checkpoint_path) as checkpointer:
                pipeline = TurnPipeline(dependencies, checkpointer=checkpointer)
                return await pipeline.run(graph_request)
        finally:
            self._tokens.pop(request.turn_run_id, None)

    def cancel(self, turn_run_id: str) -> None:
        token = self._tokens.get(turn_run_id)
        if token is None:
            self._cancel_before_start.add(turn_run_id)
            return
        token.cancel()

    async def aclose(self) -> None:
        await self._provider.aclose()


__all__ = [
    "GraphTurnRunner",
    "UowCandidateSource",
    "UowEmbeddingStore",
    "UowRetrievalTraceStore",
    "UowTurnCommitter",
]
