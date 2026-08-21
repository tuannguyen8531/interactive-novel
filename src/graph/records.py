"""Build the canonical bundle after Guard approval."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.application.contracts.ai import NarrativeDraft
from src.application.contracts.persistence import (
    BeliefRecord,
    CanonFactRecord,
    CanonicalTurnBundle,
    CharacterStateRecord,
    ClaimLinkRecord,
    EventRecord,
    KnowledgeClaimRecord,
    ObservationRecord,
    RelationshipRecord,
)
from src.domain.codec import patch_from_payload, patch_to_payload
from src.domain.engine import DomainEngine
from src.domain.patch import (
    AddClaimLink,
    AddEvent,
    AddKnowledgeClaim,
    AddObservation,
    AdvanceClock,
    ApplyRelationshipDelta,
    AssertCanonFact,
    SetCharacterCondition,
    SetCharacterLocation,
    StatePatch,
    UpdateBelief,
    UpdatePsychology,
)
from src.domain.state import GameState

from .state import TurnGraphState


def _provenance(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "source_type"):
        return {
            "source_type": value.source_type,
            "source_id": value.source_id,
            "turn_id": value.turn_id,
            "run_id": value.run_id,
            "prompt_version": value.prompt_version,
            "model_metadata": dict(value.model_metadata),
        }
    if isinstance(value, dict):
        return dict(value)
    return {"value": str(value)}


def _character_state_payload(character: Any) -> dict[str, Any]:
    state = character.state
    payload = asdict(state)
    payload["psychology"] = asdict(state.psychology)
    return payload


def build_canonical_bundle(state: TurnGraphState, game_state: GameState) -> CanonicalTurnBundle:
    """Convert the already-approved patch and prose into one atomic bundle."""

    patch_payload = state.get("approved_patch")
    if not isinstance(patch_payload, dict):
        raise ValueError("approved_patch is required before canonical record construction")
    patch = patch_from_payload(patch_payload)
    engine = DomainEngine()
    applied = engine.apply(game_state, patch)
    due_operations = engine.due_scheduled_operations(applied.after)
    if due_operations:
        patch = StatePatch(
            operations=(*patch.operations, *due_operations),
            branch_id=patch.branch_id,
            base_world_time=patch.base_world_time,
            patch_id=patch.patch_id,
        )
        patch_payload = patch_to_payload(patch)
        applied = engine.apply(game_state, patch)
    before = applied.before
    after = applied.after
    turn_id = f"turn-{state['turn_run_id']}"
    operation_list = tuple(patch.operations)
    duration_minutes = sum(operation.duration_minutes for operation in operation_list if isinstance(operation, AdvanceClock))

    changed_character_ids = {
        operation.character_id
        for operation in operation_list
        if isinstance(operation, (SetCharacterLocation, SetCharacterCondition, UpdatePsychology))
    }
    character_states = tuple(
        CharacterStateRecord(
            character_id=character_id,
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            state=_character_state_payload(after.characters[character_id]),
            last_active_turn_id=turn_id,
        )
        for character_id in sorted(changed_character_ids)
        if character_id in after.characters
    )

    event_ids = {operation.event.event_id for operation in operation_list if isinstance(operation, AddEvent)}
    event_ids.update(set(after.events).difference(before.events))
    events = tuple(
        EventRecord(
            event_id=event.event_id,
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            turn_id=turn_id,
            event_type=event.event_type,
            world_time=event.world_time,
            location_id=event.location_id,
            actor_ids=event.actor_ids,
            target_ids=event.target_ids,
            witness_ids=event.witness_ids,
            payload=dict(event.payload),
            salience=event.salience,
            emotional_intensity=event.emotional_intensity,
            cause_event_ids=event.cause_event_ids,
            provenance=_provenance(event.provenance),
        )
        for event_id, event in after.events.items()
        if event_id in event_ids
    )

    claim_ids = {operation.claim.claim_id for operation in operation_list if isinstance(operation, AddKnowledgeClaim)}
    claims = tuple(
        KnowledgeClaimRecord(
            claim_id=claim.claim_id,
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            turn_id=turn_id,
            claim_type=claim.claim_type,
            subject_id=claim.subject_id,
            predicate=claim.predicate,
            object_id=claim.object_id,
            typed_value=claim.typed_value,
            polarity=claim.polarity,
            qualifiers=dict(claim.qualifiers),
            valid_time_start=claim.valid_time.start,
            valid_time_end=claim.valid_time.end,
            branch_scope=claim.branch_scope,
            normalized_fingerprint=claim.normalized_fingerprint,
            schema_version=claim.schema_version,
            provenance=_provenance(claim.provenance),
        )
        for claim_id, claim in after.claims.items()
        if claim_id in claim_ids
    )

    fact_ids = {
        operation.fact_id or f"{patch.patch_id}:fact:{index}"
        for index, operation in enumerate(operation_list)
        if isinstance(operation, AssertCanonFact)
    }
    canon_facts = tuple(
        CanonFactRecord(
            fact_id=fact.fact_id,
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            turn_id=turn_id,
            claim_id=fact.claim_id,
            status=str(fact.status),
            source_event_or_rule=fact.source_event_or_rule,
            asserted_world_time=fact.asserted_world_time,
            asserted_turn=fact.asserted_turn,
            superseded_by=fact.superseded_by,
        )
        for fact_id, fact in after.canon_facts.items()
        if fact_id in fact_ids
    )

    link_ids = {operation.link.link_id for operation in operation_list if isinstance(operation, AddClaimLink)}
    claim_links = tuple(
        ClaimLinkRecord(
            link_id=link.link_id,
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            turn_id=turn_id,
            from_claim_id=link.from_claim_id,
            to_claim_id=link.to_claim_id,
            kind=str(link.kind),
        )
        for link_id, link in after.claim_links.items()
        if link_id in link_ids
    )

    observations = tuple(
        ObservationRecord(
            observation_id=operation.observation.observation_id,
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            turn_id=turn_id,
            observer_id=operation.observation.observer_id,
            observed_claim_id=operation.observation.observed_claim_id,
            source_event_id=operation.observation.source_event_id,
            method=operation.observation.method,
            world_time=operation.observation.world_time,
            confidence=operation.observation.confidence,
            distortion=operation.observation.distortion,
            provenance=_provenance(operation.observation.provenance),
        )
        for operation in operation_list
        if isinstance(operation, AddObservation)
    )

    beliefs = tuple(
        BeliefRecord(
            belief_id=operation.belief.belief_id,
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            turn_id=turn_id,
            believer_id=operation.belief.believer_id,
            claim_id=operation.belief.claim_id,
            stance=operation.belief.stance,
            confidence=operation.belief.confidence,
            branch_scope=operation.belief.branch_scope,
            world_time=operation.belief.world_time,
            source_reliability=operation.belief.source_reliability,
            provenance=_provenance(operation.belief.provenance),
        )
        for operation in operation_list
        if isinstance(operation, UpdateBelief)
    )

    relationship_keys = {
        (operation.source_id, operation.target_id)
        for operation in operation_list
        if isinstance(operation, ApplyRelationshipDelta)
    }
    relationship_keys.update(key for key, vector in after.relationships.items() if before.relationships.get(key) != vector)
    relationships = tuple(
        RelationshipRecord(
            relationship_id=f"relationship:{source_id}:{target_id}",
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            source_id=source_id,
            target_id=target_id,
            values=dict(after.relationships[(source_id, target_id)].values),
        )
        for source_id, target_id in sorted(relationship_keys)
        if (source_id, target_id) in after.relationships
    )

    narrative = str(state.get("final_narrative", "")).strip()
    if not narrative:
        raise ValueError("final_narrative is required before canonical record construction")
    draft = state.get("draft")
    suggested_actions = (
        tuple(item.model_dump(mode="json") for item in draft.suggested_actions) if isinstance(draft, NarrativeDraft) else ()
    )
    return CanonicalTurnBundle(
        playthrough_id=state["playthrough_id"],
        branch_id=state["branch_id"],
        raw_input=state["raw_input"],
        normalized_input=state.get("normalized_input"),
        base_revision=state["base_revision"],
        parent_turn_id=state.get("parent_turn_id"),
        world_time_start=before.world_time,
        duration_minutes=duration_minutes,
        world_time_end=after.world_time,
        turn_run_id=state["turn_run_id"],
        turn_id=turn_id,
        final_narrative=narrative,
        approved_patch=patch_payload,
        suggested_actions=suggested_actions,
        character_states=character_states,
        events=events,
        claims=claims,
        canon_facts=canon_facts,
        claim_links=claim_links,
        observations=observations,
        beliefs=beliefs,
        relationships=relationships,
    )


__all__ = ["build_canonical_bundle"]
