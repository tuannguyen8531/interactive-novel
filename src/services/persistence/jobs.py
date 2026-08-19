"""SQLAlchemy adapter for durable application jobs."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.contracts.jobs import JobRecord
from src.application.contracts.persistence import utc_now

from .models import JobModel


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _job_record(model: JobModel) -> JobRecord:
    return JobRecord(
        id=model.id,
        kind=model.kind,
        idempotency_key=model.idempotency_key,
        turn_run_id=model.turn_run_id,
        playthrough_id=model.playthrough_id,
        branch_id=model.branch_id,
        base_revision=model.base_revision,
        raw_input=model.raw_input,
        actor_id=model.actor_id,
        parent_turn_id=model.parent_turn_id,
        config_snapshot_id=model.config_snapshot_id,
        command_fingerprint=tuple(model.command_fingerprint),
        status=model.status,
        cancellation_requested=bool(model.cancellation_requested),
        result=None if model.result is None else dict(model.result),
        error=None if model.error is None else dict(model.error),
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


class SqlAlchemyJobRepository:
    """Application-job repository sharing the current UoW session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: JobRecord) -> None:
        self._session.add(
            JobModel(
                id=job.id,
                kind=job.kind,
                idempotency_key=job.idempotency_key,
                turn_run_id=job.turn_run_id,
                playthrough_id=job.playthrough_id,
                branch_id=job.branch_id,
                base_revision=job.base_revision,
                raw_input=job.raw_input,
                actor_id=job.actor_id,
                parent_turn_id=job.parent_turn_id,
                config_snapshot_id=job.config_snapshot_id,
                command_fingerprint=list(job.command_fingerprint),
                status=job.status,
                cancellation_requested=job.cancellation_requested,
                result=None if job.result is None else dict(job.result),
                error=None if job.error is None else dict(job.error),
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )
        await self._session.flush()

    async def get(self, job_id: str) -> JobRecord | None:
        return await self._get(select(JobModel).where(JobModel.id == job_id))

    async def get_by_idempotency_key(self, idempotency_key: str) -> JobRecord | None:
        return await self._get(select(JobModel).where(JobModel.idempotency_key == idempotency_key))

    async def get_by_turn_run_id(self, turn_run_id: str) -> JobRecord | None:
        return await self._get(select(JobModel).where(JobModel.turn_run_id == turn_run_id))

    async def list(
        self,
        *,
        playthrough_id: str | None = None,
        branch_id: str | None = None,
    ) -> list[JobRecord]:
        statement = select(JobModel).order_by(JobModel.created_at, JobModel.id)
        if playthrough_id is not None:
            statement = statement.where(JobModel.playthrough_id == playthrough_id)
        if branch_id is not None:
            statement = statement.where(JobModel.branch_id == branch_id)
        models = (await self._session.scalars(statement)).all()
        return [_job_record(model) for model in models]

    async def update(
        self,
        job_id: str,
        *,
        status: str,
        cancellation_requested: bool | None = None,
        result: dict[str, object] | None = None,
        error: dict[str, object] | None = None,
    ) -> None:
        values: dict[str, object] = {"status": status, "updated_at": utc_now()}
        if cancellation_requested is not None:
            values["cancellation_requested"] = cancellation_requested
        if result is not None:
            values["result"] = dict(result)
        if error is not None:
            values["error"] = dict(error)
        changed = await self._session.execute(update(JobModel).where(JobModel.id == job_id).values(**values))
        if getattr(changed, "rowcount", None) != 1:
            raise ValueError(f"Job {job_id} does not exist.")
        await self._session.flush()

    async def mark_interrupted(self) -> int:
        changed = await self._session.execute(
            update(JobModel)
            .where(JobModel.status.in_(("queued", "running", "cancelling")))
            .values(
                status="interrupted",
                error={"code": "interrupted", "message": "The application stopped before this job completed."},
                updated_at=utc_now(),
            )
        )
        await self._session.flush()
        return int(getattr(changed, "rowcount", 0) or 0)

    async def _get(self, statement):
        model = await self._session.scalar(statement)
        return None if model is None else _job_record(model)


__all__ = ["SqlAlchemyJobRepository"]
