"""Semantic checks that sit after Pydantic parsing and before Guard."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, NoReturn

from src.application.contracts.ai import (
    AIPromptRole,
    ApplyRelationshipDeltaOperation,
    ClaimLinkProposal,
    ConsistencyReport,
    CritiqueResult,
    KnowledgeClaimProposal,
    NarrativeDraft,
    SimulationResult,
    StatePatchProposal,
    TurnPlan,
    WorldSeed,
)

from .contracts import AIContractValidationError, ContractDiagnostic


def validate_semantics(value: Any) -> None:
    """Validate cross-field authority and reference invariants.

    Pydantic owns shape/type validation. This function owns constraints that
    involve multiple fields or domain authority rules.
    """

    if isinstance(value, SimulationResult):
        _validate_claims(value.claim_proposals, path="claim_proposals")
        if value.state_patch is not None:
            _validate_state_patch(value.state_patch)
    elif isinstance(value, WorldSeed):
        _validate_world_seed(value)
    elif isinstance(value, StatePatchProposal):
        _validate_state_patch(value)
    elif isinstance(value, (TurnPlan, ConsistencyReport, NarrativeDraft, CritiqueResult)):
        return
    elif isinstance(value, KnowledgeClaimProposal):
        _validate_claim(value, path="claim")
    elif isinstance(value, ClaimLinkProposal):
        if value.from_claim_id == value.to_claim_id:
            _raise("link", "claim_link_self_reference", "claim link cannot point to itself")
    else:
        raise TypeError(f"Unsupported AI contract for semantic validation: {type(value).__name__}")


def _validate_state_patch(patch: StatePatchProposal) -> None:
    for index, operation in enumerate(patch.operations):
        if isinstance(operation, ApplyRelationshipDeltaOperation) and operation.source_id == operation.target_id:
            _raise(
                f"operations.{index}",
                "relationship_self_edge",
                "relationship delta source and target must differ",
            )
        claim = getattr(operation, "claim", None)
        if isinstance(claim, KnowledgeClaimProposal):
            _validate_claim(claim, path=f"operations.{index}.claim")


def _validate_claims(claims: Iterable[KnowledgeClaimProposal], *, path: str) -> None:
    for index, claim in enumerate(claims):
        _validate_claim(claim, path=f"{path}.{index}")


def _validate_claim(claim: KnowledgeClaimProposal, *, path: str) -> None:
    if claim.source_role not in {
        AIPromptRole.WORLD_BUILDER,
        AIPromptRole.SIMULATOR,
        AIPromptRole.CONTEXT_VALIDATOR,
    }:
        _raise(path, "claim_source_role_not_authorized", "this AI role cannot propose an authoritative claim")


def _validate_world_seed(seed: WorldSeed) -> None:
    character_ids = [seed.player_character.character_id, *(item.character_id for item in seed.npc_profiles)]
    character_seeds = (seed.player_character, *seed.npc_profiles)
    character_aliases = [alias for item in character_seeds for alias in item.aliases]
    claim_ids = [item.proposal_id for item in seed.initial_claims]
    _require_unique(character_ids, "characters")
    _require_unique(claim_ids, "initial_claims")
    _require_unique((item.belief_id for item in seed.initial_beliefs), "initial_beliefs")
    _require_unique((item.location_id for item in seed.locations), "locations")
    _require_unique((item.goal_id for item in seed.goals), "goals")
    _require_unique((item.thread_id for item in seed.threads), "threads")
    _require_unique((item.tension_id for item in seed.tensions), "tensions")
    _require_unique(
        (f"{item.source_id}:{item.target_id}" for item in seed.initial_relationships),
        "initial_relationships",
    )
    _validate_relationship_values(seed)
    _require_unique_aliases(character_ids, character_aliases)
    _require_identifier_lengths(
        (
            *character_ids,
            *(item.location_id for item in seed.locations),
            *(item.goal_id for item in seed.goals),
            *(item.thread_id for item in seed.threads),
            *(item.tension_id for item in seed.tensions),
            *claim_ids,
            *(item.belief_id for item in seed.initial_beliefs),
        )
    )
    known_characters = set(character_ids)
    known_locations = {item.location_id for item in seed.locations}
    known_goals = {item.goal_id for item in seed.goals}
    known_entities = known_characters | known_locations
    if not set(seed.opening_scene.participants).issubset(known_characters):
        _raise("opening_scene.participants", "unknown_character_reference", "opening scene references an unknown character")
    if seed.opening_scene.guard_approved:
        _raise("opening_scene.guard_approved", "draft_cannot_be_guard_approved", "WorldSeed is a draft before user confirmation")
    for character_id, age in seed.opening_scene.participants.items():
        character = next(item for item in character_seeds if item.character_id == character_id)
        if age != character.age:
            _raise(
                f"opening_scene.participants.{character_id}",
                "character_age_mismatch",
                "opening scene participant age must match the character seed",
            )
    if seed.content_boundaries.adult_explicit_opt_in and any(item.age < 18 for item in character_seeds):
        _raise(
            "content_boundaries.adult_explicit_opt_in",
            "adult_content_with_minor",
            "adult explicit content cannot be enabled while a character is under 18",
        )
    for index, character in enumerate(character_seeds):
        for goal_id in character.goal_ids:
            if goal_id not in known_goals:
                _raise(
                    f"characters.{index}.goal_ids",
                    "unknown_goal_reference",
                    "character goal reference is unknown",
                )
        for claim_id in character.private_claim_ids:
            claim = next((item for item in seed.initial_claims if item.proposal_id == claim_id), None)
            if claim is None:
                _raise(
                    f"characters.{index}.private_claim_ids",
                    "unknown_claim_reference",
                    "private claim reference is unknown",
                )
            if claim.branch_scope != character.character_id:
                _raise(
                    f"characters.{index}.private_claim_ids",
                    "private_claim_visibility_mismatch",
                    "private claim visibility must be scoped to its owning character",
                )
    for index, relationship in enumerate(seed.initial_relationships):
        if relationship.source_id == relationship.target_id:
            _raise(f"initial_relationships.{index}", "relationship_self_edge", "relationship source and target must differ")
        if relationship.source_id not in known_characters or relationship.target_id not in known_characters:
            _raise(
                f"initial_relationships.{index}",
                "unknown_character_reference",
                "relationship references an unknown character",
            )
    for index, goal in enumerate(seed.goals):
        if goal.owner_id not in known_characters:
            _raise(f"goals.{index}.owner_id", "unknown_character_reference", "goal owner is unknown")
    for index, thread in enumerate(seed.threads):
        if not set(thread.participant_ids).issubset(known_characters):
            _raise(f"threads.{index}.participant_ids", "unknown_character_reference", "thread participant is unknown")
    _validate_claims(seed.initial_claims, path="initial_claims")
    _validate_claim_conflicts(seed.initial_claims)
    for index, claim in enumerate(seed.initial_claims):
        if claim.branch_scope != "public" and claim.branch_scope not in known_characters:
            _raise(
                f"initial_claims.{index}.branch_scope",
                "unknown_visibility_owner",
                "claim visibility must be public or owned by a known character",
            )
        if claim.predicate == "located_at":
            if claim.subject_id not in known_characters or claim.object_id not in known_locations:
                _raise(
                    f"initial_claims.{index}",
                    "invalid_location_claim_reference",
                    "located_at claims must reference a known character and location",
                )
        elif claim.predicate == "goal_active":
            if claim.subject_id not in known_characters or claim.object_id not in known_goals:
                _raise(
                    f"initial_claims.{index}",
                    "invalid_goal_claim_reference",
                    "goal_active claims must reference a known character and goal",
                )
        elif claim.predicate in {"age_is", "physical_condition"}:
            if claim.subject_id not in known_characters:
                _raise(
                    f"initial_claims.{index}.subject_id",
                    "unknown_character_reference",
                    "claim subject is not a known character",
                )
        elif claim.predicate in {"romantic_interest", "commitment_status"}:
            if claim.subject_id not in known_characters or claim.object_id not in known_characters:
                _raise(
                    f"initial_claims.{index}",
                    "invalid_character_claim_reference",
                    "relationship claims must reference known characters",
                )
        elif claim.predicate == "secret_exists":
            if claim.subject_id not in known_characters or claim.branch_scope != claim.subject_id:
                _raise(
                    f"initial_claims.{index}",
                    "secret_visibility_mismatch",
                    "secret claims must be private to their character owner",
                )
        elif claim.subject_id not in known_entities:
            _raise(
                f"initial_claims.{index}.subject_id",
                "unknown_entity_reference",
                "claim subject is not a known world entity",
            )
    claim_fingerprints = {item.proposal_id for item in seed.initial_claims}
    for index, belief in enumerate(seed.initial_beliefs):
        if belief.believer_id not in known_characters:
            _raise(f"initial_beliefs.{index}.believer_id", "unknown_character_reference", "belief owner is unknown")
        if belief.claim_id not in claim_fingerprints:
            _raise(f"initial_beliefs.{index}.claim_id", "unknown_claim_reference", "belief claim is unknown")
        if belief.branch_scope != "public" and belief.branch_scope not in known_characters:
            _raise(f"initial_beliefs.{index}.branch_scope", "unknown_visibility_owner", "belief scope is unknown")
    for index, tension in enumerate(seed.tensions):
        if tension.observer_id not in known_characters or tension.rival_id not in known_characters:
            _raise(f"tensions.{index}", "unknown_character_reference", "tension observer or rival is unknown")
        if tension.focus_id not in known_characters:
            _raise(f"tensions.{index}.focus_id", "unknown_character_reference", "tension focus is unknown")
        if tension.observer_id == tension.rival_id:
            _raise(f"tensions.{index}", "tension_self_edge", "tension observer and rival must differ")
    claim_ids_set = set(claim_fingerprints)
    for path, reference in _scene_claim_references(seed):
        if reference.claim_id is not None and reference.claim_id not in claim_ids_set:
            _raise(path, "unknown_claim_reference", "scene claim reference is unknown")


def _require_unique(values: Iterable[str], path: str) -> None:
    materialized = tuple(values)
    if len(set(materialized)) != len(materialized):
        _raise(path, "duplicate_identity", f"{path} contains duplicate IDs")


def _require_unique_aliases(character_ids: Iterable[str], aliases: Iterable[str]) -> None:
    tokens: set[str] = set()
    for value in (*tuple(character_ids), *tuple(aliases)):
        normalized = value.strip().casefold()
        if normalized in tokens:
            _raise("characters.aliases", "duplicate_identity", "character IDs and aliases must be unique")
        tokens.add(normalized)


def _require_identifier_lengths(values: Iterable[str]) -> None:
    for value in values:
        if len(value) > 36:
            _raise("identifiers", "identifier_too_long", "persistence identifiers must be at most 36 characters")


def _validate_relationship_values(seed: WorldSeed) -> None:
    bounds = {
        "affection": (-1.0, 1.0),
        "attraction": (0.0, 1.0),
        "trust": (0.0, 1.0),
        "respect": (-1.0, 1.0),
        "comfort": (0.0, 1.0),
        "fear": (0.0, 1.0),
        "resentment": (0.0, 1.0),
    }
    for index, relationship in enumerate(seed.initial_relationships):
        for dimension, value in relationship.values.items():
            lower, upper = bounds[dimension.value]
            if not lower <= value <= upper:
                _raise(
                    f"initial_relationships.{index}.values.{dimension.value}",
                    "relationship_value_out_of_bounds",
                    f"relationship values must be between {lower} and {upper}",
                )


def _validate_claim_conflicts(claims: Iterable[KnowledgeClaimProposal]) -> None:
    polarities: dict[str, str] = {}
    for claim in claims:
        payload = claim.model_dump(mode="json", exclude={"proposal_id", "source_role", "source_run_id", "provenance"})
        polarity = str(payload.pop("polarity"))
        signature = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        previous = polarities.get(signature)
        if previous is not None and previous != polarity:
            _raise(
                "initial_claims",
                "obvious_canon_conflict",
                "initial claims cannot assert opposite polarities for the same proposition",
            )
        polarities[signature] = polarity


def _scene_claim_references(seed: WorldSeed) -> tuple[tuple[str, Any], ...]:
    references: list[tuple[str, Any]] = []
    for index, reference in enumerate(seed.opening_scene.allowed_claims):
        references.append((f"opening_scene.allowed_claims.{index}", reference))
    for index, reference in enumerate(seed.opening_scene.forbidden_claims):
        references.append((f"opening_scene.forbidden_claims.{index}", reference))
    return tuple(references)


def _raise(path: str, code: str, message: str) -> NoReturn:
    diagnostic = ContractDiagnostic(path, code, message)
    raise AIContractValidationError("semantic", (diagnostic,))


__all__ = ["validate_semantics"]
