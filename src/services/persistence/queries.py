"""SQLAlchemy read projections for application inspection use cases."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.contracts.persistence import CharacterRole
from src.application.contracts.queries import CharacterView, MemoryView, RelationshipView

from .models import (
    BeliefModel,
    CharacterModel,
    CharacterStateModel,
    ObservationModel,
    RelationshipModel,
)
from .visibility import resolve_visible_branch_scope


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    explicit_public = profile.get("public")
    if isinstance(explicit_public, dict):
        return dict(explicit_public)
    return {
        str(key): value
        for key, value in profile.items()
        if str(key) not in {"private", "secrets", "hidden"} and not str(key).startswith("_")
    }


def _character_view(model: CharacterModel, state: CharacterStateModel | None) -> CharacterView:
    return CharacterView(
        id=model.id,
        world_id=model.world_id,
        playthrough_id=model.playthrough_id,
        role=CharacterRole(model.role),
        display_name=model.display_name,
        aliases=tuple(model.aliases),
        public_profile=_public_profile(dict(model.profile)),
        state=None if state is None else dict(state.state),
        last_active_turn_id=None if state is None else state.last_active_turn_id,
        schema_version=model.schema_version,
    )


class SqlAlchemyInspectionRepository:
    """Expose only typed, scope-checked projections to the application layer."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_characters(
        self,
        *,
        playthrough_id: str,
        world_id: str,
        branch_id: str | None = None,
    ) -> list[CharacterView]:
        models = list(
            (
                await self._session.scalars(
                    select(CharacterModel)
                    .where(
                        CharacterModel.world_id == world_id,
                        or_(CharacterModel.playthrough_id == playthrough_id, CharacterModel.playthrough_id.is_(None)),
                    )
                    .order_by(CharacterModel.created_at, CharacterModel.id)
                )
            ).all()
        )
        states = await self._states_for([model.id for model in models], playthrough_id=playthrough_id, branch_id=branch_id)
        return [_character_view(model, states.get(model.id)) for model in models]

    async def get_character_public_profile(
        self,
        *,
        playthrough_id: str,
        world_id: str,
        character_id: str,
        branch_id: str | None = None,
    ) -> CharacterView | None:
        model = await self._session.scalar(select(CharacterModel).where(CharacterModel.id == character_id))
        if model is None or model.world_id != world_id:
            return None
        if model.playthrough_id is not None and model.playthrough_id != playthrough_id:
            return None
        states = await self._states_for([model.id], playthrough_id=playthrough_id, branch_id=branch_id)
        return _character_view(model, states.get(model.id))

    async def inspect_character_memory(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        character_id: str,
        limit: int = 100,
    ) -> list[MemoryView]:
        if limit <= 0:
            raise ValueError("Memory limit must be positive.")
        scope = await resolve_visible_branch_scope(self._session, branch_id)
        if not scope.turn_ids:
            return []
        observations = list(
            (
                await self._session.scalars(
                    select(ObservationModel).where(
                        ObservationModel.playthrough_id == playthrough_id,
                        ObservationModel.branch_id.in_(scope.branch_ids),
                        ObservationModel.turn_id.in_(scope.turn_ids),
                        ObservationModel.observer_id == character_id,
                    )
                )
            ).all()
        )
        beliefs = list(
            (
                await self._session.scalars(
                    select(BeliefModel).where(
                        BeliefModel.playthrough_id == playthrough_id,
                        BeliefModel.branch_id.in_(scope.branch_ids),
                        BeliefModel.turn_id.in_(scope.turn_ids),
                        BeliefModel.believer_id == character_id,
                    )
                )
            ).all()
        )
        items = [
            MemoryView(
                memory_id=f"observation:{model.id}",
                kind="observation",
                owner_id=model.observer_id,
                branch_id=model.branch_id,
                turn_id=model.turn_id,
                world_time=model.world_time,
                payload={
                    "claim_id": model.observed_claim_id,
                    "source_event_id": model.source_event_id,
                    "method": model.method,
                    "distortion": model.distortion,
                    **dict(model.provenance),
                },
                confidence=model.confidence,
                source_id=model.source_event_id,
            )
            for model in observations
        ]
        items.extend(
            MemoryView(
                memory_id=f"belief:{model.id}",
                kind="belief",
                owner_id=model.believer_id,
                branch_id=model.branch_id,
                turn_id=model.turn_id,
                world_time=model.world_time,
                payload={
                    "claim_id": model.claim_id,
                    "stance": model.stance,
                    "branch_scope": model.branch_scope,
                    "source_reliability": model.source_reliability,
                    **dict(model.provenance),
                },
                confidence=model.confidence,
                source_id=model.claim_id,
            )
            for model in beliefs
        )
        items.sort(key=lambda item: (item.world_time, item.memory_id), reverse=True)
        return items[:limit]

    async def inspect_relationships(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        character_id: str | None = None,
    ) -> list[RelationshipView]:
        scope = await resolve_visible_branch_scope(self._session, branch_id)
        statement = select(RelationshipModel).where(
            RelationshipModel.playthrough_id == playthrough_id,
            RelationshipModel.branch_id.in_(scope.branch_ids),
        )
        if character_id is not None:
            statement = statement.where(
                or_(RelationshipModel.source_id == character_id, RelationshipModel.target_id == character_id)
            )
        models = list((await self._session.scalars(statement)).all())
        branch_rank = {value: index for index, value in enumerate(scope.branch_ids)}
        latest: dict[tuple[str, str], RelationshipModel] = {}
        for model in models:
            edge = (model.source_id, model.target_id)
            previous = latest.get(edge)
            if previous is None or branch_rank[model.branch_id] >= branch_rank[previous.branch_id]:
                latest[edge] = model
        records = [
            RelationshipView(
                relationship_id=model.id,
                playthrough_id=model.playthrough_id,
                branch_id=model.branch_id,
                source_id=model.source_id,
                target_id=model.target_id,
                values=_numeric_values(model.values),
                schema_version=model.schema_version,
            )
            for model in latest.values()
        ]
        records.sort(key=lambda item: (item.source_id, item.target_id, item.relationship_id))
        return records

    async def _states_for(
        self,
        character_ids: Iterable[str],
        *,
        playthrough_id: str,
        branch_id: str | None,
    ) -> dict[str, CharacterStateModel]:
        ids = tuple(character_ids)
        if not ids or branch_id is None:
            return {}
        scope = await resolve_visible_branch_scope(self._session, branch_id)
        if not scope.turn_ids:
            return {}
        models = list(
            (
                await self._session.scalars(
                    select(CharacterStateModel).where(
                        CharacterStateModel.character_id.in_(ids),
                        CharacterStateModel.playthrough_id == playthrough_id,
                        CharacterStateModel.branch_id.in_(scope.branch_ids),
                        CharacterStateModel.last_active_turn_id.in_(scope.turn_ids),
                    )
                )
            ).all()
        )
        branch_rank = {value: index for index, value in enumerate(scope.branch_ids)}
        latest: dict[str, CharacterStateModel] = {}
        for model in models:
            previous = latest.get(model.character_id)
            if previous is None or branch_rank[model.branch_id] >= branch_rank[previous.branch_id]:
                latest[model.character_id] = model
        return latest


def _numeric_values(values: dict[str, Any]) -> dict[str, float]:
    return {str(key): float(value) for key, value in values.items() if isinstance(value, (int, float))}


__all__ = ["SqlAlchemyInspectionRepository"]
