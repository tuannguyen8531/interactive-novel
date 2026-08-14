"""Canonical turn commit and derived intent use cases."""

from __future__ import annotations

from src.application.contracts.persistence import (
    CanonicalTurnBundle,
    DerivedJobRecord,
    InvariantReport,
    PersistenceIdempotencyConflictError,
    PersistenceNotFoundError,
    PersistenceStaleHeadError,
    SnapshotRecord,
    TurnRecord,
)
from src.application.errors import (
    IdempotencyConflictError,
    ResourceNotFoundError,
    StaleBranchRevisionError,
)
from src.application.ports.persistence import UowFactory


class CanonicalTurnApplicationService:
    """Own the transaction boundary for the all-or-nothing canonical commit."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def commit_turn(
        self,
        bundle: CanonicalTurnBundle,
        *,
        fail_after_step: str | None = None,
    ) -> TurnRecord:
        try:
            async with self._uow_factory() as uow:
                result = await uow.canonical.commit_turn(bundle, fail_after_step=fail_after_step)
                await uow.commit()
                return result
        except PersistenceStaleHeadError as error:
            raise StaleBranchRevisionError(str(error)) from error
        except PersistenceIdempotencyConflictError as error:
            raise IdempotencyConflictError(str(error)) from error
        except PersistenceNotFoundError as error:
            raise ResourceNotFoundError(str(error)) from error

    async def save_snapshot(self, snapshot: SnapshotRecord) -> None:
        async with self._uow_factory() as uow:
            await uow.canonical.save_snapshot(snapshot)
            await uow.commit()

    async def verify_invariants(self, branch_id: str) -> InvariantReport:
        async with self._uow_factory() as uow:
            return await uow.canonical.verify_invariants(branch_id)

    async def enqueue_derived_job(self, job: DerivedJobRecord) -> DerivedJobRecord:
        async with self._uow_factory() as uow:
            result = await uow.canonical.enqueue_derived_job(job)
            await uow.commit()
            return result

    async def reconcile_derived_jobs(self) -> int:
        async with self._uow_factory() as uow:
            result = await uow.canonical.reconcile_derived_jobs()
            await uow.commit()
            return result


__all__ = ["CanonicalTurnApplicationService"]
