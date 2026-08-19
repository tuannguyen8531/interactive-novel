"""Small adapters that keep job orchestration independent of SQLAlchemy."""

from __future__ import annotations

from dataclasses import replace

from src.application.contracts.jobs import JobRecord
from src.application.ports.jobs import JobRepository
from src.application.ports.persistence import UowFactory


class UowJobStore:
    """Use the application UoW for each short durable-job transaction."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def add(self, job: JobRecord) -> None:
        async with self._uow_factory() as uow:
            await uow.jobs.add(job)
            await uow.commit()

    async def get(self, job_id: str) -> JobRecord | None:
        async with self._uow_factory() as uow:
            return await uow.jobs.get(job_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> JobRecord | None:
        async with self._uow_factory() as uow:
            return await uow.jobs.get_by_idempotency_key(idempotency_key)

    async def get_by_turn_run_id(self, turn_run_id: str) -> JobRecord | None:
        async with self._uow_factory() as uow:
            return await uow.jobs.get_by_turn_run_id(turn_run_id)

    async def list(
        self,
        *,
        playthrough_id: str | None = None,
        branch_id: str | None = None,
    ) -> list[JobRecord]:
        async with self._uow_factory() as uow:
            return await uow.jobs.list(playthrough_id=playthrough_id, branch_id=branch_id)

    async def update(
        self,
        job_id: str,
        *,
        status: str,
        cancellation_requested: bool | None = None,
        result: dict[str, object] | None = None,
        error: dict[str, object] | None = None,
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.jobs.update(
                job_id,
                status=status,
                cancellation_requested=cancellation_requested,
                result=result,
                error=error,
            )
            await uow.commit()

    async def mark_interrupted(self) -> int:
        async with self._uow_factory() as uow:
            count = await uow.jobs.mark_interrupted()
            await uow.commit()
            return count


class InMemoryJobStore:
    """Deterministic durable-store substitute for API/application tests."""

    def __init__(self) -> None:
        self.jobs: dict[str, JobRecord] = {}

    async def add(self, job: JobRecord) -> None:
        self.jobs[job.id] = job

    async def get(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> JobRecord | None:
        return next((job for job in self.jobs.values() if job.idempotency_key == idempotency_key), None)

    async def get_by_turn_run_id(self, turn_run_id: str) -> JobRecord | None:
        return next((job for job in self.jobs.values() if job.turn_run_id == turn_run_id), None)

    async def list(
        self,
        *,
        playthrough_id: str | None = None,
        branch_id: str | None = None,
    ) -> list[JobRecord]:
        values = list(self.jobs.values())
        return [
            job
            for job in values
            if (playthrough_id is None or job.playthrough_id == playthrough_id)
            and (branch_id is None or job.branch_id == branch_id)
        ]

    async def update(
        self,
        job_id: str,
        *,
        status: str,
        cancellation_requested: bool | None = None,
        result: dict[str, object] | None = None,
        error: dict[str, object] | None = None,
    ) -> None:
        current = self.jobs[job_id]
        self.jobs[job_id] = replace(
            current,
            status=status,
            cancellation_requested=(current.cancellation_requested if cancellation_requested is None else cancellation_requested),
            result=current.result if result is None else dict(result),
            error=current.error if error is None else dict(error),
        )

    async def mark_interrupted(self) -> int:
        count = 0
        for job_id, job in tuple(self.jobs.items()):
            if job.status in {"queued", "running", "cancelling"}:
                self.jobs[job_id] = replace(
                    job,
                    status="interrupted",
                    error={"code": "interrupted", "message": "The application stopped before this job completed."},
                )
                count += 1
        return count


def as_job_repository(store: JobRepository) -> JobRepository:
    """Keep a narrow, explicit typing boundary for injected job stores."""
    return store


__all__ = ["InMemoryJobStore", "UowJobStore", "as_job_repository"]
