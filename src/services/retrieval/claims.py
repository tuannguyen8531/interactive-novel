"""Deterministic Claim Extractor for the targeted consistency phase."""

from __future__ import annotations

from collections.abc import Iterable

from src.application.contracts.ai import (
    AddClaimLinkOperation,
    AddKnowledgeClaimOperation,
    AddObservationOperation,
    AssertCanonFactOperation,
    KnowledgeClaimProposal,
    KnowledgeRequirement,
    SetCharacterLocationOperation,
    SimulationResult,
    StatePatchProposal,
    TurnPlan,
    UpdateBeliefOperation,
    ValidationQuery,
)
from src.application.contracts.retrieval import PUBLIC_OWNER, ClaimExtractionResult, canonical_value


class ClaimExtractor:
    """Turn typed simulation output into targeted, perspective-aware queries.

    The extractor never parses narrative prose and never creates an
    authoritative mutation.  It only forwards already typed proposals and
    creates deterministic evidence requirements for the validator/Guard.
    """

    def extract(
        self,
        simulation: SimulationResult,
        *,
        plan: TurnPlan | None = None,
        actor_id: str | None = None,
    ) -> ClaimExtractionResult:
        claims = self._unique_claims(
            [
                *simulation.claim_proposals,
                *self._claims_from_patch(simulation.state_patch),
            ]
        )
        mutations = tuple(simulation.state_patch.operations) if simulation.state_patch is not None else ()
        requirements = self._unique_requirements(
            [
                *simulation.knowledge_requirements,
                *self._requirements_from_claims(claims, simulation, actor_id=actor_id),
                *self._requirements_from_patch(simulation.state_patch),
            ]
        )
        queries = tuple(
            self._query_for_requirement(
                requirement,
                claims=claims,
                plan=plan,
            )
            for requirement in requirements
        )
        return ClaimExtractionResult(
            proposed_claims=tuple(claims),
            proposed_mutations=mutations,
            knowledge_requirements=requirements,
            validation_queries=queries,
            claim_to_mutation=self._claim_mapping(claims, mutations),
        )

    @staticmethod
    def _unique_claims(claims: Iterable[KnowledgeClaimProposal]) -> list[KnowledgeClaimProposal]:
        result: list[KnowledgeClaimProposal] = []
        seen: set[str] = set()
        for claim in claims:
            if claim.proposal_id in seen:
                continue
            seen.add(claim.proposal_id)
            result.append(claim)
        return result

    @staticmethod
    def _claims_from_patch(patch: StatePatchProposal | None) -> tuple[KnowledgeClaimProposal, ...]:
        if patch is None:
            return ()
        return tuple(operation.claim for operation in patch.operations if isinstance(operation, AddKnowledgeClaimOperation))

    @staticmethod
    def _requirements_from_claims(
        claims: Iterable[KnowledgeClaimProposal],
        simulation: SimulationResult,
        *,
        actor_id: str | None,
    ) -> tuple[KnowledgeRequirement, ...]:
        reaction_actor = simulation.npc_reactions[0].character_id if simulation.npc_reactions else None
        requirements: list[KnowledgeRequirement] = []
        for claim in claims:
            qualifier_actor = claim.qualifiers.get("actor_id")
            owner = qualifier_actor if isinstance(qualifier_actor, str) and qualifier_actor.strip() else None
            owner = owner or actor_id or reaction_actor or claim.subject_id
            purpose = claim.qualifiers.get("purpose")
            purpose_text = purpose if isinstance(purpose, str) and purpose.strip() else f"authorize proposed {claim.predicate}"
            requirements.append(
                KnowledgeRequirement(
                    requirement_id=f"requirement:{claim.proposal_id}",
                    actor_id=owner,
                    subject_id=claim.subject_id,
                    predicate=claim.predicate,
                    object_id=claim.object_id,
                    typed_value=claim.typed_value,
                    purpose=purpose_text,
                    branch_scope=claim.branch_scope,
                    world_time=claim.valid_time.start,
                    minimum_confidence=0.0,
                )
            )
        return tuple(requirements)

    @staticmethod
    def _requirements_from_patch(patch: StatePatchProposal | None) -> tuple[KnowledgeRequirement, ...]:
        if patch is None:
            return ()
        requirements: list[KnowledgeRequirement] = []
        for index, operation in enumerate(patch.operations):
            if not isinstance(operation, SetCharacterLocationOperation):
                continue
            requirements.append(
                KnowledgeRequirement(
                    requirement_id=f"requirement:location:{index}",
                    actor_id=operation.character_id,
                    subject_id=operation.character_id,
                    predicate="located_at",
                    object_id=operation.location_id,
                    purpose="authorize the character location transition",
                    branch_scope=patch.branch_id,
                    world_time=patch.base_world_time,
                    minimum_confidence=0.0,
                )
            )
        return tuple(requirements)

    @staticmethod
    def _unique_requirements(requirements: Iterable[KnowledgeRequirement]) -> tuple[KnowledgeRequirement, ...]:
        result: list[KnowledgeRequirement] = []
        seen: set[tuple[object, ...]] = set()
        for requirement in requirements:
            key = (
                requirement.actor_id,
                requirement.subject_id,
                requirement.predicate,
                requirement.object_id,
                canonical_value(requirement.typed_value),
                requirement.branch_scope,
                requirement.world_time,
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(requirement)
        return tuple(result)

    @staticmethod
    def _query_for_requirement(
        requirement: KnowledgeRequirement,
        *,
        claims: Iterable[KnowledgeClaimProposal],
        plan: TurnPlan | None,
    ) -> ValidationQuery:
        target_claim_ids = tuple(
            claim.proposal_id
            for claim in claims
            if claim.subject_id == requirement.subject_id
            and claim.predicate == requirement.predicate
            and claim.object_id == requirement.object_id
            and canonical_value(claim.typed_value) == canonical_value(requirement.typed_value)
        )
        plan_note = f" Plan checks: {len(plan.required_checks)}." if plan is not None else ""
        question = (
            f"Can actor {requirement.actor_id} use {requirement.predicate} for "
            f"{requirement.subject_id} at world time {requirement.world_time}?{plan_note}"
        )
        return ValidationQuery(
            query_id=f"query:{requirement.requirement_id}",
            requirement_id=requirement.requirement_id,
            actor_id=requirement.actor_id,
            query_type="authorization" if requirement.actor_id != PUBLIC_OWNER else "consistency",
            question=question,
            branch_scope=requirement.branch_scope,
            world_time=requirement.world_time,
            target_claim_ids=target_claim_ids,
        )

    @staticmethod
    def _claim_mapping(
        claims: Iterable[KnowledgeClaimProposal],
        mutations: Iterable[object],
    ) -> dict[str, tuple[str, ...]]:
        names_by_claim: dict[str, list[str]] = {claim.proposal_id: [] for claim in claims}
        for index, operation in enumerate(mutations):
            operation_name = f"mutation:{index}:{getattr(operation, 'operation_type', type(operation).__name__)}"
            referenced_claim_ids: tuple[str, ...] = ()
            if isinstance(operation, AddKnowledgeClaimOperation):
                referenced_claim_ids = (operation.claim.proposal_id,)
            elif isinstance(operation, AddClaimLinkOperation):
                referenced_claim_ids = (operation.link.from_claim_id, operation.link.to_claim_id)
            elif isinstance(operation, AssertCanonFactOperation):
                referenced_claim_ids = (operation.claim_id,)
            elif isinstance(operation, AddObservationOperation):
                referenced_claim_ids = (operation.observation.observed_claim_id,)
            elif isinstance(operation, UpdateBeliefOperation):
                referenced_claim_ids = (operation.belief.claim_id,)
            for claim_id in referenced_claim_ids:
                if claim_id in names_by_claim:
                    names_by_claim[claim_id].append(operation_name)
        return {claim_id: tuple(names) for claim_id, names in names_by_claim.items()}


__all__ = ["ClaimExtractor"]
