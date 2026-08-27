"""Stable identifiers for canonical records derived from a confirmed world seed."""

from __future__ import annotations

import re
import unicodedata
from uuid import NAMESPACE_URL, uuid5

from src.application.contracts.ai import WorldSeed

_IDENTIFIER_LIMIT = 36


def character_id_from_name(name: str) -> str:
    """Return the canonical, persistence-safe identifier derived from a name."""

    transliterated = name.replace("Đ", "D").replace("đ", "d")
    decomposed = unicodedata.normalize("NFKD", transliterated)
    without_marks = "".join(character for character in decomposed if not unicodedata.category(character).startswith("M"))
    slug = re.sub(r"[^\w]+", "_", without_marks.casefold(), flags=re.UNICODE).strip("_")
    return (slug or "npc")[:_IDENTIFIER_LIMIT].rstrip("_") or "npc"


def normalize_npc_character_ids(seed: WorldSeed) -> WorldSeed:
    """Derive NPC IDs from names and atomically remap every character reference."""

    used_ids = {
        seed.player_character.character_id.casefold(),
        *(alias.casefold() for character in (seed.player_character, *seed.npc_profiles) for alias in character.aliases),
    }
    remapped_ids: dict[str, str] = {}
    npc_profiles = []
    for npc in seed.npc_profiles:
        base_id = character_id_from_name(npc.name)
        character_id = (
            npc.character_id
            if _is_name_derived_character_id(npc.character_id, base_id) and npc.character_id.casefold() not in used_ids
            else _unique_character_id(base_id, used_ids)
        )
        used_ids.add(character_id.casefold())
        remapped_ids[npc.character_id] = character_id
        npc_profiles.append(npc.model_copy(update={"character_id": character_id}))

    if all(old_id == new_id for old_id, new_id in remapped_ids.items()):
        return seed

    def remap(value: str | None) -> str | None:
        return remapped_ids.get(value, value) if value is not None else None

    opening_scene = seed.opening_scene.model_copy(
        update={
            "participants": {str(remap(character_id)): age for character_id, age in seed.opening_scene.participants.items()},
            "consent": {_remap_consent_key(key, remapped_ids): state for key, state in seed.opening_scene.consent.items()},
            "pov": remap(seed.opening_scene.pov),
        }
    )
    return seed.model_copy(
        update={
            "npc_profiles": tuple(npc_profiles),
            "initial_claims": tuple(
                claim.model_copy(
                    update={
                        "subject_id": remap(claim.subject_id),
                        "object_id": remap(claim.object_id),
                        "branch_scope": remap(claim.branch_scope),
                    }
                )
                for claim in seed.initial_claims
            ),
            "initial_relationships": tuple(
                relationship.model_copy(
                    update={"source_id": remap(relationship.source_id), "target_id": remap(relationship.target_id)}
                )
                for relationship in seed.initial_relationships
            ),
            "initial_beliefs": tuple(
                belief.model_copy(update={"believer_id": remap(belief.believer_id), "branch_scope": remap(belief.branch_scope)})
                for belief in seed.initial_beliefs
            ),
            "goals": tuple(goal.model_copy(update={"owner_id": remap(goal.owner_id)}) for goal in seed.goals),
            "tensions": tuple(
                tension.model_copy(
                    update={
                        "observer_id": remap(tension.observer_id),
                        "rival_id": remap(tension.rival_id),
                        "focus_id": remap(tension.focus_id),
                    }
                )
                for tension in seed.tensions
            ),
            "threads": tuple(
                thread.model_copy(update={"participant_ids": tuple(str(remap(item)) for item in thread.participant_ids)})
                for thread in seed.threads
            ),
            "opening_scene": opening_scene,
        }
    )


def _unique_character_id(base_id: str, used_ids: set[str]) -> str:
    if base_id.casefold() not in used_ids:
        return base_id
    suffix = 2
    while True:
        suffix_text = f"_{suffix}"
        candidate = f"{base_id[: _IDENTIFIER_LIMIT - len(suffix_text)].rstrip('_')}{suffix_text}"
        if candidate.casefold() not in used_ids:
            return candidate
        suffix += 1


def _is_name_derived_character_id(character_id: str, base_id: str) -> bool:
    if character_id == base_id:
        return True
    match = re.search(r"_(\d+)$", character_id)
    if match is None or int(match.group(1)) < 2:
        return False
    suffix = match.group(0)
    expected = f"{base_id[: _IDENTIFIER_LIMIT - len(suffix)].rstrip('_')}{suffix}"
    return character_id == expected


def _remap_consent_key(key: str, remapped_ids: dict[str, str]) -> str:
    participant_id, separator, activity = key.partition(":")
    if not separator:
        return remapped_ids.get(key, key)
    return f"{remapped_ids.get(participant_id, participant_id)}:{activity}"


def opening_location_claim_id(playthrough_id: str, branch_id: str, character_id: str) -> str:
    """Return the stable claim ID for a participant's opening location."""

    value = f"interactive-novel:{playthrough_id}:{branch_id}:opening:{character_id}:location"
    return str(uuid5(NAMESPACE_URL, value))


__all__ = ["character_id_from_name", "normalize_npc_character_ids", "opening_location_claim_id"]
