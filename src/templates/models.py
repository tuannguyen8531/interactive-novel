"""Provider-neutral story template definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StoryTemplate:
    """A versioned story shape selected by the World Builder."""

    id: str
    name: str
    description: str
    genre: str
    default_tone: str
    prompt_instructions: str
    default_presets: dict[str, Any]
    opening_guidance: tuple[str, ...]
    version: str

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "genre": self.genre,
            "default_tone": self.default_tone,
            "default_presets": dict(self.default_presets),
            "opening_guidance": list(self.opening_guidance),
            "version": self.version,
        }
