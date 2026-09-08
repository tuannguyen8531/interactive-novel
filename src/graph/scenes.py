"""Prepare the public writing boundary from the accepted turn and final patch."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from src.application.contracts.ai import AIPromptRole, ClaimReference, SceneSpec, SimulationResult, TurnPlan
from src.domain.codec import patch_from_payload
from src.domain.engine import DomainEngine
from src.domain.guard import DomainGuard
from src.domain.patch import AddKnowledgeClaim
from src.domain.state import GameState

from .state import TurnGraphState


class SceneLocations(BaseModel):
    """Public spatial transition, without psychology, beliefs or relationship scores."""

    model_config = ConfigDict(frozen=True)

    before: dict[str, str | None]
    after: dict[str, str | None]


@dataclass(frozen=True)
class PreparedScene:
    scene: SceneSpec
    locations: SceneLocations
    location_catalog: tuple[dict[str, str], ...]


def prepare_scene(state: TurnGraphState, game_state: GameState, guard: DomainGuard) -> PreparedScene:
    """Apply the approved patch to a copy; never promote candidate beats to outcomes."""

    plan = state.get("plan")
    simulation = state.get("simulation")
    patch_payload = state.get("approved_patch")
    if not state.get("guard_approved") or not isinstance(patch_payload, dict):
        raise ValueError("Scene preparation requires a Guard-approved patch.")
    if not isinstance(plan, TurnPlan) or not isinstance(simulation, SimulationResult):
        raise ValueError("Scene preparation requires plan and simulation artifacts.")
    patch = patch_from_payload(patch_payload)
    after = DomainEngine(guard=guard).apply(game_state, patch).after
    attempt_only = any(item.get("code") == "invalid_model_mutations_dropped" for item in state.get("warnings", ()))
    actor_id = state.get("actor_id", "player")
    participant_ids = tuple(
        dict.fromkeys((actor_id, *plan.characters_involved, *(r.character_id for r in simulation.npc_reactions)))
    )
    participants = {
        character_id: game_state.characters[character_id].profile.age_at(game_state.world_time)
        for character_id in participant_ids
        if character_id in game_state.characters
    }
    if not participants:
        raise ValueError("Scene has no canonical participants.")
    outcome = state.get("normalized_input", state["raw_input"]) if attempt_only else simulation.proposed_outcome
    reactions = () if attempt_only else tuple(reaction.immediate_reaction for reaction in simulation.npc_reactions)
    visible_scopes = {"public", game_state.branch_id, *game_state.branch_ancestry, actor_id}
    claims = tuple(
        ClaimReference(claim_id=operation.claim.claim_id)
        for operation in patch.operations
        if isinstance(operation, AddKnowledgeClaim) and operation.claim.branch_scope in visible_scopes
    )
    world_profile = game_state.metadata.get("world_profile", {})
    tone = world_profile.get("tone", "gentle") if isinstance(world_profile, dict) else "gentle"
    scene = SceneSpec(
        scene_id=f"scene-{state['turn_run_id']}",
        source_role=AIPromptRole.SIMULATOR,
        source_run_id=state["turn_run_id"],
        world_time=game_state.world_time,
        outcome_status="attempt_only" if attempt_only else "accepted",
        tags=plan.content_tags,
        participants=participants,
        violence_detail=plan.violence_detail,
        approved_beats=(outcome,),
        visible_actions=(outcome, *reactions),
        pov="second_person",
        tone=str(tone or "gentle"),
        allowed_claims=claims,
        length_target=300,
    )
    locations = SceneLocations(
        before={key: game_state.characters[key].state.location_id for key in participants},
        after={key: after.characters[key].state.location_id for key in participants},
    )
    # Include destinations registered this turn, without exporting the entire GameState.
    visible_location_ids = set(game_state.locations) | {value for value in locations.after.values() if value is not None}
    catalog = tuple(
        {
            "location_id": key,
            "name": after.location_details[key].name if key in after.location_details else key,
            "description": after.location_details[key].description if key in after.location_details else "",
        }
        for key in sorted(visible_location_ids)
    )
    return PreparedScene(scene=scene, locations=locations, location_catalog=catalog)
