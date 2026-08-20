"""World application use cases."""

from __future__ import annotations

from typing import Any

from src.application.contracts.persistence import WorldRecord
from src.application.errors import ResourceNotFoundError
from src.application.ports.persistence import UowFactory


class WorldApplicationService:
    """Create and load worlds through one application-owned transaction."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def create_world(
        self,
        *,
        name: str,
        premise: str = "",
        genre: str = "",
        tone: str = "",
        canon_rules: dict[str, Any] | None = None,
        content_policy: dict[str, Any] | None = None,
    ) -> WorldRecord:
        world = WorldRecord.new(
            name=name,
            premise=premise,
            genre=genre,
            tone=tone,
            canon_rules=canon_rules,
            content_policy=content_policy,
        )
        async with self._uow_factory() as uow:
            await uow.worlds.add(world)
            await uow.commit()
        return world

    async def load_world(self, world_id: str) -> WorldRecord | None:
        async with self._uow_factory() as uow:
            return await uow.worlds.get(world_id)

    async def get_world(self, world_id: str) -> WorldRecord:
        """Load one world as a required resource for command use cases."""
        world = await self.load_world(world_id)
        if world is None:
            raise ResourceNotFoundError(f"World {world_id} does not exist.")
        return world

    async def list_worlds(self) -> tuple[WorldRecord, ...]:
        """List reusable worlds in stable creation order."""
        async with self._uow_factory() as uow:
            return tuple(await uow.worlds.list())

    async def delete_world(self, world_id: str) -> None:
        """Delete a world and every playthrough-scoped resource it owns."""
        async with self._uow_factory() as uow:
            if not await uow.worlds.delete(world_id):
                raise ResourceNotFoundError(f"World {world_id} does not exist.")
            await uow.commit()


__all__ = ["WorldApplicationService"]
