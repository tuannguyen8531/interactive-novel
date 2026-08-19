"""Playthrough application use cases."""

from __future__ import annotations

from typing import Any

from src.application.contracts.persistence import PlaythroughRecord
from src.application.errors import ResourceNotFoundError
from src.application.ports.persistence import UowFactory


class PlaythroughApplicationService:
    """Create and load playthroughs through one application transaction."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def create_playthrough(
        self,
        *,
        world_id: str,
        player_character_id: str | None = None,
        root_branch_id: str | None = None,
        provider_config_snapshot: dict[str, Any] | None = None,
        world_clock_minutes: int = 0,
        rng_seed: str | None = None,
        rng_state: dict[str, Any] | None = None,
    ) -> PlaythroughRecord:
        playthrough = PlaythroughRecord.new(
            world_id=world_id,
            player_character_id=player_character_id,
            root_branch_id=root_branch_id,
            active_branch_id=root_branch_id,
            provider_config_snapshot=provider_config_snapshot,
            world_clock_minutes=world_clock_minutes,
            rng_seed=rng_seed,
            rng_state=rng_state,
        )
        async with self._uow_factory() as uow:
            if await uow.worlds.get(world_id) is None:
                raise ResourceNotFoundError(f"World {world_id} does not exist.")
            await uow.playthroughs.add(playthrough)
            await uow.commit()
        return playthrough

    async def load_playthrough(self, playthrough_id: str) -> PlaythroughRecord | None:
        async with self._uow_factory() as uow:
            return await uow.playthroughs.get(playthrough_id)

    async def get_playthrough(self, playthrough_id: str) -> PlaythroughRecord:
        """Load one playthrough as a required application resource."""
        playthrough = await self.load_playthrough(playthrough_id)
        if playthrough is None:
            raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
        return playthrough

    async def list_playthroughs(self, *, world_id: str | None = None) -> tuple[PlaythroughRecord, ...]:
        """List playthroughs, optionally scoped to one world."""
        async with self._uow_factory() as uow:
            return tuple(await uow.playthroughs.list(world_id=world_id))

    async def update_provider_snapshot(
        self,
        *,
        playthrough_id: str,
        provider_config_snapshot: dict[str, object],
    ) -> PlaythroughRecord:
        """Replace a playthrough's secret-free provider configuration snapshot."""
        async with self._uow_factory() as uow:
            if await uow.playthroughs.get(playthrough_id) is None:
                raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
            await uow.playthroughs.update_provider_config_snapshot(playthrough_id, provider_config_snapshot)
            await uow.commit()
            updated = await uow.playthroughs.get(playthrough_id)
        if updated is None:
            raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
        return updated


__all__ = ["PlaythroughApplicationService"]
