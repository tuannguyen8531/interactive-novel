"""Deterministic in-world clock primitives."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import DomainValidationError
from .values import TimeRange


@dataclass(frozen=True, slots=True)
class ClockInterval:
    """The time interval occupied by one accepted operation or turn."""

    start: int
    duration_minutes: int

    def __post_init__(self) -> None:
        if isinstance(self.start, bool) or not isinstance(self.start, int) or self.start < 0:
            raise DomainValidationError("invalid_world_time", "Clock interval start must be non-negative.")
        if isinstance(self.duration_minutes, bool) or not isinstance(self.duration_minutes, int) or self.duration_minutes < 0:
            raise DomainValidationError("invalid_duration", "Clock interval duration must be non-negative.")

    @property
    def end(self) -> int:
        return self.start + self.duration_minutes

    @property
    def time_range(self) -> TimeRange:
        return TimeRange(self.start, self.end)


@dataclass(frozen=True, slots=True)
class InWorldClock:
    """Integer minutes from the world's epoch; it never moves backwards."""

    minutes: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.minutes, bool) or not isinstance(self.minutes, int) or self.minutes < 0:
            raise DomainValidationError("invalid_world_time", "World clock must be a non-negative integer.")

    @property
    def world_time(self) -> int:
        return self.minutes

    @property
    def current_minutes(self) -> int:
        return self.minutes

    def interval(self, duration_minutes: int) -> ClockInterval:
        if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes < 0:
            raise DomainValidationError("invalid_duration", "Duration must be a non-negative integer.")
        return ClockInterval(self.minutes, duration_minutes)

    def advance(self, duration_minutes: int) -> InWorldClock:
        interval = self.interval(duration_minutes)
        return InWorldClock(interval.end)


@dataclass(frozen=True, slots=True)
class ClockPolicy:
    """Guard limits for planner-proposed clock movement."""

    max_turn_duration_minutes: int = 24 * 60
    default_action_duration_minutes: int = 1
    meta_action_duration_minutes: int = 0

    def __post_init__(self) -> None:
        for name in (
            "max_turn_duration_minutes",
            "default_action_duration_minutes",
            "meta_action_duration_minutes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DomainValidationError("invalid_clock_policy", f"{name} must be non-negative.")
        if self.default_action_duration_minutes > self.max_turn_duration_minutes:
            raise DomainValidationError("invalid_clock_policy", "Default action duration exceeds the clock limit.")


__all__ = ["ClockInterval", "ClockPolicy", "InWorldClock"]
