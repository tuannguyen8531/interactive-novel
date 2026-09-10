"""World Builder generation, deterministic review and atomic confirmation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from inspect import signature
from typing import Any, Literal
from uuid import uuid4

from src.application.contracts.ai import CharacterSeed, RatingValue, SceneSpec, ViolenceCeilingValue, WorldSeed
from src.application.contracts.persistence import (
    BeliefEvidenceRecord,
    BeliefRecord,
    BranchRecord,
    CanonFactRecord,
    CanonicalTurnBundle,
    CharacterRecord,
    CharacterRole,
    CharacterStateRecord,
    EmotionalTensionRecord,
    EventRecord,
    KnowledgeClaimRecord,
    NarrativeHookRecord,
    NarrativeThreadRecord,
    PlaythroughRecord,
    RelationshipRecord,
    TurnRecord,
    WorldRecord,
)
from src.application.errors import ApplicationValidationError
from src.application.ports.persistence import UowFactory
from src.application.ports.worlds import WorldDraftGenerator
from src.application.world_seed import (
    assign_canonical_uuids,
    claim_fingerprint,
    normalize_npc_character_ids,
    opening_location_claim_id,
)
from src.domain.characters import CharacterState
from src.domain.knowledge import KnowledgeClaim
from src.domain.language import StoryLanguage
from src.domain.values import TimeRange
from src.services.ai.contracts import AIContractValidationError
from src.services.ai.validators import validate_semantics
from src.templates import StoryTemplate, StoryTemplateRegistry, StoryTemplateRegistryError


@dataclass(frozen=True, slots=True)
class WorldConfirmation:
    """Resources created by one confirmed WorldSeed transaction."""

    world: WorldRecord
    playthrough: PlaythroughRecord
    branch: BranchRecord
    opening_scene: SceneSpec
    opening_turn: TurnRecord


class WorldDraftApplicationService:
    """Keep a WorldSeed transient until explicit user confirmation."""

    def __init__(
        self,
        uow_factory: UowFactory,
        *,
        generator: WorldDraftGenerator | None = None,
        templates: StoryTemplateRegistry | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._generator = generator
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
        if not prompt.strip():
            raise ApplicationValidationError("World draft prompt must not be empty.")
        if self._generator is None:
            raise ApplicationValidationError("World draft generator is not configured.")
        template = self._require_template(template_id)
        effective_tone = tone.strip() if tone is not None else template.defaults.tone
        effective_rating = RatingValue(rating or template.defaults.rating.value)
        effective_ceiling = ViolenceCeilingValue(violence_ceiling or template.defaults.violence_ceiling.value)
        effective_language = StoryLanguage(story_language)
        generator_method: Any = self._generator.generate_world_draft
        parameters = signature(generator_method).parameters
        requested = {
            "template_id": template.id,
            "tone": effective_tone,
            "rating": effective_rating,
            "violence_ceiling": effective_ceiling,
            "player_gender": player_gender,
            "story_language": effective_language,
        }
        kwargs = {key: value for key, value in requested.items() if key in parameters}
        generated = await generator_method(prompt.strip(), **kwargs)
        boundaries = generated.content_boundaries.model_copy(
            update={
                "rating": effective_rating,
                "violence_ceiling": effective_ceiling,
            }
        )
        generated = generated.model_copy(
            update={
                "template_id": template.id,
                "genre": template.genre,
                "tone": effective_tone,
                "story_language": effective_language,
                "content_boundaries": boundaries,
                "player_character": generated.player_character.model_copy(update={"gender": player_gender}),
                "opening_scene": generated.opening_scene.model_copy(update={"tone": effective_tone}),
            }
        )
        return self.validate_world_draft(generated)

    def validate_world_draft(self, seed: WorldSeed) -> WorldSeed:
        """Re-validate shape and semantic references before review or confirm."""
        try:
            normalized = normalize_npc_character_ids(seed)
            validated = WorldSeed.model_validate(normalized.model_dump(mode="python"))
            validate_semantics(validated)
        except AIContractValidationError as error:
            raise ApplicationValidationError(
                str(error),
                details={"role": error.role, "diagnostics": [item.as_dict() for item in error.diagnostics]},
            ) from error
        template = self._require_template(validated.template_id)
        validated = validated.model_copy(update={"template_id": template.id})
        self._validate_scene_fingerprint_references(validated)
        return validated

    async def confirm_world(self, seed: WorldSeed, *, world_id: str | None = None) -> WorldRecord:
        """Legacy world-only confirmation kept for older callers."""
        validated = assign_canonical_uuids(self.validate_world_draft(seed))
        template = self._require_template(validated.template_id)
        world, characters = _build_world_records(validated, template=template, world_id=world_id)
        async with self._uow_factory() as uow:
            await uow.worlds.add(world)
            for character in characters:
                await uow.characters.add(character)
            await uow.commit()
        return world

    async def confirm_world_bundle(
        self,
        seed: WorldSeed,
        *,
        world_id: str | None = None,
        provider_config_snapshot: dict[str, Any] | None = None,
    ) -> WorldConfirmation:
        """Atomically create the world and its playable opening branch."""
        validated = assign_canonical_uuids(self.validate_world_draft(seed))
        template = self._require_template(validated.template_id)
        world, characters = _build_world_records(validated, template=template, world_id=world_id)
        player = validated.player_character
        opening_time = validated.opening_scene.world_time
        playthrough = PlaythroughRecord.new(
            world_id=world.id,
            player_character_id=player.character_id,
            provider_config_snapshot=provider_config_snapshot,
            world_clock_minutes=opening_time,
        )
        branch = BranchRecord.root(playthrough_id=playthrough.id)
        bundle = _build_opening_bundle(
            validated,
            playthrough=playthrough,
            branch=branch,
        )

        async with self._uow_factory() as uow:
            await uow.worlds.add(world)
            for character in characters:
                await uow.characters.add(character)
            await uow.playthroughs.add(playthrough)
            await uow.canonical.add_branch(branch)
            await uow.playthroughs.set_root_branch(playthrough.id, branch.id)
            opening_turn = await uow.canonical.commit_turn(bundle)
            await uow.commit()

        confirmed_playthrough = replace(
            playthrough,
            root_branch_id=branch.id,
            active_branch_id=branch.id,
            world_clock_minutes=bundle.world_time_end,
        )
        confirmed_branch = replace(branch, head_turn_id=opening_turn.id, head_revision=1)
        return WorldConfirmation(
            world=world,
            playthrough=confirmed_playthrough,
            branch=confirmed_branch,
            opening_scene=validated.opening_scene,
            opening_turn=opening_turn,
        )

    def _validate_scene_fingerprint_references(self, seed: WorldSeed) -> None:
        fingerprints = {claim_fingerprint(claim) for claim in seed.initial_claims}
        for reference in (*seed.opening_scene.allowed_claims, *seed.opening_scene.forbidden_claims):
            if reference.fingerprint is not None and reference.fingerprint not in fingerprints:
                raise ApplicationValidationError("Opening scene references an unknown claim fingerprint.")

    def _require_template(self, template_id: str) -> StoryTemplate:
        try:
            return self._templates.get(template_id)
        except StoryTemplateRegistryError as error:
            raise ApplicationValidationError(str(error), details={"template_id": template_id}) from error


def _build_world_records(
    seed: WorldSeed,
    *,
    template: StoryTemplate,
    world_id: str | None,
) -> tuple[WorldRecord, tuple[CharacterRecord, ...]]:
    world = WorldRecord.new(
        world_id=world_id,
        name=seed.title,
        premise=seed.premise,
        genre=seed.genre,
        tone=seed.tone,
        canon_rules={
            "world_seed": seed.model_dump(mode="json"),
            "world_builder": {"confirmed": True, "template": seed.template_id},
            "narrative_profile": template.narrative_profile.as_dict(),
            "story_language": seed.story_language.value,
        },
        content_policy=seed.content_boundaries.model_dump(mode="json"),
    )
    characters = (_character_record(world.id, seed.player_character, role=CharacterRole.PLAYER),) + tuple(
        _character_record(world.id, item, role=CharacterRole.NPC) for item in seed.npc_profiles
    )
    return world, characters


def _build_opening_bundle(
    seed: WorldSeed,
    *,
    playthrough: PlaythroughRecord,
    branch: BranchRecord,
    turn_id: str | None = None,
    event_id: str | None = None,
    turn_run_id: str | None = None,
) -> CanonicalTurnBundle:
    turn_id = turn_id or str(uuid4())
    event_id = event_id or str(uuid4())
    world_time = seed.opening_scene.world_time
    known_names = {item.character_id: item.name for item in (seed.player_character, *seed.npc_profiles)}
    participants = tuple(seed.opening_scene.participants)
    location = seed.locations[0]
    claims = tuple(
        _claim_record(
            claim,
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            turn_id=turn_id,
            source_event_id=event_id,
        )
        for claim in seed.initial_claims
    )
    location_claims = tuple(
        _opening_location_claim(
            character_id,
            location_id=location.location_id,
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            turn_id=turn_id,
            event_id=event_id,
            world_time=world_time,
            seed=seed,
        )
        for character_id in participants
        if not any(
            claim.subject_id == character_id
            and claim.predicate == "located_at"
            and claim.object_id == location.location_id
            and claim.polarity == "positive"
            for claim in claims
        )
    )
    claims = (*claims, *location_claims)
    claim_by_id = {item.claim_id: item for item in claims}
    canon_facts = tuple(
        CanonFactRecord(
            fact_id=str(uuid4()),
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            turn_id=turn_id,
            claim_id=claim.claim_id,
            status="active",
            source_event_or_rule="world_seed",
            asserted_world_time=world_time,
            asserted_turn=turn_id,
        )
        for claim in claims
    )
    beliefs, belief_evidence = _belief_records(
        seed,
        playthrough_id=playthrough.id,
        branch_id=branch.id,
        turn_id=turn_id,
        event_id=event_id,
        claim_by_id=claim_by_id,
    )
    relationships = tuple(
        RelationshipRecord(
            relationship_id=str(uuid4()),
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            source_id=relationship.source_id,
            target_id=relationship.target_id,
            values={dimension.value: float(value) for dimension, value in relationship.values.items()},
        )
        for relationship in seed.initial_relationships
    )
    tensions = tuple(
        EmotionalTensionRecord(
            tension_id=tension.tension_id,
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            turn_id=turn_id,
            observer_id=tension.observer_id,
            rival_id=tension.rival_id,
            focus_id=tension.focus_id,
            intensity=0.5,
            payload={"appraisal": tension.appraisal, "source": "world_seed"},
        )
        for tension in seed.tensions
    )
    threads = tuple(
        NarrativeThreadRecord(
            thread_id=thread.thread_id,
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            turn_id=turn_id,
            status="seeded",
            progress=0.0,
            urgency=0.5,
            payload={
                "thread_id": thread.thread_id,
                "premise": thread.premise,
                "stakes": thread.stakes,
                "participant_ids": list(thread.participant_ids),
                "source": "world_seed",
            },
        )
        for thread in seed.threads
    )
    hooks = tuple(
        NarrativeHookRecord(
            hook_id=str(uuid4()),
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            turn_id=turn_id,
            status="active",
            payload={
                "thread_id": thread.thread_id,
                "premise": thread.premise,
                "stakes": thread.stakes,
                "participant_ids": list(thread.participant_ids),
                "source": "world_seed",
            },
        )
        for thread in seed.threads
    )
    event = EventRecord(
        event_id=event_id,
        playthrough_id=playthrough.id,
        branch_id=branch.id,
        turn_id=turn_id,
        event_type="opening_scene",
        world_time=world_time,
        location_id=location.location_id,
        actor_ids=participants,
        payload={
            "scene_spec": seed.opening_scene.model_dump(mode="json"),
            "location": location.model_dump(mode="json"),
            "participant_names": [known_names[item] for item in participants],
        },
        salience=1.0,
        emotional_intensity=0.2,
        provenance={"source_type": "world_seed", "source_id": seed.run_id, "run_id": seed.run_id},
    )
    participant_names = ", ".join(known_names[item] for item in participants)
    if seed.story_language is StoryLanguage.VIETNAMESE:
        narrative = f"{seed.title} bắt đầu tại {location.name}. {seed.premise}\n\nCó mặt: {participant_names}."
    else:
        narrative = f"{seed.title} begins in {location.name}. {seed.premise}\n\nPresent: {participant_names}."
    opening_state = asdict(CharacterState(location_id=location.location_id, last_active_world_time=world_time))
    character_states = tuple(
        CharacterStateRecord(
            character_id=character_id,
            playthrough_id=playthrough.id,
            branch_id=branch.id,
            state=opening_state,
            last_active_turn_id=turn_id,
        )
        for character_id in participants
    )
    return CanonicalTurnBundle(
        playthrough_id=playthrough.id,
        branch_id=branch.id,
        raw_input="World Builder opening scene",
        base_revision=0,
        world_time_start=world_time,
        duration_minutes=0,
        world_time_end=world_time,
        turn_run_id=turn_run_id or str(uuid4()),
        final_narrative=narrative,
        approved_patch={
            "source": "world_builder_confirmation",
            "world_seed_run_id": seed.run_id,
            "opening_scene": seed.opening_scene.model_dump(mode="json"),
        },
        turn_id=turn_id,
        character_states=character_states,
        events=(event,),
        claims=claims,
        canon_facts=canon_facts,
        beliefs=beliefs,
        belief_evidence=belief_evidence,
        relationships=relationships,
        tensions=tensions,
        threads=threads,
        hooks=hooks,
        derived_job_types=(),
    )


def _belief_records(
    seed: WorldSeed,
    *,
    playthrough_id: str,
    branch_id: str,
    turn_id: str,
    event_id: str,
    claim_by_id: dict[str, KnowledgeClaimRecord],
) -> tuple[tuple[BeliefRecord, ...], tuple[BeliefEvidenceRecord, ...]]:
    beliefs: list[BeliefRecord] = []
    evidence: list[BeliefEvidenceRecord] = []
    for proposal in seed.initial_beliefs:
        claim = claim_by_id[proposal.claim_id]
        beliefs.append(
            BeliefRecord(
                belief_id=proposal.belief_id,
                playthrough_id=playthrough_id,
                branch_id=branch_id,
                turn_id=turn_id,
                believer_id=proposal.believer_id,
                claim_id=claim.claim_id,
                stance=proposal.stance,
                confidence=proposal.confidence,
                branch_scope=proposal.branch_scope,
                world_time=proposal.world_time,
                source_reliability=proposal.source_reliability,
                provenance={"source": "world_seed", "evidence_ids": list(proposal.evidence_ids)},
            )
        )
        for evidence_ref, method in (
            *((item, "world_seed_evidence") for item in proposal.evidence_ids),
            *((item, "world_seed_counter_evidence") for item in proposal.counter_evidence_ids),
        ):
            evidence.append(
                BeliefEvidenceRecord(
                    evidence_id=str(uuid4()),
                    belief_id=proposal.belief_id,
                    playthrough_id=playthrough_id,
                    branch_id=branch_id,
                    turn_id=turn_id,
                    owner_id=proposal.believer_id,
                    source_event_id=event_id,
                    claim_id=claim.claim_id,
                    world_time=proposal.world_time,
                    method=method,
                    confidence=proposal.confidence,
                    provenance={"source_reference": evidence_ref, "source": "world_seed"},
                )
            )
    return tuple(beliefs), tuple(evidence)


def _claim_record(
    claim: Any,
    *,
    playthrough_id: str,
    branch_id: str,
    turn_id: str,
    source_event_id: str,
) -> KnowledgeClaimRecord:
    provenance = claim.provenance.model_dump(mode="json")
    provenance["source_event_id"] = source_event_id
    provenance["owner_id"] = "public" if claim.branch_scope == "public" else claim.branch_scope
    return KnowledgeClaimRecord(
        claim_id=claim.proposal_id,
        playthrough_id=playthrough_id,
        branch_id=branch_id,
        turn_id=turn_id,
        claim_type=claim.claim_type,
        subject_id=claim.subject_id,
        predicate=claim.predicate,
        object_id=claim.object_id,
        typed_value=claim.typed_value,
        polarity=claim.polarity.value,
        qualifiers=dict(claim.qualifiers),
        valid_time_start=claim.valid_time.start,
        valid_time_end=claim.valid_time.end,
        branch_scope=claim.branch_scope,
        normalized_fingerprint=claim_fingerprint(claim),
        schema_version=claim.schema_version,
        provenance=provenance,
    )


def _opening_location_claim(
    character_id: str,
    *,
    location_id: str,
    playthrough_id: str,
    branch_id: str,
    turn_id: str,
    event_id: str,
    world_time: int,
    seed: WorldSeed,
) -> KnowledgeClaimRecord:
    claim_id = opening_location_claim_id(playthrough_id, branch_id, character_id)
    claim = KnowledgeClaim(
        claim_id=claim_id,
        subject_id=character_id,
        predicate="located_at",
        object_id=location_id,
        branch_scope=branch_id,
        valid_time=TimeRange(start=world_time),
    )
    return KnowledgeClaimRecord(
        claim_id=claim_id,
        playthrough_id=playthrough_id,
        branch_id=branch_id,
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
        provenance={
            "source_type": "world_seed",
            "source_id": seed.run_id,
            "run_id": seed.run_id,
            "prompt_version": seed.prompt_version,
            "source_event_id": event_id,
            "owner_id": "public",
        },
    )


def _character_record(world_id: str, seed: CharacterSeed, *, role: CharacterRole) -> CharacterRecord:
    return CharacterRecord.new(
        character_id=seed.character_id,
        world_id=world_id,
        role=role,
        display_name=seed.name,
        aliases=seed.aliases,
        profile={
            "public": {
                "age": seed.age,
                "gender": seed.gender,
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


__all__ = ["WorldConfirmation", "WorldDraftApplicationService"]
