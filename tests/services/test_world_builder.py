from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.application.contracts.ai import AIPromptRole, WorldBriefSuggestion, WorldSeed
from src.application.contracts.providers import ProviderResponse, StructuredResponse
from src.domain.language import StoryLanguage
from src.services.ai.world_builder import ProviderWorldDraftGenerator
from src.services.prompts import PromptRegistry

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ai" / "role_outputs.json"


class _Provider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.request: Any = None

    async def generate_structured(self, request: Any, schema: Any) -> StructuredResponse:
        self.request = request
        response = ProviderResponse(
            provider="fixture",
            model="fixture-model",
            role=request.role,
            physical_call_id=request.physical_call_id,
            text=json.dumps(self.payload),
        )
        return StructuredResponse(response=response, data=schema.validate(self.payload, provider="fixture"))


@pytest.mark.asyncio
async def test_provider_world_builder_renders_versioned_school_romance_prompt() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    provider = _Provider(payload)
    generator = ProviderWorldDraftGenerator(provider)  # type: ignore[arg-type]

    result = await generator.generate_world_draft("A quiet club prepares for a festival.")

    assert isinstance(result, WorldSeed)
    assert result.title == "The Quiet Courtyard"
    assert provider.request.role == AIPromptRole.WORLD_BUILDER
    assert '"template": "school_romance"' in provider.request.user_prompt
    assert '"player_character"' in provider.request.user_prompt
    assert '"opening_scene"' in provider.request.user_prompt
    assert provider.request.metadata["output_schema_version"] == "world-seed"
    assert result.prompt_version == PromptRegistry().get(AIPromptRole.WORLD_BUILDER).semantic_version
    assert result.run_id != payload["run_id"]


@pytest.mark.asyncio
async def test_provider_world_builder_applies_selected_story_template() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    provider = _Provider(payload)
    generator = ProviderWorldDraftGenerator(provider)  # type: ignore[arg-type]

    result = await generator.generate_world_draft("A missing heirloom leaves several suspects.", template_id="mystery")

    assert result.template_id == "mystery"
    assert '"template": "mystery"' in provider.request.user_prompt
    assert "clue-driven" in provider.request.user_prompt


@pytest.mark.asyncio
async def test_provider_world_builder_carries_story_language_into_prompt_and_seed() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    provider = _Provider(payload)
    generator = ProviderWorldDraftGenerator(provider)  # type: ignore[arg-type]

    result = await generator.generate_world_draft(
        "Một câu chuyện tình cảm ở trường học.",
        story_language=StoryLanguage.VIETNAMESE,
    )

    assert result.story_language is StoryLanguage.VIETNAMESE
    assert '"story_language": "vi"' in provider.request.user_prompt
    assert "player-facing story content in natural Vietnamese" in provider.request.user_prompt


@pytest.mark.asyncio
async def test_provider_world_guide_uses_world_builder_route_and_structured_contract() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_guide"]
    provider = _Provider(payload)
    generator = ProviderWorldDraftGenerator(provider)  # type: ignore[arg-type]

    result = await generator.assist_world_prompt(
        "Một câu chuyện tình cảm trong học viện phép thuật.",
        template_id="fantasy_adventure",
        tone="quiet, bittersweet",
        player_gender="female",
        story_language=StoryLanguage.VIETNAMESE,
    )

    assert isinstance(result, WorldBriefSuggestion)
    assert provider.request.role == AIPromptRole.WORLD_BUILDER
    assert provider.request.logical_roles == (AIPromptRole.WORLD_GUIDE,)
    assert provider.request.temperature == 0.5
    assert provider.request.max_output_tokens == 2_000
    assert provider.request.metadata["output_schema_version"] == "world-brief-suggestion"
    assert '"template": "fantasy_adventure"' in provider.request.user_prompt
    assert '"tone": "quiet, bittersweet"' in provider.request.user_prompt
    assert '"story_language": "vi"' in provider.request.user_prompt
    assert '"rating"' not in provider.request.user_prompt
    assert '"violence_ceiling"' not in provider.request.user_prompt
