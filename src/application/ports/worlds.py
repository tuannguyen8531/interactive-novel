"""Port for the provider-backed world draft generator."""

from __future__ import annotations

from typing import Literal, Protocol

from src.application.contracts.ai import WorldBriefSuggestion, WorldSeed
from src.domain.language import StoryLanguage


class WorldDraftGenerator(Protocol):
    async def generate_world_draft(self, prompt: str) -> WorldSeed: ...

    async def assist_world_prompt(
        self,
        prompt: str,
        *,
        template_id: str = "school_romance",
        tone: str | None = None,
        player_gender: Literal["male", "female"] = "male",
        story_language: StoryLanguage | str = StoryLanguage.ENGLISH,
    ) -> WorldBriefSuggestion: ...


__all__ = ["WorldDraftGenerator"]
