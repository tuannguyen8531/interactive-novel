"""API route registration."""

from fastapi import FastAPI

from src.api.routes.health import router as health_router
from src.api.routes.providers import router as providers_router
from src.api.routes.queries import router as queries_router
from src.api.routes.resources import router as resources_router
from src.api.routes.turns import router as turns_router


def register_routes(app: FastAPI) -> None:
    """Register public routes under the versioned API prefix."""
    app.include_router(health_router, prefix="/api")
    app.include_router(resources_router, prefix="/api")
    app.include_router(queries_router, prefix="/api")
    app.include_router(turns_router, prefix="/api")
    app.include_router(providers_router, prefix="/api")


__all__ = ["register_routes"]
