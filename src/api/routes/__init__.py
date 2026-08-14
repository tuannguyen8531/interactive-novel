"""API route registration."""

from fastapi import FastAPI

from src.api.routes.health import router as health_router


def register_routes(app: FastAPI) -> None:
    """Register public routes under the versioned API prefix."""
    app.include_router(health_router, prefix="/api")


__all__ = ["register_routes"]
