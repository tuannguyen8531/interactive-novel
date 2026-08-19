"""Thin REST routes for worlds, playthroughs and branches."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.container import ApplicationContainer
from src.api.dependencies import get_services
from src.api.schemas import (
    ForkBranchRequest,
    PlaythroughCreateRequest,
    RootBranchRequest,
    SwitchBranchRequest,
    WorldCreateRequest,
    WorldDraftGenerateRequest,
    WorldDraftRequest,
)
from src.api.serialization import public_json

router = APIRouter(tags=["resources"])
_services_dependency = Depends(get_services)


@router.post("/world-drafts")
async def generate_world_draft(
    payload: WorldDraftGenerateRequest,
    services: ApplicationContainer = _services_dependency,
):
    draft = await services.world_drafts.generate_world_draft(payload.prompt)
    return public_json(draft)


@router.post("/world-drafts/validate")
async def validate_world_draft(
    payload: WorldDraftRequest,
    services: ApplicationContainer = _services_dependency,
):
    draft = services.world_drafts.validate_world_draft(payload.draft)
    return public_json(draft)


@router.post("/world-drafts/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_world_draft(
    payload: WorldDraftRequest,
    services: ApplicationContainer = _services_dependency,
):
    confirmation = await services.world_drafts.confirm_world_bundle(
        payload.draft,
        world_id=payload.world_id,
    )
    return public_json(confirmation)


@router.get("/worlds")
async def list_worlds(services: ApplicationContainer = _services_dependency):
    return public_json(await services.worlds.list_worlds())


@router.post("/worlds", status_code=status.HTTP_201_CREATED)
async def create_world(payload: WorldCreateRequest, services: ApplicationContainer = _services_dependency):
    world = await services.worlds.create_world(**payload.model_dump())
    return public_json(world)


@router.get("/worlds/{world_id}")
async def get_world(world_id: str, services: ApplicationContainer = _services_dependency):
    return public_json(await services.worlds.get_world(world_id))


@router.get("/playthroughs")
async def list_playthroughs(
    world_id: str | None = None,
    services: ApplicationContainer = _services_dependency,
):
    return public_json(await services.playthroughs.list_playthroughs(world_id=world_id))


@router.post("/playthroughs", status_code=status.HTTP_201_CREATED)
async def create_playthrough(
    payload: PlaythroughCreateRequest,
    services: ApplicationContainer = _services_dependency,
):
    playthrough = await services.playthroughs.create_playthrough(**payload.model_dump())
    return public_json(playthrough)


@router.get("/playthroughs/{playthrough_id}")
async def get_playthrough(playthrough_id: str, services: ApplicationContainer = _services_dependency):
    return public_json(await services.playthroughs.get_playthrough(playthrough_id))


@router.post("/branches/root", status_code=status.HTTP_201_CREATED)
async def create_root_branch(
    payload: RootBranchRequest,
    services: ApplicationContainer = _services_dependency,
):
    branch = await services.branches.create_root_branch(**payload.model_dump())
    return public_json(branch)


@router.post("/branches/fork", status_code=status.HTTP_201_CREATED)
async def fork_branch(payload: ForkBranchRequest, services: ApplicationContainer = _services_dependency):
    branch = await services.branches.fork_branch(**payload.model_dump())
    return public_json(branch)


@router.get("/playthroughs/{playthrough_id}/branches")
async def list_branches(playthrough_id: str, services: ApplicationContainer = _services_dependency):
    async with services.uow_factory() as uow:
        playthrough = await uow.playthroughs.get(playthrough_id)
        if playthrough is None:
            from src.application.errors import ResourceNotFoundError

            raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
        branches = await uow.canonical.list_branches(playthrough_id)
    return public_json(branches)


@router.post("/branches/{branch_id}/switch")
async def switch_branch(
    branch_id: str,
    payload: SwitchBranchRequest,
    services: ApplicationContainer = _services_dependency,
):
    branch = await services.branches.switch_branch(playthrough_id=payload.playthrough_id, branch_id=branch_id)
    return public_json(branch)


@router.get("/branches/{branch_id}/ancestry")
async def branch_ancestry(branch_id: str, services: ApplicationContainer = _services_dependency):
    return public_json(await services.branches.list_ancestry(branch_id))


@router.get("/playthroughs/{playthrough_id}/export")
async def export_playthrough(playthrough_id: str, services: ApplicationContainer = _services_dependency):
    exported = await services.exports.export_playthrough(playthrough_id)
    return exported.as_dict()


__all__ = ["router"]
