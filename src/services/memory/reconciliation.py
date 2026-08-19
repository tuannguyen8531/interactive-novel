"""Freshness and canonical fallback rules for derived artifacts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from src.application.contracts.persistence import DerivedArtifactRecord

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class DerivedResolution[T]:
    """A read result that makes fallback observable to tests and telemetry."""

    value: T
    used_fallback: bool
    reason: str


class DerivedArtifactResolver:
    """Never let a missing/stale projection block a canonical read."""

    def resolve(
        self,
        artifact: DerivedArtifactRecord | None,
        *,
        source_revision: int,
        fallback: Callable[[], T],
        artifact_version: str | None = None,
    ) -> DerivedResolution[dict[str, object] | T]:
        if artifact is not None and artifact.is_fresh_for(source_revision, artifact_version=artifact_version):
            return DerivedResolution(value=artifact.payload, used_fallback=False, reason="fresh")
        reason = "missing" if artifact is None else "stale"
        return DerivedResolution(value=fallback(), used_fallback=True, reason=reason)


__all__ = ["DerivedArtifactResolver", "DerivedResolution"]
