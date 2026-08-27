"""Character profile/state entities."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .clock import InWorldClock
from .errors import DomainValidationError
from .psychology import PsychologicalState
from .values import MINUTES_PER_YEAR


@dataclass(frozen=True, slots=True)
class CharacterProfile:
    """Stable identity and long-lived traits."""

    character_id: str
    display_name: str
    age_anchor: int
    age_anchor_world_time: int = 0
    aliases: tuple[str, ...] = ()
    gender: str = "unspecified"
    role: str = ""
    background: str = ""
    appearance: str = ""
    voice: str = ""
    traits: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()
    long_term_goals: tuple[str, ...] = ()
    likes: tuple[str, ...] = ()
    dislikes: tuple[str, ...] = ()
    initial_secrets: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.character_id.strip() or not self.display_name.strip():
            raise DomainValidationError("invalid_character_profile", "Character identity cannot be empty.")
        if isinstance(self.age_anchor, bool) or not isinstance(self.age_anchor, int) or self.age_anchor < 0:
            raise DomainValidationError("invalid_character_age", "Character age anchor must be non-negative.")
        if (
            isinstance(self.age_anchor_world_time, bool)
            or not isinstance(self.age_anchor_world_time, int)
            or self.age_anchor_world_time < 0
        ):
            raise DomainValidationError("invalid_world_time", "Age anchor world time must be non-negative.")

    def age_at(self, world_time: int | InWorldClock) -> int:
        """Calculate age at scene time without mutating historical facts."""
        minutes = world_time.world_time if isinstance(world_time, InWorldClock) else world_time
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0:
            raise DomainValidationError("invalid_world_time", "World time must be a non-negative integer.")
        elapsed_years = (minutes - self.age_anchor_world_time) // MINUTES_PER_YEAR
        return max(0, self.age_anchor + elapsed_years)

    @property
    def id(self) -> str:
        return self.character_id


@dataclass(frozen=True, slots=True)
class CharacterState:
    """Changing state kept separate from the stable character profile."""

    location_id: str | None = None
    physical_condition: str = "healthy"
    psychology: PsychologicalState = field(default_factory=PsychologicalState)
    short_term_goals: tuple[str, ...] = ()
    attention_target_id: str | None = None
    inventory_ids: tuple[str, ...] = ()
    last_active_world_time: int = 0

    def __post_init__(self) -> None:
        if self.last_active_world_time < 0:
            raise DomainValidationError("invalid_world_time", "Last active world time cannot be negative.")
        if not self.physical_condition.strip():
            raise DomainValidationError("invalid_character_state", "Physical condition cannot be empty.")
        object.__setattr__(self, "short_term_goals", tuple(self.short_term_goals))
        object.__setattr__(self, "inventory_ids", tuple(self.inventory_ids))


@dataclass(frozen=True, slots=True)
class Character:
    """Profile plus mutable-by-replacement state."""

    profile: CharacterProfile
    state: CharacterState = field(default_factory=CharacterState)

    @property
    def character_id(self) -> str:
        return self.profile.character_id

    def with_state(self, **changes: object) -> Character:
        return replace(self, state=replace(self.state, **changes))


__all__ = ["Character", "CharacterProfile", "CharacterState"]
