"""Background turn submission, durability and concurrency policy."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from src.application.contracts.jobs import JobRecord
from src.application.contracts.persistence import TurnRecord
from src.application.contracts.providers import ProviderError
from src.application.contracts.turns import SubmitTurnCommand, TurnJobView
from src.application.errors import (
    IdempotencyConflictError,
    ResourceConflictError,
    ResourceNotFoundError,
    StaleBranchRevisionError,
)
from src.application.ports.jobs import JobRepository
from src.application.ports.persistence import UowFactory
from src.application.ports.turns import TurnRunner

from .events import InMemoryJobEventBroker


@dataclass(slots=True)
class _PendingTurn:
    command: SubmitTurnCommand
    view: TurnJobView
    task: asyncio.Task[Any] | None = None


class TurnApplicationService:
    """Schedule safe turn jobs with durable state and bounded concurrency."""

    def __init__(
        self,
        uow_factory: UowFactory,
        runner: TurnRunner,
        *,
        job_store: JobRepository | None = None,
        event_broker: InMemoryJobEventBroker | None = None,
        max_concurrency: int = 2,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive.")
        self._uow_factory = uow_factory
        self._runner = runner
        self._job_store = job_store
        self.events = event_broker
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._by_key: dict[str, _PendingTurn] = {}
        self._by_run_id: dict[str, _PendingTurn] = {}
        self._active_by_branch: dict[str, str] = {}
        self._branch_locks: dict[str, asyncio.Lock] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._submission_lock = asyncio.Lock()
        self._accepting = True
        self._stopping = False

    async def start(self) -> int:
        """Recover jobs left in an active state by the previous process."""
        self._accepting = True
        self._stopping = False
        if self._job_store is None:
            return 0
        return await self._job_store.mark_interrupted()

    async def shutdown(self, *, timeout_seconds: float = 5.0) -> None:
        """Stop accepting work and give active jobs a bounded graceful window."""
        self._accepting = False
        self._stopping = True
        for pending in tuple(self._by_run_id.values()):
            if pending.view.status not in _TERMINAL_STATUSES:
                with suppress(ValueError):
                    self._runner.cancel(pending.command.turn_run_id)
        tasks = tuple(self._tasks)
        if tasks:
            done, pending_tasks = await asyncio.wait(tasks, timeout=max(0.0, timeout_seconds))
            del done
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
        if self._job_store is not None:
            await self._job_store.mark_interrupted()

    async def submit_turn(self, command: SubmitTurnCommand) -> TurnJobView:
        if not self._accepting:
            raise ResourceConflictError("The turn runner is shutting down.")
        async with self._submission_lock:
            existing = self._by_key.get(command.idempotency_key)
            if existing is not None:
                return self._validate_existing(command, existing.view, existing.command.fingerprint())

            if self._job_store is not None:
                durable = await self._job_store.get_by_idempotency_key(command.idempotency_key)
                if durable is not None:
                    return self._view_from_job(command, durable)

            async with self._uow_factory() as uow:
                playthrough = await uow.playthroughs.get(command.playthrough_id)
                if playthrough is None:
                    raise ResourceNotFoundError(f"Playthrough {command.playthrough_id} does not exist.")
                branch = await uow.canonical.get_branch(command.branch_id)
                if branch is None or branch.playthrough_id != command.playthrough_id:
                    raise ResourceNotFoundError(f"Branch {command.branch_id} does not belong to this playthrough.")
                if branch.lifecycle != "active" or playthrough.lifecycle != "active":
                    raise ResourceConflictError("Cannot submit a turn to an inactive playthrough or branch.")
                if branch.head_revision != command.base_revision:
                    raise StaleBranchRevisionError(
                        f"Expected branch revision {command.base_revision}, found {branch.head_revision}."
                    )
                persisted = await uow.canonical.get_turn_by_run_id(command.turn_run_id)

            if persisted is not None:
                return self._completed_from_persisted(command, persisted)
            if self._job_store is not None:
                durable_by_run = await self._job_store.get_by_turn_run_id(command.turn_run_id)
                if durable_by_run is not None:
                    return self._view_from_job(command, durable_by_run)

            active_run_id = self._active_by_branch.get(command.branch_id)
            if active_run_id is not None:
                raise ResourceConflictError(
                    "Only one active turn is allowed on a branch.",
                    details={"branch_id": command.branch_id, "active_turn_run_id": active_run_id},
                )
            previous = self._by_run_id.get(command.turn_run_id)
            if previous is not None:
                return self._validate_existing(command, previous.view, previous.command.fingerprint())

            now = datetime.now(UTC)
            job = JobRecord.new(
                idempotency_key=command.idempotency_key,
                turn_run_id=command.turn_run_id,
                playthrough_id=command.playthrough_id,
                branch_id=command.branch_id,
                base_revision=command.base_revision,
                raw_input=command.raw_input,
                actor_id=command.actor_id,
                parent_turn_id=command.parent_turn_id,
                config_snapshot_id=command.config_snapshot_id,
                command_fingerprint=command.fingerprint(),
            )
            if self._job_store is not None:
                await self._job_store.add(job)
            pending = _PendingTurn(
                command=command,
                view=TurnJobView(
                    idempotency_key=command.idempotency_key,
                    turn_run_id=command.turn_run_id,
                    playthrough_id=command.playthrough_id,
                    branch_id=command.branch_id,
                    status="queued",
                    job_id=job.id,
                    created_at=now,
                    updated_at=now,
                ),
            )
            self._by_key[command.idempotency_key] = pending
            self._by_run_id[command.turn_run_id] = pending
            self._active_by_branch[command.branch_id] = command.turn_run_id

        if self.events is not None:
            await self.events.register(job_id=job.id, turn_run_id=command.turn_run_id)
            await self.events.publish_job_event(
                job_id=job.id,
                turn_run_id=command.turn_run_id,
                event_type="job_queued",
                phase="job",
                payload={"status": "queued"},
            )
        pending.task = asyncio.create_task(self._execute(pending), name=f"turn-job:{command.turn_run_id}")
        self._tasks.add(pending.task)
        pending.task.add_done_callback(self._tasks.discard)
        return pending.view

    async def get_turn(self, turn_id_or_run_id: str) -> TurnRecord | TurnJobView | None:
        pending = self._by_run_id.get(turn_id_or_run_id)
        if pending is not None:
            return pending.view
        if self._job_store is not None:
            durable = await self._job_store.get(turn_id_or_run_id)
            if durable is None:
                durable = await self._job_store.get_by_turn_run_id(turn_id_or_run_id)
            if durable is not None:
                return self._view_from_job_record(durable)
        async with self._uow_factory() as uow:
            persisted = await uow.canonical.get_turn(turn_id_or_run_id)
            if persisted is None:
                persisted = await uow.canonical.get_turn_by_run_id(turn_id_or_run_id)
        return persisted

    async def get_job(self, job_id: str) -> TurnJobView | None:
        for pending in self._by_run_id.values():
            if pending.view.job_id == job_id:
                return pending.view
        if self._job_store is None:
            return None
        durable = await self._job_store.get(job_id)
        return None if durable is None else self._view_from_job_record(durable)

    async def list_jobs(
        self,
        *,
        playthrough_id: str | None = None,
        branch_id: str | None = None,
    ) -> tuple[TurnJobView, ...]:
        if self._job_store is not None:
            jobs = await self._job_store.list(playthrough_id=playthrough_id, branch_id=branch_id)
            return tuple(self._view_from_job_record(job) for job in jobs)
        values = [pending.view for pending in self._by_run_id.values()]
        return tuple(
            item
            for item in values
            if (playthrough_id is None or item.playthrough_id == playthrough_id)
            and (branch_id is None or item.branch_id == branch_id)
        )

    async def cancel_turn(self, turn_run_id: str) -> TurnJobView:
        pending = self._by_run_id.get(turn_run_id)
        if pending is None:
            if self._job_store is not None:
                durable = await self._job_store.get_by_turn_run_id(turn_run_id)
                if durable is not None:
                    if durable.status in _TERMINAL_STATUSES:
                        return self._view_from_job_record(durable)
                    await self._job_store.update(
                        durable.id,
                        status="cancelled",
                        cancellation_requested=True,
                    )
                    cancelled = replace(self._view_from_job_record(durable), status="cancelled", cancellation_requested=True)
                    if self.events is not None:
                        await self.events.register(job_id=durable.id, turn_run_id=durable.turn_run_id)
                        await self.events.publish_job_event(
                            job_id=durable.id,
                            turn_run_id=durable.turn_run_id,
                            event_type="cancelled",
                            phase="job",
                            payload={"status": "cancelled"},
                            terminal=True,
                        )
                    return cancelled
            async with self._uow_factory() as uow:
                persisted = await uow.canonical.get_turn_by_run_id(turn_run_id)
            if persisted is None:
                raise ResourceNotFoundError(f"Turn run {turn_run_id} does not exist.")
            return self._completed_from_persisted(
                SubmitTurnCommand(
                    idempotency_key=turn_run_id,
                    turn_run_id=persisted.turn_run_id,
                    playthrough_id=persisted.playthrough_id,
                    branch_id=persisted.branch_id,
                    base_revision=persisted.base_revision,
                    raw_input=persisted.raw_input,
                    actor_id="unknown",
                    game_state=_placeholder_game_state(persisted),
                ),
                persisted,
            )
        if pending.view.status in _TERMINAL_STATUSES:
            return pending.view
        pending.view = replace(
            pending.view,
            status="cancelling",
            cancellation_requested=True,
            updated_at=datetime.now(UTC),
        )
        await self._persist_view(pending.view)
        if self.events is not None and pending.view.job_id is not None:
            await self.events.publish_job_event(
                job_id=pending.view.job_id,
                turn_run_id=turn_run_id,
                event_type="cancellation_requested",
                phase="job",
                payload={"status": "cancelling"},
            )
        with suppress(ValueError):
            self._runner.cancel(turn_run_id)
        return pending.view

    async def wait_for_turn(self, turn_run_id: str) -> TurnJobView:
        pending = self._by_run_id.get(turn_run_id)
        if pending is None:
            result = await self.get_turn(turn_run_id)
            if isinstance(result, TurnJobView):
                return result
            if result is None:
                raise ResourceNotFoundError(f"Turn run {turn_run_id} does not exist.")
            return TurnJobView(
                idempotency_key=turn_run_id,
                turn_run_id=result.turn_run_id,
                playthrough_id=result.playthrough_id,
                branch_id=result.branch_id,
                status="completed",
                result=result,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
        if pending.task is not None:
            await pending.task
        return pending.view

    async def _execute(self, pending: _PendingTurn) -> None:
        pending.view = replace(pending.view, status="running", updated_at=datetime.now(UTC))
        await self._persist_view(pending.view)
        if self.events is not None and pending.view.job_id is not None:
            await self.events.publish_job_event(
                job_id=pending.view.job_id,
                turn_run_id=pending.command.turn_run_id,
                event_type="job_running",
                phase="job",
                payload={"status": "running"},
            )
        branch_lock = self._branch_locks.setdefault(pending.command.branch_id, asyncio.Lock())
        try:
            async with self._semaphore, branch_lock:
                if pending.view.cancellation_requested:
                    with suppress(ValueError):
                        self._runner.cancel(pending.command.turn_run_id)
                raw_result = await self._runner.run(pending.command.run_request())
            pending.view = self._view_from_result(pending.view, raw_result)
        except asyncio.CancelledError:
            if self._stopping:
                pending.view = replace(
                    pending.view,
                    status="interrupted",
                    error={"code": "interrupted", "message": "The application stopped before this job completed."},
                    updated_at=datetime.now(UTC),
                )
            else:
                pending.view = replace(
                    pending.view,
                    status="cancelled",
                    cancellation_requested=True,
                    updated_at=datetime.now(UTC),
                )
        except Exception as error:
            pending.view = replace(
                pending.view,
                status="cancelled" if pending.view.cancellation_requested else "failed",
                error=_error_payload(error),
                updated_at=datetime.now(UTC),
            )
        finally:
            await self._persist_view(pending.view)
            if self.events is not None and pending.view.job_id is not None and pending.view.status in _TERMINAL_STATUSES:
                await self.events.publish_job_event(
                    job_id=pending.view.job_id,
                    turn_run_id=pending.command.turn_run_id,
                    event_type=pending.view.status,
                    phase="job",
                    payload={
                        "status": pending.view.status,
                        "result": _json_safe(pending.view.result),
                        "error": _json_safe(pending.view.error),
                    },
                    terminal=True,
                )
            if self._active_by_branch.get(pending.command.branch_id) == pending.command.turn_run_id:
                self._active_by_branch.pop(pending.command.branch_id, None)

    async def _persist_view(self, view: TurnJobView) -> None:
        if self._job_store is None or view.job_id is None:
            return
        result = _json_safe(view.result)
        result_payload = result if isinstance(result, dict) else ({"value": result} if result is not None else None)
        await self._job_store.update(
            view.job_id,
            status=view.status,
            cancellation_requested=view.cancellation_requested,
            result=result_payload,
            error=view.error,
        )

    def _view_from_result(self, current: TurnJobView, raw_result: object) -> TurnJobView:
        if isinstance(raw_result, Mapping):
            graph_status = str(raw_result.get("status", ""))
            committed = bool(raw_result.get("commit_done", False))
            if committed:
                status = "completed"
            elif graph_status in {"cancelled", "cancelling"}:
                status = "cancelled"
            else:
                status = "failed"
            result = raw_result.get("committed_turn", raw_result.get("result"))
            error_value = raw_result.get("errors")
            error = None if not error_value else {"diagnostics": _json_safe(error_value)}
            return replace(
                current,
                status=status,
                result=result,
                error=error,
                updated_at=datetime.now(UTC),
            )
        return replace(current, status="completed", result=raw_result, updated_at=datetime.now(UTC))

    @staticmethod
    def _completed_from_persisted(command: SubmitTurnCommand, persisted: TurnRecord) -> TurnJobView:
        if persisted.raw_input != command.raw_input or persisted.branch_id != command.branch_id:
            raise IdempotencyConflictError("The turn run ID was reused for a different turn.")
        return TurnJobView(
            idempotency_key=command.idempotency_key,
            turn_run_id=persisted.turn_run_id,
            playthrough_id=persisted.playthrough_id,
            branch_id=persisted.branch_id,
            status="completed" if persisted.status == "completed" else persisted.status,
            result=persisted,
            created_at=persisted.created_at,
            updated_at=persisted.updated_at,
        )

    @staticmethod
    def _validate_existing(command: SubmitTurnCommand, view: TurnJobView, fingerprint: tuple[Any, ...]) -> TurnJobView:
        if tuple(fingerprint) != command.fingerprint():
            raise IdempotencyConflictError(
                "The idempotency key was reused for a different turn command.",
                details={"idempotency_key": command.idempotency_key},
            )
        return view

    @staticmethod
    def _view_from_job(command: SubmitTurnCommand, job: JobRecord) -> TurnJobView:
        if tuple(job.command_fingerprint) != command.fingerprint():
            raise IdempotencyConflictError(
                "The idempotency key or turn run ID was reused for a different turn command.",
                details={"idempotency_key": command.idempotency_key},
            )
        return TurnApplicationService._view_from_job_record(job)

    @staticmethod
    def _view_from_job_record(job: JobRecord) -> TurnJobView:
        return TurnJobView(
            idempotency_key=job.idempotency_key,
            turn_run_id=job.turn_run_id,
            playthrough_id=job.playthrough_id,
            branch_id=job.branch_id,
            status=job.status,
            result=job.result,
            error=job.error,
            cancellation_requested=job.cancellation_requested,
            job_id=job.id,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "interrupted"})


def _error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, ProviderError):
        details: dict[str, Any] = {"provider": error.provider}
        if error.request_id is not None:
            details["request_id"] = error.request_id
        if error.status_code is not None:
            details["status_code"] = error.status_code
        return {"code": error.code, "message": str(error), "details": details}
    return {"code": type(error).__name__, "message": str(error)}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_safe(asdict(value))  # type: ignore[arg-type]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _placeholder_game_state(record: TurnRecord):
    """Build only the scope needed for a terminal persisted-turn DTO."""
    from src.domain.state import GameState

    return GameState.empty(
        world_id="unknown",
        playthrough_id=record.playthrough_id,
        branch_id=record.branch_id,
        world_time=record.world_time_start,
    )


__all__ = ["TurnApplicationService"]
