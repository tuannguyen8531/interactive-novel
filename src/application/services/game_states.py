"""Hydrate one branch-scoped domain state from seed data and canonical history."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from src.application.contracts.ai import WorldSeed
from src.application.errors import ResourceNotFoundError
from src.application.ports.persistence import UowFactory
from src.application.world_seed import opening_location_claim_id
from src.domain.characters import Character, CharacterProfile
from src.domain.content import ContentPolicy
from src.domain.events import Belief, Event
from src.domain.knowledge import CanonFact, KnowledgeClaim
from src.domain.narrative import NarrativeThread
from src.domain.relationships import RelationshipVector
from src.domain.state import GameState
from src.domain.values import Provenance, TimeRange

from .replay import ReplayApplicationService


class GameStateApplicationService:
    """Build the authoritative input snapshot for a turn at its branch head."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory
        self._replay = ReplayApplicationService(uow_factory)

    async def load(self, *, playthrough_id: str, branch_id: str) -> GameState:
        async with self._uow_factory() as uow:
            playthrough = await uow.playthroughs.get(playthrough_id)
            if playthrough is None:
                raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
            branch = await uow.canonical.get_branch(branch_id)
            if branch is None or branch.playthrough_id != playthrough_id:
                raise ResourceNotFoundError(f"Branch {branch_id} does not belong to this playthrough.")
            world = await uow.worlds.get(playthrough.world_id)
            if world is None:
                raise ResourceNotFoundError(f"World {playthrough.world_id} does not exist.")
            ancestry = await uow.canonical.get_branch_ancestry(branch_id)
            characters = await uow.characters.list(world_id=world.id, playthrough_id=playthrough_id)
            turns = await uow.canonical.list_visible_turns(branch_id)
            events = await uow.canonical.list_visible_events(branch_id)

        first_world_time = min((turn.world_time_start for turn in turns), default=0)
        seed = _world_seed(world.canon_rules)
        if seed is not None:
            first_world_time = seed.opening_scene.world_time

        state = GameState.empty(
            world_id=world.id,
            playthrough_id=playthrough_id,
            branch_id=branch_id,
            world_time=first_world_time,
            policy=ContentPolicy.from_mapping(world.content_policy),
        )
        state.branch_ancestry = tuple(item.id for item in ancestry)
        state.characters = {record.id: _character(record) for record in characters}
        state.metadata = {
            "branch_head_revision": branch.head_revision,
            "branch_head_turn_id": branch.head_turn_id,
            "rng_seed": playthrough.rng_seed,
            "rng_state": deepcopy(playthrough.rng_state),
            "world_profile": {
                "template_id": seed.template_id if seed is not None else None,
                "genre": world.genre,
                "tone": world.tone,
                "premise": world.premise,
                "narrative_profile": dict(world.canon_rules.get("narrative_profile", {})),
            },
        }
        if seed is not None:
            _apply_world_seed(state, seed)

        # Bootstrap records predate the typed-patch codec. Later events are
        # restored by replaying the corresponding approved patches.
        opening_turn_id = turns[0].id if turns else None
        for record in events:
            if record.turn_id != opening_turn_id:
                continue
            event = Event(
                event_id=record.event_id,
                event_type=record.event_type,
                world_time=record.world_time,
                branch_scope=record.branch_id,
                location_id=record.location_id,
                actor_ids=record.actor_ids,
                target_ids=record.target_ids,
                witness_ids=record.witness_ids,
                payload=record.payload,
                salience=record.salience,
                emotional_intensity=record.emotional_intensity,
                cause_event_ids=record.cause_event_ids,
                turn_id=record.turn_id,
                provenance=_provenance(record.provenance),
            )
            state.events[event.event_id] = event

        rebuilt = await self._replay.replay_branch(branch_id=branch_id, initial_state=state)
        if branch.head_turn_id is not None:
            head = next((turn for turn in turns if turn.id == branch.head_turn_id), None)
            if head is None:
                raise ResourceNotFoundError(f"Branch head turn {branch.head_turn_id} does not exist.")
            if rebuilt.world_time != head.world_time_end:
                raise ValueError(
                    f"Replayed world time {rebuilt.world_time} does not match branch head time {head.world_time_end}."
                )
        rebuilt.metadata["branch_head_revision"] = branch.head_revision
        rebuilt.metadata["branch_head_turn_id"] = branch.head_turn_id
        return rebuilt


def _world_seed(canon_rules: Mapping[str, Any]) -> WorldSeed | None:
    value = canon_rules.get("world_seed")
    if not isinstance(value, Mapping):
        return None
    return WorldSeed.model_validate(value)


def _character(record: Any) -> Character:
    profile = dict(record.profile)
    public_value = profile.get("public")
    private_value = profile.get("private")
    public: Mapping[str, Any] = public_value if isinstance(public_value, Mapping) else profile
    private: Mapping[str, Any] = private_value if isinstance(private_value, Mapping) else {}
    return Character(
        CharacterProfile(
            character_id=record.id,
            display_name=record.display_name,
            age_anchor=int(public.get("age", 18)),
            aliases=tuple(record.aliases),
            gender=str(public.get("gender", "unspecified")),
            role=str(public.get("role", "")),
            background=_background(public),
            appearance=str(public.get("appearance", "")),
            voice=str(public.get("voice", "")),
            traits=tuple(str(value) for value in public.get("traits", ())),
            values=tuple(str(value) for value in public.get("values", ())),
            boundaries=tuple(str(value) for value in public.get("boundaries", ())),
            long_term_goals=tuple(str(value) for value in public.get("goal_ids", ())),
            likes=tuple(str(value) for value in public.get("likes", ())),
            dislikes=tuple(str(value) for value in public.get("dislikes", ())),
            initial_secrets=tuple(str(value) for value in private.get("claim_ids", ())),
        )
    )


def _background(public: Mapping[str, Any]) -> str:
    background = str(public.get("background", "")).strip()
    legacy_description = str(public.get("description", "")).strip()
    if legacy_description and legacy_description not in background:
        return f"{legacy_description}\n\n{background}".strip()
    return background


def _apply_world_seed(state: GameState, seed: WorldSeed) -> None:
    state.metadata["character_goals"] = {
        character_id: [goal.model_dump(mode="json") for goal in seed.goals if goal.owner_id == character_id]
        for character_id in (seed.player_character.character_id, *(item.character_id for item in seed.npc_profiles))
    }
    state.metadata["emotional_tensions"] = [item.model_dump(mode="json") for item in seed.tensions]
    state.locations.update(location.location_id for location in seed.locations)
    opening_location_id = seed.locations[0].location_id
    for character_id in seed.opening_scene.participants:
        character = state.characters.get(character_id)
        if character is not None:
            state.characters[character_id] = character.with_state(
                location_id=opening_location_id,
                last_active_world_time=seed.opening_scene.world_time,
            )
    for relationship in seed.initial_relationships:
        state.relationships[(relationship.source_id, relationship.target_id)] = RelationshipVector(
            {str(dimension): float(value) for dimension, value in relationship.values.items()}
        )
    for proposal in seed.initial_claims:
        claim = KnowledgeClaim(
            claim_id=proposal.proposal_id,
            subject_id=proposal.subject_id,
            predicate=proposal.predicate,
            object_id=proposal.object_id,
            typed_value=proposal.typed_value,
            polarity=proposal.polarity.value,
            qualifiers=proposal.qualifiers,
            valid_time=TimeRange(proposal.valid_time.start, proposal.valid_time.end),
            branch_scope=proposal.branch_scope,
            schema_version=proposal.schema_version,
            claim_type=proposal.claim_type,
            provenance=_provenance(proposal.provenance.model_dump(mode="json")),
        )
        state.claims[claim.claim_id] = claim
        fact = CanonFact(
            fact_id=f"world-seed:{claim.claim_id}",
            claim_id=claim.claim_id,
            source_event_or_rule="world_seed",
            asserted_world_time=seed.opening_scene.world_time,
        )
        state.canon_facts[fact.fact_id] = fact
    opening_location_claims = {
        (claim.subject_id, claim.predicate, claim.object_id, claim.polarity) for claim in state.claims.values()
    }
    for character_id in seed.opening_scene.participants:
        signature = (character_id, "located_at", opening_location_id, "positive")
        if signature in opening_location_claims:
            continue
        claim = KnowledgeClaim(
            claim_id=opening_location_claim_id(state.playthrough_id, state.branch_id, character_id),
            subject_id=character_id,
            predicate="located_at",
            object_id=opening_location_id,
            branch_scope=state.branch_id,
            valid_time=TimeRange(seed.opening_scene.world_time),
            provenance=Provenance(
                source_type="world_seed",
                source_id=seed.run_id,
                run_id=seed.run_id,
                prompt_version=seed.prompt_version,
            ),
        )
        state.claims[claim.claim_id] = claim
        fact = CanonFact(
            fact_id=f"world-seed:{claim.claim_id}",
            claim_id=claim.claim_id,
            source_event_or_rule="world_seed_opening_location",
            asserted_world_time=seed.opening_scene.world_time,
        )
        state.canon_facts[fact.fact_id] = fact
    for proposal in seed.initial_beliefs:
        belief = Belief(
            belief_id=proposal.belief_id,
            believer_id=proposal.believer_id,
            claim_id=proposal.claim_id,
            stance=proposal.stance,
            confidence=proposal.confidence,
            evidence_ids=proposal.evidence_ids,
            counter_evidence_ids=proposal.counter_evidence_ids,
            branch_scope=proposal.branch_scope,
            world_time=proposal.world_time,
            source_reliability=proposal.source_reliability,
        )
        state.beliefs[belief.belief_id] = belief
    for item in seed.threads:
        thread = NarrativeThread(
            thread_id=item.thread_id,
            premise=item.premise,
            branch_scope="public",
            participant_ids=item.participant_ids,
            stakes=item.stakes,
            urgency=0.5,
        )
        state.threads[thread.thread_id] = thread


def _provenance(value: Any) -> Provenance | None:
    if value is None:
        return None
    mapping = value if isinstance(value, Mapping) else {}
    source_type = str(mapping.get("source_type", mapping.get("source", "canonical")))
    source_id = str(mapping.get("source_id", mapping.get("run_id", "canonical")))
    return Provenance(
        source_type=source_type,
        source_id=source_id,
        turn_id=None if mapping.get("turn_id") is None else str(mapping["turn_id"]),
        run_id=None if mapping.get("run_id") is None else str(mapping["run_id"]),
        prompt_version=None if mapping.get("prompt_version") is None else str(mapping["prompt_version"]),
        model_metadata=dict(mapping.get("model_metadata", {})),
    )


__all__ = ["GameStateApplicationService"]
