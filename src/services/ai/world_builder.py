"""Provider adapter for the transient AI World Builder draft."""

from __future__ import annotations

import json
from typing import Literal
from uuid import uuid4

from src.application.contracts.ai import AIPromptRole, RatingValue, ViolenceCeilingValue, WorldSeed
from src.application.contracts.providers import ProviderRequest
from src.application.ports.providers import ProviderGateway
from src.domain.language import StoryLanguage
from src.services.ai.contracts import AIContractRegistry
from src.services.prompts import PromptRegistry
from src.templates import StoryTemplateRegistry


class ProviderWorldDraftGenerator:
    """Turn a natural-language request into a validated, non-persistent WorldSeed."""

    def __init__(
        self,
        provider: ProviderGateway,
        *,
        prompts: PromptRegistry | None = None,
        contracts: AIContractRegistry | None = None,
        templates: StoryTemplateRegistry | None = None,
    ) -> None:
        self._provider = provider
        self._prompts = prompts or PromptRegistry()
        self._contracts = contracts or AIContractRegistry()
        self._templates = templates or StoryTemplateRegistry()

    async def generate_world_draft(
        self,
        prompt: str,
        *,
        template_id: str = "school_romance",
        tone: str | None = None,
        rating: RatingValue | str | None = None,
        violence_ceiling: ViolenceCeilingValue | str | None = None,
        player_gender: Literal["male", "female"] = "male",
        story_language: StoryLanguage | str = StoryLanguage.ENGLISH,
    ) -> WorldSeed:
        definition = self._prompts.get(AIPromptRole.WORLD_BUILDER)
        template = self._templates.get(template_id)
        effective_tone = tone.strip() if tone is not None else template.defaults.tone
        effective_rating = RatingValue(rating or template.defaults.rating.value)
        effective_ceiling = ViolenceCeilingValue(violence_ceiling or template.defaults.violence_ceiling.value)
        effective_language = StoryLanguage(story_language)
        adult_explicit_opt_in = effective_rating == RatingValue.ADULT_18_PLUS
        run_id = str(uuid4())
        physical_call_id = str(uuid4())
        input_envelope = {
            "schema_version": "world-builder-input",
            "role": AIPromptRole.WORLD_BUILDER.value,
            "run_id": run_id,
            "template": template.id,
            "prompt": prompt.strip(),
            "story_language": effective_language.value,
            "language_instruction": _language_instruction(effective_language),
            "template_instructions": template.prompt_instructions,
            "presets": {
                "tone": effective_tone,
                "rating": effective_rating.value,
                "violence_ceiling": effective_ceiling.value,
                "adult_explicit_opt_in": adult_explicit_opt_in,
                "player_gender": player_gender,
                "allowed_character_genders": ["male", "female"],
            },
            "narrative_profile": template.narrative_profile.as_dict(),
            "opening_guidance": list(template.opening_guidance),
        }
        request = ProviderRequest(
            system_prompt=(
                "You are the local-first World Builder. Return only a strict JSON object; "
                "the result is a draft and has no persistence authority. "
                f"{_language_instruction(effective_language)}"
            ),
            user_prompt=definition.render(
                {
                    "input_json": json.dumps(input_envelope, ensure_ascii=False, sort_keys=True),
                }
            ),
            role=AIPromptRole.WORLD_BUILDER,
            physical_call_id=physical_call_id,
            logical_roles=(AIPromptRole.WORLD_BUILDER,),
            temperature=0.4,
            max_output_tokens=16_000,
            metadata={
                "prompt_version": definition.semantic_version,
                "output_schema_version": definition.output_schema_version,
                "template_hash": definition.template_hash,
                "story_language": effective_language.value,
            },
        )
        response = await self._provider.generate_structured(
            request,
            self._contracts.structured_schema(
                AIPromptRole.WORLD_BUILDER,
                authoritative_metadata={
                    "schema_version": definition.output_schema_version,
                    "role": AIPromptRole.WORLD_BUILDER.value,
                    "run_id": run_id,
                    "prompt_version": definition.semantic_version,
                    "physical_call_id": physical_call_id,
                },
            ),
        )
        result = (
            response.data
            if isinstance(response.data, WorldSeed)
            else self._contracts.parse(AIPromptRole.WORLD_BUILDER, response.data)
        )
        if not isinstance(result, WorldSeed):
            raise TypeError("World builder contract returned a non-WorldSeed response.")
        boundaries = result.content_boundaries.model_copy(
            update={
                "rating": effective_rating,
                "violence_ceiling": effective_ceiling,
                "adult_explicit_opt_in": adult_explicit_opt_in,
            }
        )
        opening_scene = result.opening_scene.model_copy(update={"tone": effective_tone})
        player_character = result.player_character.model_copy(update={"gender": player_gender})
        return result.model_copy(
            update={
                "template_id": template.id,
                "genre": template.genre,
                "tone": effective_tone,
                "content_boundaries": boundaries,
                "player_character": player_character,
                "opening_scene": opening_scene,
                "story_language": effective_language,
            }
        )


def _language_instruction(language: StoryLanguage) -> str:
    if language is StoryLanguage.VIETNAMESE:
        return (
            "Write all player-facing story content in natural Vietnamese with correct diacritics, including the "
            "title, premise, location names, character names, backgrounds, dialogue, opening scene and suggested actions. "
            "Keep JSON field names and IDs in the contract format."
        )
    return (
        "Write all player-facing story content in English, including the title, premise, location names, "
        "character names, backgrounds, dialogue, opening scene and suggested actions. "
        "Keep JSON field names and IDs in the contract format."
    )


__all__ = ["ProviderWorldDraftGenerator"]
