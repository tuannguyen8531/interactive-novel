"""Persistence ports owned by the application layer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from src.application.contracts.persistence import PlaythroughRecord, WorldRecord


class WorldRepository(Protocol):
    async def add(self, world: WorldRecord) -> None: ...

    async def get(self, world_id: str) -> WorldRecord | None: ...


class PlaythroughRepository(Protocol):
    async def add(self, playthrough: PlaythroughRecord) -> None: ...

    async def get(self, playthrough_id: str) -> PlaythroughRecord | None: ...


class UnitOfWork(Protocol):
    worlds: WorldRepository
    playthroughs: PlaythroughRepository

    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


UowFactory = Callable[[], UnitOfWork]

__all__ = ["PlaythroughRepository", "UnitOfWork", "UowFactory", "WorldRepository"]
