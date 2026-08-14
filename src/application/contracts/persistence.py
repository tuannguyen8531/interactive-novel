"""Persistence-neutral records for the Phase 2 application services.

These records deliberately describe only the stable persistence contract. The
full domain entities and invariant-rich value objects belong to Phase 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    """Return an aware UTC timestamp for audit columns."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class WorldRecord:
    """Persistence-neutral representation of a reusable world."""

    id: str
    name: str
    premise: str
    genre: str
    tone: str
    canon_rules: dict[str, Any]
    content_policy: dict[str, Any]
    schema_version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        name: str,
        premise: str = "",
        genre: str = "",
        tone: str = "",
        canon_rules: dict[str, Any] | None = None,
        content_policy: dict[str, Any] | None = None,
        world_id: str | None = None,
    ) -> WorldRecord:
        if not name.strip():
            raise ValueError("World name must not be empty.")
        now = utc_now()
        return cls(
            id=world_id or str(uuid4()),
            name=name,
            premise=premise,
            genre=genre,
            tone=tone,
            canon_rules=dict(canon_rules or {}),
            content_policy=dict(content_policy or {}),
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class PlaythroughRecord:
    """Persistence-neutral representation of a single playthrough."""

    id: str
    world_id: str
    player_character_id: str | None
    root_branch_id: str | None
    provider_config_snapshot: dict[str, Any]
    world_clock_minutes: int
    rng_seed: str
    rng_state: dict[str, Any]
    lifecycle: str = "active"
    schema_version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        world_id: str,
        player_character_id: str | None = None,
        root_branch_id: str | None = None,
        provider_config_snapshot: dict[str, Any] | None = None,
        world_clock_minutes: int = 0,
        rng_seed: str | None = None,
        rng_state: dict[str, Any] | None = None,
        playthrough_id: str | None = None,
    ) -> PlaythroughRecord:
        if world_clock_minutes < 0:
            raise ValueError("World clock cannot be negative.")
        now = utc_now()
        return cls(
            id=playthrough_id or str(uuid4()),
            world_id=world_id,
            player_character_id=player_character_id,
            root_branch_id=root_branch_id,
            provider_config_snapshot=dict(provider_config_snapshot or {}),
            world_clock_minutes=world_clock_minutes,
            rng_seed=rng_seed or str(uuid4()),
            rng_state=dict(rng_state or {}),
            created_at=now,
            updated_at=now,
        )


__all__ = ["PlaythroughRecord", "WorldRecord", "utc_now"]
