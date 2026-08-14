"""World application use cases."""

from __future__ import annotations

from typing import Any

from src.application.contracts.persistence import WorldRecord
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


__all__ = ["WorldApplicationService"]
