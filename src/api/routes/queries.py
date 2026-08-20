"""Read-only player and inspection projections."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.container import ApplicationContainer
from src.api.dependencies import get_services
from src.api.serialization import public_json

router = APIRouter(tags=["queries"])
_services_dependency = Depends(get_services)


@router.get("/playthroughs/{playthrough_id}/characters")
async def list_characters(
    playthrough_id: str,
    branch_id: str | None = None,
    services: ApplicationContainer = _services_dependency,
):
    return public_json(await services.queries.list_characters(playthrough_id=playthrough_id, branch_id=branch_id))


@router.get("/playthroughs/{playthrough_id}/characters/{character_id}")
async def get_character(
    playthrough_id: str,
    character_id: str,
    branch_id: str | None = None,
    services: ApplicationContainer = _services_dependency,
):
    return public_json(
        await services.queries.get_character_public_profile(
            playthrough_id=playthrough_id,
            character_id=character_id,
            branch_id=branch_id,
        )
    )


@router.get("/playthroughs/{playthrough_id}/branches/{branch_id}/characters/{character_id}/memory")
async def inspect_character_memory(
    playthrough_id: str,
    branch_id: str,
    character_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    services: ApplicationContainer = _services_dependency,
):
    return public_json(
        await services.queries.inspect_character_memory(
            playthrough_id=playthrough_id,
            branch_id=branch_id,
            character_id=character_id,
            limit=limit,
        )
    )


@router.get("/playthroughs/{playthrough_id}/branches/{branch_id}/relationships")
async def inspect_relationships(
    playthrough_id: str,
    branch_id: str,
    character_id: str | None = None,
    services: ApplicationContainer = _services_dependency,
):
    return public_json(
        await services.queries.inspect_relationships(
            playthrough_id=playthrough_id,
            branch_id=branch_id,
            character_id=character_id,
        )
    )


@router.get("/playthroughs/{playthrough_id}/branches/{branch_id}/timeline")
async def inspect_timeline(
    playthrough_id: str,
    branch_id: str,
    services: ApplicationContainer = _services_dependency,
):
    return public_json(await services.queries.inspect_timeline(playthrough_id=playthrough_id, branch_id=branch_id))


@router.get("/playthroughs/{playthrough_id}/branches/{branch_id}/inspector")
async def inspect_runtime(
    playthrough_id: str,
    branch_id: str,
    services: ApplicationContainer = _services_dependency,
):
    payload = await services.queries.inspect_runtime(playthrough_id=playthrough_id, branch_id=branch_id)
    telemetry = services.telemetry
    turn_runs_value = payload.get("turn_runs", ())
    turn_runs = turn_runs_value if isinstance(turn_runs_value, (list, tuple)) else ()
    run_ids = {
        str(item["turn_run_id"]) for item in turn_runs if isinstance(item, dict) and isinstance(item.get("turn_run_id"), str)
    }
    payload["llm_traces"] = tuple(event.as_dict() for event in telemetry.events if event.run_id in run_ids)
    payload["telemetry"] = {
        "enabled": telemetry.enabled,
        "summary": telemetry.summary().as_dict(),
        "note": None if telemetry.enabled else "Enable TELEMETRY_ENABLED to retain secret-safe LLM trace metadata.",
    }
    return public_json(payload)


__all__ = ["router"]
