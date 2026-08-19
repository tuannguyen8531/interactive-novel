"""Persistence ports owned by the application layer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.application.contracts.persistence import (
    BranchRecord,
    CanonicalTurnBundle,
    DerivedJobRecord,
    EventRecord,
    InvariantReport,
    PlaythroughRecord,
    SnapshotRecord,
    TurnRecord,
    WorldRecord,
)

from .retrieval import MemoryCandidateSource


class WorldRepository(Protocol):
    async def add(self, world: WorldRecord) -> None: ...

    async def get(self, world_id: str) -> WorldRecord | None: ...


class PlaythroughRepository(Protocol):
    async def add(self, playthrough: PlaythroughRecord) -> None: ...

    async def get(self, playthrough_id: str) -> PlaythroughRecord | None: ...

    async def set_root_branch(self, playthrough_id: str, branch_id: str) -> None: ...


class CanonicalRepository(Protocol):
    """Persistence port for canonical turn, branch and derived boundaries."""

    async def add_branch(self, branch: BranchRecord) -> None: ...

    async def get_branch(self, branch_id: str) -> BranchRecord | None: ...

    async def get_turn(self, turn_id: str) -> TurnRecord | None: ...

    async def get_branch_ancestry(self, branch_id: str) -> list[BranchRecord]: ...

    async def verify_invariants(self, branch_id: str) -> InvariantReport: ...

    async def commit_turn(
        self,
        bundle: CanonicalTurnBundle,
        *,
        fail_after_step: str | None = None,
    ) -> TurnRecord: ...

    async def list_visible_events(self, branch_id: str) -> list[EventRecord]: ...

    async def list_approved_patches(
        self,
        branch_id: str,
        *,
        after_revision: int = 0,
    ) -> list[tuple[int, dict[str, object]]]: ...

    async def save_snapshot(self, snapshot: SnapshotRecord) -> None: ...

    async def load_latest_snapshot(self, branch_id: str) -> SnapshotRecord | None: ...

    async def enqueue_derived_job(self, job: DerivedJobRecord) -> DerivedJobRecord: ...

    async def list_derived_jobs(self, *, status: str | None = None) -> list[DerivedJobRecord]: ...

    async def mark_derived_job(
        self,
        job_id: str,
        *,
        status: str,
        error: str | None = None,
    ) -> None: ...

    async def reconcile_derived_jobs(self) -> int: ...


class UnitOfWork(Protocol):
    worlds: WorldRepository
    playthroughs: PlaythroughRepository
    canonical: CanonicalRepository

    @property
    def retrieval(self) -> MemoryCandidateSource: ...

    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


UowFactory = Callable[[], UnitOfWork]

__all__ = ["CanonicalRepository", "PlaythroughRepository", "UnitOfWork", "UowFactory", "WorldRepository"]
