"""Persistence ports owned by the application layer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.application.contracts.persistence import (
    BranchRecord,
    CanonicalTurnBundle,
    CharacterRecord,
    DerivedJobRecord,
    EventRecord,
    InvariantReport,
    PlaythroughRecord,
    SnapshotRecord,
    TurnRecord,
    WorldRecord,
)
from src.application.contracts.queries import CharacterView, MemoryView, RelationshipView

from .derived import DerivedArtifactRepository
from .jobs import JobRepository
from .retrieval import RetrievalRepository


class WorldRepository(Protocol):
    async def add(self, world: WorldRecord) -> None: ...

    async def get(self, world_id: str) -> WorldRecord | None: ...

    async def list(self) -> list[WorldRecord]: ...

    async def delete(self, world_id: str) -> bool: ...


class CharacterRepository(Protocol):
    async def add(self, character: CharacterRecord) -> None: ...

    async def get(self, character_id: str) -> CharacterRecord | None: ...

    async def list(self, *, world_id: str, playthrough_id: str | None = None) -> list[CharacterRecord]: ...


class PlaythroughRepository(Protocol):
    async def add(self, playthrough: PlaythroughRecord) -> None: ...

    async def get(self, playthrough_id: str) -> PlaythroughRecord | None: ...

    async def list(self, *, world_id: str | None = None) -> list[PlaythroughRecord]: ...

    async def set_root_branch(self, playthrough_id: str, branch_id: str) -> None: ...

    async def set_active_branch(self, playthrough_id: str, branch_id: str) -> None: ...

    async def set_world_clock(self, playthrough_id: str, world_clock_minutes: int) -> None: ...

    async def update_provider_config_snapshot(self, playthrough_id: str, snapshot: dict[str, object]) -> None: ...


class CanonicalRepository(Protocol):
    """Persistence port for canonical turn, branch and derived boundaries."""

    async def add_branch(self, branch: BranchRecord) -> None: ...

    async def get_branch(self, branch_id: str) -> BranchRecord | None: ...

    async def get_turn(self, turn_id: str) -> TurnRecord | None: ...

    async def get_turn_by_run_id(self, turn_run_id: str) -> TurnRecord | None: ...

    async def list_branches(self, playthrough_id: str) -> list[BranchRecord]: ...

    async def list_turns(self, playthrough_id: str, *, branch_id: str | None = None) -> list[TurnRecord]: ...

    async def list_visible_turns(self, branch_id: str) -> list[TurnRecord]: ...

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


class InspectionRepository(Protocol):
    """Read-only projections used by character, memory and relationship queries."""

    async def list_characters(
        self,
        *,
        playthrough_id: str,
        world_id: str,
        branch_id: str | None = None,
    ) -> list[CharacterView]: ...

    async def get_character_public_profile(
        self,
        *,
        playthrough_id: str,
        world_id: str,
        character_id: str,
        branch_id: str | None = None,
    ) -> CharacterView | None: ...

    async def inspect_character_memory(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        character_id: str,
        limit: int = 100,
    ) -> list[MemoryView]: ...

    async def inspect_relationships(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        character_id: str | None = None,
    ) -> list[RelationshipView]: ...


class UnitOfWork(Protocol):
    worlds: WorldRepository
    characters: CharacterRepository
    playthroughs: PlaythroughRepository
    canonical: CanonicalRepository
    inspection: InspectionRepository
    jobs: JobRepository
    derived: DerivedArtifactRepository

    @property
    def retrieval(self) -> RetrievalRepository: ...

    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


UowFactory = Callable[[], UnitOfWork]

__all__ = [
    "CanonicalRepository",
    "CharacterRepository",
    "InspectionRepository",
    "JobRepository",
    "PlaythroughRepository",
    "UnitOfWork",
    "UowFactory",
    "WorldRepository",
]
