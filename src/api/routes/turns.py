"""Asynchronous turn/job REST and SSE endpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from src.api.container import ApplicationContainer
from src.api.dependencies import get_services
from src.api.schemas import TurnSubmitRequest
from src.api.serialization import public_json
from src.application.contracts.turns import SubmitTurnCommand
from src.application.errors import ResourceNotFoundError, ServiceUnavailableError
from src.domain.state import GameState

router = APIRouter(tags=["turns"])
_services_dependency = Depends(get_services)


@router.post("/turns", status_code=status.HTTP_202_ACCEPTED)
async def submit_turn(
    payload: TurnSubmitRequest,
    services: ApplicationContainer = _services_dependency,
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    playthrough = await services.playthroughs.get_playthrough(payload.playthrough_id)
    turn_run_id = payload.turn_run_id or str(uuid4())
    idempotency_key = idempotency_header or payload.idempotency_key or turn_run_id
    game_state = GameState.empty(
        world_id=playthrough.world_id,
        playthrough_id=payload.playthrough_id,
        branch_id=payload.branch_id,
        world_time=playthrough.world_clock_minutes,
    )
    command = SubmitTurnCommand(
        idempotency_key=idempotency_key,
        turn_run_id=turn_run_id,
        playthrough_id=payload.playthrough_id,
        branch_id=payload.branch_id,
        base_revision=payload.base_revision,
        raw_input=payload.raw_input,
        actor_id=payload.actor_id,
        game_state=game_state,
        parent_turn_id=payload.parent_turn_id,
        config_snapshot_id=payload.config_snapshot_id,
    )
    view = await services.turns.submit_turn(command)
    return public_json(view)


@router.get("/turns/{turn_id_or_run_id}")
async def get_turn(turn_id_or_run_id: str, services: ApplicationContainer = _services_dependency):
    result = await services.turns.get_turn(turn_id_or_run_id)
    if result is None:
        raise ResourceNotFoundError(f"Turn or run {turn_id_or_run_id} does not exist.")
    return public_json(result)


@router.post("/turns/{turn_run_id}/cancel")
async def cancel_turn(turn_run_id: str, services: ApplicationContainer = _services_dependency):
    return public_json(await services.turns.cancel_turn(turn_run_id))


@router.get("/jobs")
async def list_jobs(
    playthrough_id: str | None = None,
    branch_id: str | None = None,
    services: ApplicationContainer = _services_dependency,
):
    return public_json(await services.turns.list_jobs(playthrough_id=playthrough_id, branch_id=branch_id))


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, services: ApplicationContainer = _services_dependency):
    job = await services.turns.get_job(job_id)
    if job is None:
        raise ResourceNotFoundError(f"Job {job_id} does not exist.")
    return public_json(job)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, services: ApplicationContainer = _services_dependency):
    job = await services.turns.get_job(job_id)
    if job is None:
        raise ResourceNotFoundError(f"Job {job_id} does not exist.")
    return public_json(await services.turns.cancel_turn(job.turn_run_id))


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    request: Request,
    services: ApplicationContainer = _services_dependency,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    replay_from: str | None = Query(default=None, alias="last_event_id"),
):
    job = await services.turns.get_job(job_id)
    if job is None:
        raise ResourceNotFoundError(f"Job {job_id} does not exist.")
    if services.events is None:
        raise ServiceUnavailableError("The event stream is not configured.")
    cursor = last_event_id or replay_from
    if job.status in {"completed", "failed", "cancelled", "interrupted"} and not await services.events.history(
        job_id, after=cursor
    ):
        await services.events.register(job_id=job_id, turn_run_id=job.turn_run_id)
        await services.events.publish_job_event(
            job_id=job_id,
            turn_run_id=job.turn_run_id,
            event_type=job.status,
            phase="job",
            payload={"status": job.status, "result": public_json(job.result), "error": public_json(job.error)},
            terminal=True,
        )

    async def stream() -> AsyncIterator[dict[str, str]]:
        async for event in services.events.subscribe(job_id, last_event_id=cursor):
            if await request.is_disconnected():
                return
            yield {
                "id": event.id,
                "event": event.event_type,
                "data": json.dumps(event.as_dict(), ensure_ascii=False),
            }

    return EventSourceResponse(stream(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


__all__ = ["router"]
