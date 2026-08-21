"""SQLAlchemy adapter for rebuildable derived artifacts."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.contracts.persistence import DerivedArtifactRecord

from .models import DerivedArtifactModel


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _record(model: DerivedArtifactModel) -> DerivedArtifactRecord:
    return DerivedArtifactRecord(
        id=model.id,
        artifact_type=model.artifact_type,
        playthrough_id=model.playthrough_id,
        branch_id=model.branch_id,
        source_turn_id=model.source_turn_id,
        source_revision=model.source_revision,
        artifact_version=model.artifact_version,
        content_hash=model.content_hash,
        payload=dict(model.payload),
        status=model.status,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


class SqlAlchemyDerivedArtifactRepository:
    """Persist only projections; canonical turn/state rows are never updated."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, artifact: DerivedArtifactRecord) -> DerivedArtifactRecord:
        model = await self._session.scalar(select(DerivedArtifactModel).where(DerivedArtifactModel.id == artifact.id))
        if model is None:
            model = await self._session.scalar(
                select(DerivedArtifactModel).where(
                    DerivedArtifactModel.playthrough_id == artifact.playthrough_id,
                    DerivedArtifactModel.branch_id == artifact.branch_id,
                    DerivedArtifactModel.artifact_type == artifact.artifact_type,
                    DerivedArtifactModel.source_revision == artifact.source_revision,
                    DerivedArtifactModel.artifact_version == artifact.artifact_version,
                )
            )
        values = {
            "id": artifact.id,
            "artifact_type": artifact.artifact_type,
            "playthrough_id": artifact.playthrough_id,
            "branch_id": artifact.branch_id,
            "source_turn_id": artifact.source_turn_id,
            "source_revision": artifact.source_revision,
            "artifact_version": artifact.artifact_version,
            "content_hash": artifact.content_hash,
            "payload": dict(artifact.payload),
            "status": artifact.status,
            "created_at": artifact.created_at,
            "updated_at": artifact.updated_at,
        }
        if model is None:
            self._session.add(DerivedArtifactModel(**values))
        else:
            for key, value in values.items():
                if key != "id":
                    setattr(model, key, value)
        await self._session.flush()
        return artifact

    async def get_latest(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        artifact_type: str,
        source_revision: int | None = None,
        artifact_version: str | None = None,
    ) -> DerivedArtifactRecord | None:
        statement = (
            select(DerivedArtifactModel)
            .where(
                DerivedArtifactModel.playthrough_id == playthrough_id,
                DerivedArtifactModel.branch_id == branch_id,
                DerivedArtifactModel.artifact_type == artifact_type,
            )
            .order_by(DerivedArtifactModel.source_revision.desc(), DerivedArtifactModel.created_at.desc())
        )
        if source_revision is not None:
            statement = statement.where(DerivedArtifactModel.source_revision == source_revision)
        if artifact_version is not None:
            statement = statement.where(DerivedArtifactModel.artifact_version == artifact_version)
        model = await self._session.scalar(statement)
        return None if model is None else _record(model)

    async def list(
        self,
        *,
        playthrough_id: str | None = None,
        branch_id: str | None = None,
        artifact_type: str | None = None,
    ) -> list[DerivedArtifactRecord]:
        statement = select(DerivedArtifactModel).order_by(
            DerivedArtifactModel.source_revision,
            DerivedArtifactModel.created_at,
            DerivedArtifactModel.id,
        )
        if playthrough_id is not None:
            statement = statement.where(DerivedArtifactModel.playthrough_id == playthrough_id)
        if branch_id is not None:
            statement = statement.where(DerivedArtifactModel.branch_id == branch_id)
        if artifact_type is not None:
            statement = statement.where(DerivedArtifactModel.artifact_type == artifact_type)
        return [_record(model) for model in (await self._session.scalars(statement)).all()]


__all__ = ["SqlAlchemyDerivedArtifactRepository"]
