"""Perspective-safe character, memory, relationship and timeline queries."""

from __future__ import annotations

from dataclasses import replace

from src.application.contracts.queries import CharacterView, MemoryView, RelationshipView, TimelineView
from src.application.errors import ResourceNotFoundError
from src.application.ports.persistence import UnitOfWork, UowFactory

from .game_states import GameStateApplicationService


class CharacterQueryApplicationService:
    """Expose read-only projections without returning persistence models."""

    def __init__(
        self,
        uow_factory: UowFactory,
        *,
        game_states: GameStateApplicationService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._game_states = game_states

    async def list_characters(
        self,
        *,
        playthrough_id: str,
        branch_id: str | None = None,
    ) -> tuple[CharacterView, ...]:
        async with self._uow_factory() as uow:
            playthrough = await uow.playthroughs.get(playthrough_id)
            if playthrough is None:
                raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
            branch = await self._scope_branch(
                uow,
                playthrough_id=playthrough_id,
                branch_id=branch_id or playthrough.active_branch_id,
            )
            characters = await uow.inspection.list_characters(
                playthrough_id=playthrough_id,
                world_id=playthrough.world_id,
                branch_id=None if branch is None else branch.id,
            )
            return tuple(replace(item, state=None, last_active_turn_id=None) for item in characters)

    async def get_character_public_profile(
        self,
        *,
        playthrough_id: str,
        character_id: str,
        branch_id: str | None = None,
    ) -> CharacterView:
        async with self._uow_factory() as uow:
            playthrough = await uow.playthroughs.get(playthrough_id)
            if playthrough is None:
                raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
            branch = await self._scope_branch(
                uow,
                playthrough_id=playthrough_id,
                branch_id=branch_id or playthrough.active_branch_id,
            )
            character = await uow.inspection.get_character_public_profile(
                playthrough_id=playthrough_id,
                world_id=playthrough.world_id,
                character_id=character_id,
                branch_id=None if branch is None else branch.id,
            )
            if character is None:
                raise ResourceNotFoundError(f"Character {character_id} does not exist in this playthrough.")
            return replace(character, state=None, last_active_turn_id=None)

    async def inspect_character_memory(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        character_id: str,
        limit: int = 100,
    ) -> tuple[MemoryView, ...]:
        async with self._uow_factory() as uow:
            await self._required_branch(uow, playthrough_id=playthrough_id, branch_id=branch_id)
            return tuple(
                await uow.inspection.inspect_character_memory(
                    playthrough_id=playthrough_id,
                    branch_id=branch_id,
                    character_id=character_id,
                    limit=limit,
                )
            )

    async def inspect_relationships(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        character_id: str | None = None,
    ) -> tuple[RelationshipView, ...]:
        if self._game_states is not None:
            state = await self._game_states.load(playthrough_id=playthrough_id, branch_id=branch_id)
            records = (
                RelationshipView(
                    relationship_id=f"relationship:{source_id}:{target_id}",
                    playthrough_id=playthrough_id,
                    branch_id=branch_id,
                    source_id=source_id,
                    target_id=target_id,
                    values=dict(vector.values),
                )
                for (source_id, target_id), vector in state.relationships.items()
                if character_id is None or character_id in {source_id, target_id}
            )
            return tuple(sorted(records, key=lambda item: (item.source_id, item.target_id)))
        async with self._uow_factory() as uow:
            await self._required_branch(uow, playthrough_id=playthrough_id, branch_id=branch_id)
            return tuple(
                await uow.inspection.inspect_relationships(
                    playthrough_id=playthrough_id,
                    branch_id=branch_id,
                    character_id=character_id,
                )
            )

    async def inspect_timeline(self, *, playthrough_id: str, branch_id: str) -> tuple[TimelineView, ...]:
        async with self._uow_factory() as uow:
            await self._required_branch(uow, playthrough_id=playthrough_id, branch_id=branch_id)
            events = await uow.canonical.list_visible_events(branch_id)
        return tuple(
            TimelineView(
                event_id=event.event_id,
                playthrough_id=event.playthrough_id,
                branch_id=event.branch_id,
                turn_id=event.turn_id,
                event_type=event.event_type,
                world_time=event.world_time,
                location_id=event.location_id,
                actor_ids=event.actor_ids,
                target_ids=event.target_ids,
                witness_ids=event.witness_ids,
                payload=dict(event.payload),
                salience=event.salience,
                emotional_intensity=event.emotional_intensity,
            )
            for event in events
        )

    async def _scope_branch(self, uow: UnitOfWork, *, playthrough_id: str, branch_id: str | None):
        if branch_id is None:
            return None
        return await self._required_branch(uow, playthrough_id=playthrough_id, branch_id=branch_id)

    async def _required_branch(self, uow: UnitOfWork, *, playthrough_id: str, branch_id: str):
        branch = await uow.canonical.get_branch(branch_id)
        if branch is None or branch.playthrough_id != playthrough_id:
            raise ResourceNotFoundError(f"Branch {branch_id} does not belong to playthrough {playthrough_id}.")
        return branch


__all__ = ["CharacterQueryApplicationService"]
