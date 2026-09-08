"""Derived, human-readable story time for AI context; never canonical state."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict

from src.domain.clock import InWorldClock


class StoryTimeContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    world_time: int
    day: int
    time_24h: str
    period: Literal["night", "morning", "afternoon", "evening"]

    @classmethod
    def from_minutes(cls, minutes: int) -> Self:
        clock = InWorldClock(minutes)
        day_index, minute_of_day = divmod(clock.minutes, 1440)
        hour, minute = divmod(minute_of_day, 60)
        period = "night" if hour < 6 or hour >= 22 else "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        return cls(world_time=minutes, day=day_index + 1, time_24h=f"{hour:02d}:{minute:02d}", period=period)


class TurnClockContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    current: StoryTimeContext
    approved_end: StoryTimeContext | None = None
    approved_duration_minutes: int | None = None
