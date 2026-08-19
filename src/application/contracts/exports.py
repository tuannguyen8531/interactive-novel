"""Serializable export contract for one complete playthrough."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from src.application.contracts.persistence import (
    BranchRecord,
    DerivedJobRecord,
    EventRecord,
    PlaythroughRecord,
    RelationshipRecord,
    TurnRecord,
    WorldRecord,
)
from src.application.contracts.queries import CharacterView


@dataclass(frozen=True, slots=True)
class PlaythroughExport:
    """Canonical and inspectable data needed to restore or review a run."""

    format_version: str
    exported_at: datetime
    world: WorldRecord
    playthrough: PlaythroughRecord
    branches: tuple[BranchRecord, ...] = ()
    turns: tuple[TurnRecord, ...] = ()
    characters: tuple[CharacterView, ...] = ()
    events: tuple[EventRecord, ...] = ()
    relationships: tuple[RelationshipRecord, ...] = ()
    derived_jobs: tuple[DerivedJobRecord, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Convert records to JSON-compatible primitive values."""
        return _json_safe(asdict(self))


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


__all__ = ["PlaythroughExport"]
