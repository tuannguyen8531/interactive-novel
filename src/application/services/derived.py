"""Application orchestration for post-commit memory and index jobs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import replace
from typing import Any

from src.application.contracts.persistence import DerivedArtifactRecord, DerivedJobRecord, SnapshotRecord
from src.application.contracts.retrieval import RetrievalScope
from src.application.ports.persistence import UowFactory
from src.application.ports.providers import ProviderPort
from src.domain.codec import state_to_payload
from src.services.memory.analysis import MemoryConsolidator
from src.services.retrieval.rebuild import EmbeddingRebuildService

from .game_states import GameStateApplicationService

LOGGER = logging.getLogger(__name__)


class DerivedJobApplicationService:
    """Run retryable derived work without putting it on the canonical commit path."""

    def __init__(
        self,
        uow_factory: UowFactory,
        *,
        embedding_provider: ProviderPort | None = None,
        game_states: GameStateApplicationService | None = None,
        embedding_version: str = "phase-13-embedding-1",
        summary_window_turns: int = 10,
    ) -> None:
        self._uow_factory = uow_factory
        self._embedding_provider = embedding_provider
        self._game_states = game_states
        self._embedding_version = embedding_version
        self._consolidator = MemoryConsolidator(window_turns=summary_window_turns)

    async def process_pending(self, *, limit: int = 10) -> tuple[DerivedJobRecord, ...]:
        """Claim no locks and process a bounded queue snapshot idempotently."""
        if limit <= 0:
            raise ValueError("Derived job limit must be positive.")
        async with self._uow_factory() as uow:
            pending = tuple((await uow.canonical.list_derived_jobs(status="queued"))[:limit])
        processed: list[DerivedJobRecord] = []
        for job in pending:
            processed.append(await self.process_job(job))
        return tuple(processed)

    async def process_job(self, job: DerivedJobRecord) -> DerivedJobRecord:
        """Process one job and preserve canonical completion on derived failure."""
        async with self._uow_factory() as uow:
            try:
                status, error = await self._process_in_uow(uow, job)
            except Exception as exc:  # derived jobs are explicitly retryable
                status, error = "failed", str(exc)
            await uow.canonical.mark_derived_job(job.id, status=status, error=error)
            await uow.commit()
        return replace(job, status=status, last_error=error, attempts=job.attempts + 1)

    async def reconcile(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        source_revision: int,
        artifact_types: Iterable[str] = ("episodic_summary", "embedding_manifest"),
    ) -> dict[str, str]:
        """Report missing/stale projections; callers can fall back to canon."""
        async with self._uow_factory() as uow:
            result: dict[str, str] = {}
            for artifact_type in artifact_types:
                artifact = await uow.derived.get_latest(
                    playthrough_id=playthrough_id,
                    branch_id=branch_id,
                    artifact_type=artifact_type,
                )
                if artifact is None:
                    result[artifact_type] = "missing"
                elif artifact.source_revision != source_revision:
                    result[artifact_type] = "stale"
                else:
                    result[artifact_type] = "fresh"
            return result

    async def _process_in_uow(self, uow: Any, job: DerivedJobRecord) -> tuple[str, str | None]:
        branch = await uow.canonical.get_branch(job.branch_id)
        if branch is None:
            raise ValueError(f"Branch {job.branch_id} does not exist.")
        if job.source_revision < branch.head_revision:
            # A newer canonical turn owns another intent of the same type. Do
            # not label current-head data with this older source revision.
            return "completed", None
        if job.source_revision > branch.head_revision:
            raise ValueError("Derived job source revision is ahead of the branch head.")
        if job.job_type == "summary":
            await self._build_summaries(uow, job)
            return "completed", None
        if job.job_type == "embedding":
            await self._rebuild_embeddings(uow, job)
            return "completed", None
        if job.job_type == "snapshot":
            snapshot = await uow.canonical.load_latest_snapshot(job.branch_id)
            if snapshot is not None and snapshot.source_revision >= job.source_revision:
                return "completed", None
            await self._build_snapshot(uow, job)
            return "completed", None
        return "failed", f"Unsupported derived job type: {job.job_type}"

    async def _build_summaries(self, uow: Any, job: DerivedJobRecord) -> None:
        branch = await uow.canonical.get_branch(job.branch_id)
        if branch is None:
            raise ValueError(f"Branch {job.branch_id} does not exist.")
        ancestry = await uow.canonical.get_branch_ancestry(job.branch_id)
        turns = [turn for turn in await uow.canonical.list_visible_turns(job.branch_id) if turn.status == "completed"]
        events = await uow.canonical.list_visible_events(job.branch_id)
        world_time = max((item.world_time_end for item in turns), default=0)
        scope = RetrievalScope(
            playthrough_id=job.playthrough_id,
            branch_id=job.branch_id,
            branch_ancestry=tuple(item.id for item in ancestry),
            world_time=world_time,
        )
        candidates = await uow.retrieval.list_candidates(scope)
        summaries = self._consolidator.consolidate(
            playthrough_id=job.playthrough_id,
            branch_id=job.branch_id,
            source_revision=job.source_revision,
            turns=turns,
            candidates=candidates,
        )
        for summary in summaries:
            payload = summary.as_dict()
            payload["source_event_ids"] = [event.event_id for event in events if event.event_id in summary.source_ids]
            await uow.derived.save(
                DerivedArtifactRecord.new(
                    artifact_type="episodic_summary",
                    playthrough_id=summary.playthrough_id,
                    branch_id=summary.branch_id,
                    source_turn_id=summary.turn_ids[-1],
                    source_revision=summary.source_revision,
                    artifact_version=summary.summary_version,
                    payload=payload,
                    artifact_id=summary.summary_id,
                )
            )

    async def _build_snapshot(self, uow: Any, job: DerivedJobRecord) -> None:
        if self._game_states is None:
            raise RuntimeError("Game-state loader is not configured.")
        branch = await uow.canonical.get_branch(job.branch_id)
        if branch is None:
            raise ValueError(f"Branch {job.branch_id} does not exist.")
        playthrough = await uow.playthroughs.get(job.playthrough_id)
        if playthrough is None:
            raise ValueError(f"Playthrough {job.playthrough_id} does not exist.")
        state = await self._game_states.load(playthrough_id=job.playthrough_id, branch_id=job.branch_id)
        await uow.canonical.save_snapshot(
            SnapshotRecord.from_payload(
                playthrough_id=job.playthrough_id,
                branch_id=job.branch_id,
                source_turn_id=branch.head_turn_id,
                source_revision=branch.head_revision,
                world_clock_minutes=state.world_time,
                rng_state=playthrough.rng_state,
                state_payload=state_to_payload(state),
                builder_version="phase-13-state-loader-1",
            )
        )

    async def _rebuild_embeddings(self, uow: Any, job: DerivedJobRecord) -> None:
        if self._embedding_provider is None:
            raise RuntimeError("Embedding provider is not configured.")
        ancestry = await uow.canonical.get_branch_ancestry(job.branch_id)
        events = await uow.canonical.list_visible_events(job.branch_id)
        scope = RetrievalScope(
            playthrough_id=job.playthrough_id,
            branch_id=job.branch_id,
            branch_ancestry=tuple(item.id for item in ancestry),
            world_time=max((item.world_time for item in events), default=0),
        )
        report = await EmbeddingRebuildService(
            uow.retrieval,
            embedding_version=self._embedding_version,
        ).rebuild(
            scope,
            uow.retrieval,
            provider=self._embedding_provider,
        )
        if report.failed_source_ids:
            raise RuntimeError(f"Embedding rebuild failed for {len(report.failed_source_ids)} sources.")
        await uow.derived.save(
            DerivedArtifactRecord.new(
                artifact_type="embedding_manifest",
                playthrough_id=job.playthrough_id,
                branch_id=job.branch_id,
                source_turn_id=job.source_turn_id,
                source_revision=job.source_revision,
                artifact_version=self._embedding_version,
                payload={
                    "candidate_count": report.candidate_count,
                    "indexed_count": report.indexed_count,
                    "model": report.model,
                    "embedding_version": report.embedding_version,
                },
            )
        )


DerivedArtifactApplicationService = DerivedJobApplicationService


class DerivedJobWorker:
    """Single-process, bounded worker for the durable derived queue."""

    def __init__(self, service: DerivedJobApplicationService, *, poll_seconds: float = 1.0, batch_size: int = 10) -> None:
        if poll_seconds <= 0 or batch_size <= 0:
            raise ValueError("Derived worker settings must be positive.")
        self._service = service
        self._poll_seconds = poll_seconds
        self._batch_size = batch_size
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="derived-job-worker")

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                processed = await self._service.process_pending(limit=self._batch_size)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Derived job worker iteration failed.")
                processed = ()
            if processed:
                continue
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self._poll_seconds)


__all__ = ["DerivedArtifactApplicationService", "DerivedJobApplicationService", "DerivedJobWorker"]
