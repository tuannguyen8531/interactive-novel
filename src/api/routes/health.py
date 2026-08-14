"""Health endpoint."""

from fastapi import APIRouter, Request

from src.api.schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Return a safe liveness response without touching persistence."""
    settings = request.app.state.settings
    return HealthResponse(status="ok", service=settings.app_name, version=settings.app_version)


__all__ = ["router"]
