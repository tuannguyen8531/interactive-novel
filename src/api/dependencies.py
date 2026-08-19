"""FastAPI dependency helpers for the process-local application container."""

from __future__ import annotations

from fastapi import Request

from src.api.container import ApplicationContainer
from src.application.errors import ServiceUnavailableError


def get_services(request: Request) -> ApplicationContainer:
    """Return the lifespan-owned container or a stable readiness error."""
    services = getattr(request.app.state, "services", None)
    if services is None:
        raise ServiceUnavailableError()
    return services


__all__ = ["get_services"]
