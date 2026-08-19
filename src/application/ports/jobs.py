"""Application ports for durable background job state."""

from __future__ import annotations

from typing import Protocol

from src.application.contracts.jobs import JobRecord


class JobRepository(Protocol):
    """Storage boundary for application jobs, independent of the ORM."""

    async def add(self, job: JobRecord) -> None: ...

    async def get(self, job_id: str) -> JobRecord | None: ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> JobRecord | None: ...

    async def get_by_turn_run_id(self, turn_run_id: str) -> JobRecord | None: ...

    async def list(
        self,
        *,
        playthrough_id: str | None = None,
        branch_id: str | None = None,
    ) -> list[JobRecord]: ...

    async def update(
        self,
        job_id: str,
        *,
        status: str,
        cancellation_requested: bool | None = None,
        result: dict[str, object] | None = None,
        error: dict[str, object] | None = None,
    ) -> None: ...

    async def mark_interrupted(self) -> int: ...


__all__ = ["JobRepository"]
