"""Small derived-artifact adapter for unit tests and local orchestration."""

from __future__ import annotations

from src.application.contracts.persistence import DerivedArtifactRecord


class InMemoryDerivedArtifactRepository:
    """A deterministic adapter with the same freshness semantics as SQLite."""

    def __init__(self) -> None:
        self.artifacts: dict[tuple[str, str, str, int, str], DerivedArtifactRecord] = {}

    async def save(self, artifact: DerivedArtifactRecord) -> DerivedArtifactRecord:
        key = (
            artifact.playthrough_id,
            artifact.branch_id,
            artifact.artifact_type,
            artifact.source_revision,
            artifact.artifact_version,
        )
        self.artifacts[key] = artifact
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
        records = [
            artifact
            for artifact in self.artifacts.values()
            if artifact.playthrough_id == playthrough_id
            and artifact.branch_id == branch_id
            and artifact.artifact_type == artifact_type
            and (source_revision is None or artifact.source_revision == source_revision)
            and (artifact_version is None or artifact.artifact_version == artifact_version)
        ]
        return max(records, key=lambda item: (item.source_revision, item.created_at), default=None)

    async def list(
        self,
        *,
        playthrough_id: str | None = None,
        branch_id: str | None = None,
        artifact_type: str | None = None,
    ) -> list[DerivedArtifactRecord]:
        return sorted(
            (
                artifact
                for artifact in self.artifacts.values()
                if (playthrough_id is None or artifact.playthrough_id == playthrough_id)
                and (branch_id is None or artifact.branch_id == branch_id)
                and (artifact_type is None or artifact.artifact_type == artifact_type)
            ),
            key=lambda item: (item.source_revision, item.id),
        )


__all__ = ["InMemoryDerivedArtifactRepository"]
