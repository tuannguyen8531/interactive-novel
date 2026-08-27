"""Provider-neutral story template definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.content import Rating, ViolenceCeiling


@dataclass(frozen=True, slots=True)
class StoryTemplateDefaults:
    """Typed builder defaults that users may override before generation."""

    tone: str = "warm, reflective"
    rating: Rating = Rating.TEEN_14_PLUS
    violence_ceiling: ViolenceCeiling = ViolenceCeiling.NONE

    def __post_init__(self) -> None:
        if not self.tone.strip():
            raise ValueError("Story template default tone cannot be empty.")
        object.__setattr__(self, "tone", self.tone.strip())
        object.__setattr__(self, "rating", Rating(self.rating))
        object.__setattr__(self, "violence_ceiling", ViolenceCeiling(self.violence_ceiling))

    def as_dict(self) -> dict[str, str]:
        return {
            "tone": self.tone,
            "rating": self.rating.value,
            "violence_ceiling": self.violence_ceiling.value,
        }


@dataclass(frozen=True, slots=True)
class NarrativeProfile:
    """Persistent creative priorities shared by every runtime role."""

    primary_focus: str = "romance"
    romance_priority: str = "high"
    relationship_pacing: str = "earned_progression"

    def __post_init__(self) -> None:
        for name in ("primary_focus", "romance_priority", "relationship_pacing"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"Narrative profile field {name!r} cannot be empty.")
            object.__setattr__(self, name, value)

    def as_dict(self) -> dict[str, str]:
        return {
            "primary_focus": self.primary_focus,
            "romance_priority": self.romance_priority,
            "relationship_pacing": self.relationship_pacing,
        }


@dataclass(frozen=True, slots=True)
class StoryTemplate:
    """A versioned story shape selected by the World Builder."""

    id: str
    name: str
    description: str
    genre: str
    prompt_instructions: str
    defaults: StoryTemplateDefaults
    narrative_profile: NarrativeProfile
    opening_guidance: tuple[str, ...]
    version: str

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "genre": self.genre,
            "prompt_instructions": self.prompt_instructions,
            "defaults": self.defaults.as_dict(),
            "narrative_profile": self.narrative_profile.as_dict(),
            "opening_guidance": list(self.opening_guidance),
            "version": self.version,
        }


__all__ = ["NarrativeProfile", "StoryTemplate", "StoryTemplateDefaults"]
