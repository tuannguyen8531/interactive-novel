"""SQLAlchemy adapters for the application persistence ports."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.contracts.persistence import CharacterRecord, PlaythroughRecord, WorldRecord

from .models import (
    BeliefEvidenceModel,
    BeliefModel,
    BranchModel,
    CanonFactModel,
    CharacterModel,
    CharacterStateModel,
    ClaimLinkModel,
    DerivedArtifactModel,
    DerivedJobModel,
    EmotionalTensionModel,
    EventModel,
    JobModel,
    KnowledgeClaimModel,
    MemoryEmbeddingModel,
    NarrativeHookModel,
    NarrativeThreadModel,
    ObservationModel,
    OutboxEventModel,
    PlaythroughModel,
    RelationshipChangeModel,
    RelationshipModel,
    RetrievalTraceModel,
    SnapshotModel,
    TurnModel,
    WorldModel,
)


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
        rng_state=deepcopy(model.rng_state),
        active_branch_id=model.active_branch_id,
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

    async def list(self) -> list[WorldRecord]:
        result = await self._session.scalars(select(WorldModel).order_by(WorldModel.created_at, WorldModel.id))
        return [_world_record(model) for model in result.all()]

    async def delete(self, world_id: str) -> bool:
        """Delete one complete world aggregate without leaving audit rows behind."""
        exists = await self._session.scalar(select(WorldModel.id).where(WorldModel.id == world_id))
        if exists is None:
            return False

        playthrough_ids = tuple(
            (await self._session.scalars(select(PlaythroughModel.id).where(PlaythroughModel.world_id == world_id))).all()
        )
        if playthrough_ids:
            # Break the canonical history's intentional cycles, then delete
            # children before parents. A direct SQLite cascade can recurse around
            # playthrough -> branch -> turn -> branch indefinitely.
            await self._session.execute(
                update(PlaythroughModel)
                .where(PlaythroughModel.id.in_(playthrough_ids))
                .values(player_character_id=None, root_branch_id=None, active_branch_id=None)
            )
            await self._session.execute(
                update(BranchModel)
                .where(BranchModel.playthrough_id.in_(playthrough_ids))
                .values(parent_branch_id=None, fork_turn_id=None, head_turn_id=None)
            )
            await self._session.execute(
                update(TurnModel).where(TurnModel.playthrough_id.in_(playthrough_ids)).values(parent_turn_id=None)
            )

            leaf_models = (
                BeliefEvidenceModel,
                RelationshipChangeModel,
                ClaimLinkModel,
                ObservationModel,
                CanonFactModel,
                BeliefModel,
                CharacterStateModel,
                EmotionalTensionModel,
                NarrativeHookModel,
                NarrativeThreadModel,
                SnapshotModel,
                DerivedArtifactModel,
                MemoryEmbeddingModel,
                DerivedJobModel,
                OutboxEventModel,
                JobModel,
                RetrievalTraceModel,
            )
            for model in leaf_models:
                await self._session.execute(delete(model).where(model.playthrough_id.in_(playthrough_ids)))

            await self._session.execute(delete(RelationshipModel).where(RelationshipModel.playthrough_id.in_(playthrough_ids)))
            await self._session.execute(
                delete(KnowledgeClaimModel).where(KnowledgeClaimModel.playthrough_id.in_(playthrough_ids))
            )
            await self._session.execute(delete(EventModel).where(EventModel.playthrough_id.in_(playthrough_ids)))
            await self._session.execute(delete(TurnModel).where(TurnModel.playthrough_id.in_(playthrough_ids)))
            await self._session.execute(delete(BranchModel).where(BranchModel.playthrough_id.in_(playthrough_ids)))
            await self._session.execute(delete(PlaythroughModel).where(PlaythroughModel.id.in_(playthrough_ids)))

        # Characters created during world review are world-scoped rather than
        # playthrough-scoped, so they need an explicit aggregate cleanup.
        await self._session.execute(delete(CharacterModel).where(CharacterModel.world_id == world_id))
        result = await self._session.execute(delete(WorldModel).where(WorldModel.id == world_id))
        await self._session.flush()
        return getattr(result, "rowcount", None) == 1


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
                rng_state=deepcopy(playthrough.rng_state),
                active_branch_id=playthrough.active_branch_id,
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

    async def list(self, *, world_id: str | None = None) -> list[PlaythroughRecord]:
        statement = select(PlaythroughModel).order_by(PlaythroughModel.created_at, PlaythroughModel.id)
        if world_id is not None:
            statement = statement.where(PlaythroughModel.world_id == world_id)
        result = await self._session.scalars(statement)
        return [_playthrough_record(model) for model in result.all()]

    async def set_root_branch(self, playthrough_id: str, branch_id: str) -> None:
        result = await self._session.execute(
            update(PlaythroughModel)
            .where(PlaythroughModel.id == playthrough_id)
            .values(root_branch_id=branch_id, active_branch_id=branch_id, updated_at=datetime.now(UTC))
        )
        if getattr(result, "rowcount", None) != 1:
            raise ValueError(f"Playthrough {playthrough_id} does not exist.")
        await self._session.flush()

    async def set_active_branch(self, playthrough_id: str, branch_id: str) -> None:
        result = await self._session.execute(
            update(PlaythroughModel)
            .where(PlaythroughModel.id == playthrough_id)
            .values(active_branch_id=branch_id, updated_at=datetime.now(UTC))
        )
        if getattr(result, "rowcount", None) != 1:
            raise ValueError(f"Playthrough {playthrough_id} does not exist.")
        await self._session.flush()

    async def set_world_clock(self, playthrough_id: str, world_clock_minutes: int) -> None:
        if world_clock_minutes < 0:
            raise ValueError("World clock cannot be negative.")
        result = await self._session.execute(
            update(PlaythroughModel)
            .where(PlaythroughModel.id == playthrough_id)
            .values(world_clock_minutes=world_clock_minutes, updated_at=datetime.now(UTC))
        )
        if getattr(result, "rowcount", None) != 1:
            raise ValueError(f"Playthrough {playthrough_id} does not exist.")
        await self._session.flush()

    async def update_provider_config_snapshot(self, playthrough_id: str, snapshot: dict[str, object]) -> None:
        result = await self._session.execute(
            update(PlaythroughModel)
            .where(PlaythroughModel.id == playthrough_id)
            .values(provider_config_snapshot=dict(snapshot), updated_at=datetime.now(UTC))
        )
        if getattr(result, "rowcount", None) != 1:
            raise ValueError(f"Playthrough {playthrough_id} does not exist.")
        await self._session.flush()


class SqlAlchemyCharacterRepository:
    """World/profile repository for confirmed world-builder characters."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, character: CharacterRecord) -> None:
        self._session.add(
            CharacterModel(
                id=character.id,
                world_id=character.world_id,
                playthrough_id=character.playthrough_id,
                display_name=character.display_name,
                aliases=list(character.aliases),
                profile=dict(character.profile),
                schema_version=character.schema_version,
                created_at=character.created_at,
                updated_at=character.updated_at,
            )
        )
        await self._session.flush()

    async def get(self, character_id: str) -> CharacterRecord | None:
        model = await self._session.scalar(select(CharacterModel).where(CharacterModel.id == character_id))
        return None if model is None else _character_record(model)

    async def list(self, *, world_id: str, playthrough_id: str | None = None) -> list[CharacterRecord]:
        statement = select(CharacterModel).where(CharacterModel.world_id == world_id)
        if playthrough_id is not None:
            statement = statement.where(
                or_(CharacterModel.playthrough_id == playthrough_id, CharacterModel.playthrough_id.is_(None))
            )
        statement = statement.order_by(CharacterModel.created_at, CharacterModel.id)
        return [_character_record(model) for model in (await self._session.scalars(statement)).all()]


def _character_record(model: CharacterModel) -> CharacterRecord:
    return CharacterRecord(
        id=model.id,
        world_id=model.world_id,
        playthrough_id=model.playthrough_id,
        display_name=model.display_name,
        aliases=tuple(model.aliases),
        profile=dict(model.profile),
        schema_version=model.schema_version,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


__all__ = ["SqlAlchemyCharacterRepository", "SqlAlchemyPlaythroughRepository", "SqlAlchemyWorldRepository"]
