"""Application port for discardable derived artifacts."""

from __future__ import annotations

from typing import Protocol

from src.application.contracts.persistence import DerivedArtifactRecord


class DerivedArtifactRepository(Protocol):
    """Store derived projections without granting them canonical authority."""

    async def save(self, artifact: DerivedArtifactRecord) -> DerivedArtifactRecord: ...

    async def get_latest(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        artifact_type: str,
        source_revision: int | None = None,
        artifact_version: str | None = None,
    ) -> DerivedArtifactRecord | None: ...

    async def list(
        self,
        *,
        playthrough_id: str | None = None,
        branch_id: str | None = None,
        artifact_type: str | None = None,
    ) -> list[DerivedArtifactRecord]: ...


__all__ = ["DerivedArtifactRepository"]
