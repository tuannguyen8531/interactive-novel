"""Durable turn-job and safe streaming contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

JobStatus = Literal["queued", "running", "cancelling", "completed", "failed", "cancelled", "interrupted"]


def utc_now() -> datetime:
    """Return an aware UTC timestamp for job records and events."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class JobRecord:
    """Persistence-neutral state for one submitted application job."""

    id: str
    kind: str
    idempotency_key: str
    turn_run_id: str
    playthrough_id: str
    branch_id: str
    base_revision: int
    raw_input: str
    actor_id: str
    parent_turn_id: str | None
    config_snapshot_id: str
    command_fingerprint: tuple[Any, ...]
    status: str = "queued"
    cancellation_requested: bool = False
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        idempotency_key: str,
        turn_run_id: str,
        playthrough_id: str,
        branch_id: str,
        base_revision: int,
        raw_input: str,
        actor_id: str,
        parent_turn_id: str | None,
        config_snapshot_id: str,
        command_fingerprint: tuple[Any, ...],
        job_id: str | None = None,
    ) -> JobRecord:
        now = utc_now()
        return cls(
            id=job_id or str(uuid4()),
            kind="turn",
            idempotency_key=idempotency_key,
            turn_run_id=turn_run_id,
            playthrough_id=playthrough_id,
            branch_id=branch_id,
            base_revision=base_revision,
            raw_input=raw_input,
            actor_id=actor_id,
            parent_turn_id=parent_turn_id,
            config_snapshot_id=config_snapshot_id,
            command_fingerprint=tuple(command_fingerprint),
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class JobEvent:
    """Safe event sent to one job's SSE stream."""

    id: str
    job_id: str
    turn_run_id: str
    event_type: str
    phase: str
    payload: dict[str, Any] = field(default_factory=dict)
    payload_version: str = "job-event"
    created_at: datetime = field(default_factory=utc_now)
    terminal: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "turn_run_id": self.turn_run_id,
            "event_type": self.event_type,
            "phase": self.phase,
            "payload": dict(self.payload),
            "payload_version": self.payload_version,
            "created_at": self.created_at.isoformat(),
            "terminal": self.terminal,
        }


__all__ = ["JobEvent", "JobRecord", "JobStatus", "utc_now"]
