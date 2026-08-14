"""Small immutable value objects shared by the domain model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import DomainValidationError

MINUTES_PER_DAY = 24 * 60
MINUTES_PER_YEAR = 365 * MINUTES_PER_DAY


def clamp(value: float, lower: float, upper: float) -> float:
    """Return *value* constrained to an inclusive interval."""
    if lower > upper:
        raise DomainValidationError("invalid_bounds", "Lower bound cannot exceed upper bound.")
    return max(lower, min(upper, value))


def _require_non_negative_minutes(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainValidationError("invalid_world_time", f"{field_name} must be a non-negative integer.")


@dataclass(frozen=True, slots=True)
class TimeRange:
    """Inclusive start, optionally open-ended end, in world-clock minutes."""

    start: int
    end: int | None = None

    def __post_init__(self) -> None:
        _require_non_negative_minutes(self.start, "start")
        if self.end is not None:
            _require_non_negative_minutes(self.end, "end")
            if self.end < self.start:
                raise DomainValidationError("invalid_time_range", "Time range end cannot precede start.")

    def contains(self, world_time: int) -> bool:
        _require_non_negative_minutes(world_time, "world_time")
        return self.start <= world_time and (self.end is None or world_time <= self.end)

    def is_future_at(self, world_time: int) -> bool:
        _require_non_negative_minutes(world_time, "world_time")
        return self.start > world_time

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TimeRange:
        return cls(start=int(value.get("start", 0)), end=None if value.get("end") is None else int(value["end"]))


@dataclass(frozen=True, slots=True)
class Provenance:
    """Trace metadata required for authoritative state changes."""

    source_type: str
    source_id: str
    turn_id: str | None = None
    run_id: str | None = None
    prompt_version: str | None = None
    model_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_type.strip() or not self.source_id.strip():
            raise DomainValidationError("invalid_provenance", "Provenance requires source type and source ID.")
        object.__setattr__(self, "model_metadata", dict(self.model_metadata))


__all__ = [
    "MINUTES_PER_DAY",
    "MINUTES_PER_YEAR",
    "Provenance",
    "TimeRange",
    "clamp",
]
