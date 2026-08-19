"""Application-facing LangGraph runner adapter."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.application.contracts.persistence import CanonicalTurnBundle, DerivedJobRecord
from src.application.contracts.providers import CancellationToken, ExecutionMode
from src.application.contracts.retrieval import RetrievalScope
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
            cancellation=token,
            execution_mode=self._execution_mode,
            event_sink=self._event_sink,
            derived_job_handler=self._enqueue_derived_jobs,
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

    async def _enqueue_derived_jobs(
        self,
        intents: tuple[dict[str, Any], ...],
        bundle: CanonicalTurnBundle,
    ) -> None:
        async with self._uow_factory() as uow:
            for intent in intents:
                job_type = str(intent["job_type"])
                await uow.canonical.enqueue_derived_job(
                    DerivedJobRecord(
                        id=str(uuid4()),
                        idempotency_key=f"{bundle.turn_id}:{job_type}",
                        job_type=job_type,
                        playthrough_id=bundle.playthrough_id,
                        branch_id=bundle.branch_id,
                        source_turn_id=bundle.turn_id,
                        source_revision=bundle.base_revision + 1,
                        payload={"source": "turn_commit"},
                    )
                )
            await uow.commit()


__all__ = ["GraphTurnRunner", "UowCandidateSource", "UowTurnCommitter"]
