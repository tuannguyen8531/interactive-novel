"""Story template registry and immutable template definitions."""

from .models import NarrativeProfile, StoryTemplate, StoryTemplateDefaults
from .registry import StoryTemplateRegistry, StoryTemplateRegistryError

__all__ = [
    "NarrativeProfile",
    "StoryTemplate",
    "StoryTemplateDefaults",
    "StoryTemplateRegistry",
    "StoryTemplateRegistryError",
]
