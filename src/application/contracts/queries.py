"""Typed read models returned by application query use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CharacterView:
    """Public character data plus the scoped current state, when available."""

    id: str
    world_id: str
    playthrough_id: str | None
    display_name: str
    aliases: tuple[str, ...]
    public_profile: dict[str, Any]
    state: dict[str, Any] | None = None
    last_active_turn_id: str | None = None
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class MemoryView:
    """A perspective-scoped observation or belief returned for inspection."""

    memory_id: str
    kind: str
    owner_id: str
    branch_id: str
    turn_id: str
    world_time: int
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    source_id: str | None = None


@dataclass(frozen=True, slots=True)
class RelationshipView:
    """One directed relationship edge in a playthrough branch."""

    relationship_id: str
    playthrough_id: str
    branch_id: str
    source_id: str
    target_id: str
    values: dict[str, float]
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class TimelineView:
    """Stable, API-neutral projection of a canonical event."""

    event_id: str
    playthrough_id: str
    branch_id: str
    turn_id: str
    event_type: str
    world_time: int
    location_id: str | None
    actor_ids: tuple[str, ...]
    target_ids: tuple[str, ...]
    witness_ids: tuple[str, ...]
    payload: dict[str, Any]
    salience: float
    emotional_intensity: float


__all__ = ["CharacterView", "MemoryView", "RelationshipView", "TimelineView"]
