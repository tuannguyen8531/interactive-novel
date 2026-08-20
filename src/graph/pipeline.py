"""Public runner for one bounded turn graph invocation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from langgraph.checkpoint.memory import InMemorySaver

from src.application.contracts.providers import CancellationToken, ExecutionMode
from src.application.ports.providers import ProviderPort
from src.application.ports.retrieval import EmbeddingStore, MemoryCandidateSource, RetrievalTraceStore
from src.application.ports.telemetry import TelemetryRecorderPort
from src.domain.guard import DomainGuard

from .builder import build_turn_graph
from .checkpoint import checkpoint_config
from .events import AsyncEventCallback, EventSink
from .runtime import DerivedJobHandler, TurnCommitter, TurnGraphRuntime, TurnPipelineRequest
from .state import TurnGraphState, initial_graph_state


@dataclass(slots=True)
class TurnPipelineDependencies:
    """Runtime services injected from the application composition root."""

    provider: ProviderPort
    committer: TurnCommitter
    candidate_source: MemoryCandidateSource | None = None
    embedding_store: EmbeddingStore | None = None
    retrieval_trace_store: RetrievalTraceStore | None = None
    guard: DomainGuard | None = None
    cancellation: CancellationToken | None = None
    execution_mode: ExecutionMode = ExecutionMode.QUALITY
    event_sink: EventSink | AsyncEventCallback | None = None
    derived_job_handler: DerivedJobHandler | None = None
    max_repair_attempts: int = 1
    max_revision_attempts: int = 1
    max_contract_retries: int = 1
    failure_hook: Callable[[str], None] | None = None
    telemetry: TelemetryRecorderPort | None = None
    input_max_chars: int = 20_000
    embedding_version: str = "phase-13-embedding-1"


class TurnPipeline:
    """Compile/run/resume a turn while keeping checkpoint thread identity stable."""

    def __init__(self, dependencies: TurnPipelineDependencies, *, checkpointer: Any | None = None) -> None:
        self.dependencies = dependencies
        self.checkpointer = checkpointer or InMemorySaver()
        self._graphs: dict[str, Any] = {}
        self._runtimes: dict[str, TurnGraphRuntime] = {}

    async def run(self, request: TurnPipelineRequest) -> TurnGraphState:
        runtime = self._runtime(request)
        graph = build_turn_graph(runtime, checkpointer=self.checkpointer)
        self._graphs[request.turn_run_id] = graph
        self._runtimes[request.turn_run_id] = runtime
        initial = initial_graph_state(
            turn_run_id=request.turn_run_id,
            playthrough_id=request.playthrough_id,
            branch_id=request.branch_id,
            base_revision=request.base_revision,
            parent_turn_id=request.parent_turn_id,
            raw_input=request.raw_input,
            actor_id=request.actor_id,
            config_snapshot_id=request.config_snapshot_id,
        )
        return cast(TurnGraphState, await graph.ainvoke(initial, config=checkpoint_config(request.turn_run_id)))

    async def resume(self, turn_run_id: str) -> TurnGraphState:
        """Resume from the last checkpoint using the same runtime dependencies."""

        graph = self._graphs.get(turn_run_id)
        if graph is None:
            raise ValueError("No runtime graph is registered for this turn run.")
        return cast(TurnGraphState, await graph.ainvoke(None, config=checkpoint_config(turn_run_id)))

    def cancel(self, turn_run_id: str) -> None:
        runtime = self._runtimes.get(turn_run_id)
        if runtime is None or runtime.cancellation is None:
            raise ValueError("No cancellable runtime is registered for this turn run.")
        runtime.cancellation.cancel()

    def _runtime(self, request: TurnPipelineRequest) -> TurnGraphRuntime:
        token = self.dependencies.cancellation or CancellationToken()
        return TurnGraphRuntime(
            request=request,
            provider=self.dependencies.provider,
            candidate_source=self.dependencies.candidate_source,
            embedding_store=self.dependencies.embedding_store,
            retrieval_trace_store=self.dependencies.retrieval_trace_store,
            committer=self.dependencies.committer,
            guard=self.dependencies.guard or DomainGuard(),
            cancellation=token,
            execution_mode=self.dependencies.execution_mode,
            event_sink=self.dependencies.event_sink,
            derived_job_handler=self.dependencies.derived_job_handler,
            max_repair_attempts=self.dependencies.max_repair_attempts,
            max_revision_attempts=self.dependencies.max_revision_attempts,
            max_contract_retries=self.dependencies.max_contract_retries,
            failure_hook=self.dependencies.failure_hook,
            telemetry=self.dependencies.telemetry,
            input_max_chars=self.dependencies.input_max_chars,
            embedding_version=self.dependencies.embedding_version,
        )


__all__ = ["TurnPipeline", "TurnPipelineDependencies", "TurnPipelineRequest"]
