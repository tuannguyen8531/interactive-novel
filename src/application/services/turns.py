"""Application turn submission, cancellation and in-process concurrency policy."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from src.application.contracts.persistence import TurnRecord
from src.application.contracts.turns import SubmitTurnCommand, TurnJobView
from src.application.errors import (
    IdempotencyConflictError,
    ResourceConflictError,
    ResourceNotFoundError,
    StaleBranchRevisionError,
)
from src.application.ports.persistence import UowFactory
from src.application.ports.turns import TurnRunner


@dataclass(slots=True)
class _PendingTurn:
    command: SubmitTurnCommand
    view: TurnJobView
    task: asyncio.Task[Any] | None = None


class TurnApplicationService:
    """Schedule one turn at a time per branch and preserve idempotent retries."""

    def __init__(self, uow_factory: UowFactory, runner: TurnRunner) -> None:
        self._uow_factory = uow_factory
        self._runner = runner
        self._by_key: dict[str, _PendingTurn] = {}
        self._by_run_id: dict[str, _PendingTurn] = {}
        self._active_by_branch: dict[str, str] = {}
        self._submission_lock = asyncio.Lock()

    async def submit_turn(self, command: SubmitTurnCommand) -> TurnJobView:
        existing = self._by_key.get(command.idempotency_key)
        if existing is not None:
            if existing.command.fingerprint() != command.fingerprint():
                raise IdempotencyConflictError(
                    "The idempotency key was reused for a different turn command.",
                    details={"idempotency_key": command.idempotency_key},
                )
            return existing.view

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
                raise StaleBranchRevisionError(f"Expected branch revision {command.base_revision}, found {branch.head_revision}.")
            persisted = await uow.canonical.get_turn_by_run_id(command.turn_run_id)

        if persisted is not None:
            return self._completed_from_persisted(command, persisted)
        async with self._submission_lock:
            active_run_id = self._active_by_branch.get(command.branch_id)
            if active_run_id is not None:
                raise ResourceConflictError(
                    "Only one active turn is allowed on a branch.",
                    details={"branch_id": command.branch_id, "active_turn_run_id": active_run_id},
                )
            if command.turn_run_id in self._by_run_id:
                previous = self._by_run_id[command.turn_run_id]
                if previous.command.fingerprint() != command.fingerprint():
                    raise IdempotencyConflictError("The turn run ID was reused for a different command.")
                return previous.view

            now = datetime.now(UTC)
            pending = _PendingTurn(
                command=command,
                view=TurnJobView(
                    idempotency_key=command.idempotency_key,
                    turn_run_id=command.turn_run_id,
                    playthrough_id=command.playthrough_id,
                    branch_id=command.branch_id,
                    status="queued",
                    created_at=now,
                    updated_at=now,
                ),
            )
            self._by_key[command.idempotency_key] = pending
            self._by_run_id[command.turn_run_id] = pending
            self._active_by_branch[command.branch_id] = command.turn_run_id
        pending.task = asyncio.create_task(self._execute(pending))
        return pending.view

    async def get_turn(self, turn_id_or_run_id: str) -> TurnRecord | TurnJobView | None:
        pending = self._by_run_id.get(turn_id_or_run_id)
        if pending is not None:
            return pending.view
        async with self._uow_factory() as uow:
            persisted = await uow.canonical.get_turn(turn_id_or_run_id)
            if persisted is None:
                persisted = await uow.canonical.get_turn_by_run_id(turn_id_or_run_id)
        return persisted

    async def cancel_turn(self, turn_run_id: str) -> TurnJobView:
        pending = self._by_run_id.get(turn_run_id)
        if pending is None:
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
        if pending.view.status in {"completed", "failed", "cancelled"}:
            return pending.view
        pending.view = replace(
            pending.view,
            status="cancelling",
            cancellation_requested=True,
            updated_at=datetime.now(UTC),
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
            )
        if pending.task is not None:
            await pending.task
        return pending.view

    async def _execute(self, pending: _PendingTurn) -> None:
        pending.view = replace(pending.view, status="running", updated_at=datetime.now(UTC))
        if pending.view.cancellation_requested:
            with suppress(ValueError):
                self._runner.cancel(pending.command.turn_run_id)
        try:
            raw_result = await self._runner.run(pending.command.run_request())
            pending.view = self._view_from_result(pending.view, raw_result)
        except asyncio.CancelledError:
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
                error={"code": type(error).__name__, "message": str(error)},
                updated_at=datetime.now(UTC),
            )
        finally:
            if self._active_by_branch.get(pending.command.branch_id) == pending.command.turn_run_id:
                self._active_by_branch.pop(pending.command.branch_id, None)

    def _view_from_result(self, current: TurnJobView, raw_result: object) -> TurnJobView:
        if isinstance(raw_result, Mapping):
            graph_status = str(raw_result.get("status", ""))
            if graph_status in {"cancelled", "cancelling"}:
                status = "cancelled"
            elif bool(raw_result.get("commit_done", False)) or graph_status in {"completed", "committed"}:
                status = "completed"
            else:
                status = "failed"
            result = raw_result.get("committed_turn", raw_result.get("result"))
            error_value = raw_result.get("errors")
            error = None if not error_value else {"diagnostics": error_value}
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
