"""Semantic checks that sit after Pydantic parsing and before Guard."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

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
    _require_unique(character_ids, "characters")
    _require_unique((item.location_id for item in seed.locations), "locations")
    _require_unique((item.goal_id for item in seed.goals), "goals")
    _require_unique((item.thread_id for item in seed.threads), "threads")
    _require_unique((item.tension_id for item in seed.tensions), "tensions")
    known_characters = set(character_ids)
    if not set(seed.opening_scene.participants).issubset(known_characters):
        _raise("opening_scene.participants", "unknown_character_reference", "opening scene references an unknown character")
    if seed.opening_scene.guard_approved:
        _raise("opening_scene.guard_approved", "draft_cannot_be_guard_approved", "WorldSeed is a draft before user confirmation")
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


def _require_unique(values: Iterable[str], path: str) -> None:
    materialized = tuple(values)
    if len(set(materialized)) != len(materialized):
        _raise(path, "duplicate_identity", f"{path} contains duplicate IDs")


def _raise(path: str, code: str, message: str) -> None:
    diagnostic = ContractDiagnostic(path, code, message)
    raise AIContractValidationError("semantic", (diagnostic,))


__all__ = ["validate_semantics"]
