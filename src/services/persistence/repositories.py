"""SQLAlchemy adapters for the application persistence ports."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.contracts.persistence import PlaythroughRecord, WorldRecord

from .models import PlaythroughModel, WorldModel


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _world_record(model: WorldModel) -> WorldRecord:
    return WorldRecord(
        id=model.id,
        name=model.name,
        premise=model.premise,
        genre=model.genre,
        tone=model.tone,
        canon_rules=dict(model.canon_rules),
        content_policy=dict(model.content_policy),
        schema_version=model.schema_version,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _playthrough_record(model: PlaythroughModel) -> PlaythroughRecord:
    return PlaythroughRecord(
        id=model.id,
        world_id=model.world_id,
        player_character_id=model.player_character_id,
        root_branch_id=model.root_branch_id,
        provider_config_snapshot=dict(model.provider_config_snapshot),
        world_clock_minutes=model.world_clock_minutes,
        rng_seed=model.rng_seed,
        rng_state=dict(model.rng_state),
        lifecycle=model.lifecycle,
        schema_version=model.schema_version,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


class SqlAlchemyWorldRepository:
    """World repository backed by the current Unit of Work session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, world: WorldRecord) -> None:
        self._session.add(
            WorldModel(
                id=world.id,
                name=world.name,
                premise=world.premise,
                genre=world.genre,
                tone=world.tone,
                canon_rules=dict(world.canon_rules),
                content_policy=dict(world.content_policy),
                schema_version=world.schema_version,
                created_at=world.created_at,
                updated_at=world.updated_at,
            )
        )
        await self._session.flush()

    async def get(self, world_id: str) -> WorldRecord | None:
        result = await self._session.execute(select(WorldModel).where(WorldModel.id == world_id))
        model = result.scalar_one_or_none()
        return None if model is None else _world_record(model)


class SqlAlchemyPlaythroughRepository:
    """Playthrough repository backed by the current Unit of Work session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, playthrough: PlaythroughRecord) -> None:
        self._session.add(
            PlaythroughModel(
                id=playthrough.id,
                world_id=playthrough.world_id,
                player_character_id=playthrough.player_character_id,
                root_branch_id=playthrough.root_branch_id,
                provider_config_snapshot=dict(playthrough.provider_config_snapshot),
                world_clock_minutes=playthrough.world_clock_minutes,
                rng_seed=playthrough.rng_seed,
                rng_state=dict(playthrough.rng_state),
                lifecycle=playthrough.lifecycle,
                schema_version=playthrough.schema_version,
                created_at=playthrough.created_at,
                updated_at=playthrough.updated_at,
            )
        )
        await self._session.flush()

    async def get(self, playthrough_id: str) -> PlaythroughRecord | None:
        result = await self._session.execute(select(PlaythroughModel).where(PlaythroughModel.id == playthrough_id))
        model = result.scalar_one_or_none()
        return None if model is None else _playthrough_record(model)


__all__ = ["SqlAlchemyPlaythroughRepository", "SqlAlchemyWorldRepository"]
