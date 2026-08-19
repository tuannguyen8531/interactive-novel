"""World draft generation, validation and confirmation use cases."""

from __future__ import annotations

from typing import Any

from src.application.contracts.ai import WorldSeed
from src.application.contracts.persistence import CharacterRecord, WorldRecord
from src.application.errors import ApplicationValidationError
from src.application.ports.persistence import UowFactory
from src.application.ports.worlds import WorldDraftGenerator


class WorldDraftApplicationService:
    """Keep an AI world seed transient until the user explicitly confirms it."""

    def __init__(self, uow_factory: UowFactory, *, generator: WorldDraftGenerator | None = None) -> None:
        self._uow_factory = uow_factory
        self._generator = generator

    async def generate_world_draft(self, prompt: str) -> WorldSeed:
        if not prompt.strip():
            raise ApplicationValidationError("World draft prompt must not be empty.")
        if self._generator is None:
            raise ApplicationValidationError("World draft generator is not configured.")
        return self.validate_world_draft(await self._generator.generate_world_draft(prompt))

    def validate_world_draft(self, seed: WorldSeed) -> WorldSeed:
        """Re-validate shape and enforce identity/reference rules before confirm."""
        validated = WorldSeed.model_validate(seed.model_dump(mode="python"))
        character_ids = [validated.player_character.character_id, *(item.character_id for item in validated.npc_profiles)]
        if len(set(character_ids)) != len(character_ids):
            raise ApplicationValidationError("World draft contains duplicate character IDs.")
        known_characters = set(character_ids)
        if not set(validated.opening_scene.participants).issubset(known_characters):
            raise ApplicationValidationError("World draft opening scene references an unknown character.")
        for relationship in validated.initial_relationships:
            if relationship.source_id == relationship.target_id:
                raise ApplicationValidationError("World draft cannot contain a self relationship.")
            if relationship.source_id not in known_characters or relationship.target_id not in known_characters:
                raise ApplicationValidationError("World draft relationship references an unknown character.")
        if validated.opening_scene.guard_approved:
            raise ApplicationValidationError("World draft must be reviewed before confirmation.")
        return validated

    async def confirm_world(self, seed: WorldSeed, *, world_id: str | None = None) -> WorldRecord:
        validated = self.validate_world_draft(seed)
        world = WorldRecord.new(
            world_id=world_id,
            name=validated.title,
            premise=validated.premise,
            genre=validated.genre,
            tone=validated.tone,
            canon_rules={"world_seed": validated.model_dump(mode="json")},
            content_policy=validated.content_boundaries.model_dump(mode="json"),
        )
        characters = (_character_record(world.id, validated.player_character),) + tuple(
            _character_record(world.id, item) for item in validated.npc_profiles
        )
        async with self._uow_factory() as uow:
            await uow.worlds.add(world)
            for character in characters:
                await uow.characters.add(character)
            await uow.commit()
        return world


def _character_record(world_id: str, seed: Any) -> CharacterRecord:
    return CharacterRecord.new(
        character_id=seed.character_id,
        world_id=world_id,
        display_name=seed.name,
        aliases=seed.aliases,
        profile={
            "public": {
                "age": seed.age,
                "role": seed.role,
                "background": seed.background,
                "voice": seed.voice,
                "traits": list(seed.traits),
                "values": list(seed.values),
                "goal_ids": list(seed.goal_ids),
            },
            "private": {"claim_ids": list(seed.private_claim_ids)},
        },
    )


__all__ = ["WorldDraftApplicationService"]
