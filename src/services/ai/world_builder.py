"""Provider adapter for the transient AI World Builder draft."""

from __future__ import annotations

import json
from typing import Literal
from uuid import uuid4

from src.application.contracts.ai import (
    AIPromptRole,
    NarrativeDraft,
    RatingValue,
    ViolenceCeilingValue,
    WorldBriefSuggestion,
    WorldSeed,
)
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
            }
        )
        effective_tone = effective_tone if effective_tone is not None else result.tone
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

    async def assist_world_prompt(
        self,
        prompt: str,
        *,
        template_id: str = "school_romance",
        tone: str | None = None,
        player_gender: Literal["male", "female"] = "male",
        story_language: StoryLanguage | str = StoryLanguage.ENGLISH,
    ) -> WorldBriefSuggestion:
        """Refine a transient world idea without creating canonical records."""
        definition = self._prompts.get(AIPromptRole.WORLD_GUIDE)
        template = self._templates.get(template_id)
        effective_tone = tone.strip() if tone is not None else template.defaults.tone
        effective_language = StoryLanguage(story_language)
        run_id = str(uuid4())
        physical_call_id = str(uuid4())
        input_envelope = {
            "schema_version": "world-guide-input",
            "role": AIPromptRole.WORLD_GUIDE.value,
            "run_id": run_id,
            "template": template.id,
            "prompt": prompt.strip(),
            "story_language": effective_language.value,
            "language_instruction": _language_instruction(effective_language),
            "template_instructions": template.prompt_instructions,
            "presets": {
                "tone": effective_tone,
                "player_gender": player_gender,
            },
            "narrative_profile": template.narrative_profile.as_dict(),
            "opening_guidance": list(template.opening_guidance),
        }
        request = ProviderRequest(
            system_prompt=(
                "You are the local-first World Guide. Return only a strict JSON object; "
                "the result is transient writing guidance and has no persistence authority. "
                f"{_language_instruction(effective_language)}"
            ),
            user_prompt=definition.render({"input_json": json.dumps(input_envelope, ensure_ascii=False, sort_keys=True)}),
            # Route physically through the existing world_builder provider target.
            role=AIPromptRole.WORLD_BUILDER,
            physical_call_id=physical_call_id,
            logical_roles=(AIPromptRole.WORLD_GUIDE,),
            temperature=0.5,
            max_output_tokens=2_000,
            metadata={
                "logical_role": AIPromptRole.WORLD_GUIDE.value,
                "prompt_version": definition.semantic_version,
                "output_schema_version": definition.output_schema_version,
                "template_hash": definition.template_hash,
                "story_language": effective_language.value,
            },
        )
        response = await self._provider.generate_structured(
            request,
            self._contracts.structured_schema(
                AIPromptRole.WORLD_GUIDE,
                authoritative_metadata={
                    "schema_version": definition.output_schema_version,
                    "role": AIPromptRole.WORLD_GUIDE.value,
                    "run_id": run_id,
                    "prompt_version": definition.semantic_version,
                    "physical_call_id": physical_call_id,
                },
            ),
        )
        result = (
            response.data
            if isinstance(response.data, WorldBriefSuggestion)
            else self._contracts.parse(AIPromptRole.WORLD_GUIDE, response.data)
        )
        if not isinstance(result, WorldBriefSuggestion):
            raise TypeError("World guide contract returned a non-WorldBriefSuggestion response.")
        return result

    async def generate_opening_preview(self, seed: WorldSeed) -> NarrativeDraft:
        """Write the playable opening without creating canonical game state."""
        definition = self._prompts.get(AIPromptRole.WRITER)
        run_id = str(uuid4())
        physical_call_id = str(uuid4())
        scene = seed.opening_scene.model_copy(update={"guard_approved": True})
        characters = (seed.player_character, *seed.npc_profiles)
        location = seed.locations[0]
        context = {
            "story_language": seed.story_language.value,
            "world": {
                "title": seed.title,
                "premise": seed.premise,
                "genre": seed.genre,
                "tone": seed.tone,
                "content_boundaries": seed.content_boundaries.model_dump(mode="json"),
            },
            "character_profiles": [
                {
                    "character_id": character.character_id,
                    "name": character.name,
                    "age": character.age,
                    "gender": character.gender,
                    "role": character.role,
                    "background": character.background,
                    "voice": character.voice,
                    "traits": list(character.traits),
                    "values": list(character.values),
                }
                for character in characters
                if character.character_id in scene.participants
            ],
            "locations": [item.model_dump(mode="json") for item in seed.locations],
            "scene_locations": {
                "before": {character_id: location.location_id for character_id in scene.participants},
                "after": {character_id: location.location_id for character_id in scene.participants},
            },
            "current_locations": {character_id: location.location_id for character_id in scene.participants},
            "clock": {
                "approved_start": scene.world_time,
                "approved_end": scene.world_time,
                "approved_duration_minutes": 0,
            },
            "revision_feedback": {},
        }
        request = ProviderRequest(
            system_prompt=(
                "You are the Writer preparing a transient opening preview. Return only a strict JSON object. "
                "Do not advance time or invent state changes. "
                f"{_language_instruction(seed.story_language)}"
            ),
            user_prompt=definition.render(
                {
                    "input_json": json.dumps(
                        {"scene_spec": scene.model_dump(mode="json"), "context": context},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "language_guidance": self._prompts.read_language_guidance(seed.story_language.value),
                }
            ),
            role=AIPromptRole.WRITER,
            physical_call_id=physical_call_id,
            logical_roles=(AIPromptRole.WRITER,),
            temperature=0.6,
            max_output_tokens=4_000,
            metadata={
                "prompt_version": definition.semantic_version,
                "output_schema_version": definition.output_schema_version,
                "template_hash": definition.template_hash,
                "story_language": seed.story_language.value,
                "opening_preview": True,
            },
        )
        response = await self._provider.generate_structured(
            request,
            self._contracts.structured_schema(
                AIPromptRole.WRITER,
                authoritative_metadata={
                    "schema_version": definition.output_schema_version,
                    "role": AIPromptRole.WRITER.value,
                    "run_id": run_id,
                    "prompt_version": definition.semantic_version,
                    "physical_call_id": physical_call_id,
                },
            ),
        )
        result = (
            response.data
            if isinstance(response.data, NarrativeDraft)
            else self._contracts.parse(AIPromptRole.WRITER, response.data)
        )
        if not isinstance(result, NarrativeDraft):
            raise TypeError("Writer contract returned a non-NarrativeDraft response.")
        if result.scene_id != scene.scene_id:
            raise TypeError("Writer contract returned a preview for a different opening scene.")
        if not result.suggested_actions:
            raise TypeError("Writer contract returned an opening without suggested actions.")
        return result


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
