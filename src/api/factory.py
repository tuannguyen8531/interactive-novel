"""FastAPI application factory for the local-first runtime."""

from __future__ import annotations

import logging
import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from src.api.container import ApplicationContainer, build_application_container
from src.api.errors import application_error_response, error_response, http_exception_response
from src.api.routes import register_routes
from src.application.contracts.providers import ProviderError
from src.application.errors import ApplicationError
from src.config import Settings, get_settings
from src.paths import PROJECT_ROOT

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own database migration, job recovery and graceful runner shutdown."""
    container: ApplicationContainer | None = getattr(app.state, "services", None)
    if container is None:
        container = build_application_container(app.state.settings)
        app.state.services = container
    try:
        await container.start()
        yield
    finally:
        await container.shutdown()


def create_app(
    settings: Settings | None = None,
    *,
    services: ApplicationContainer | None = None,
    frontend_dist: Path | None = None,
) -> FastAPI:
    """Construct an isolated FastAPI application for runtime and tests."""
    app_settings = settings or get_settings()
    app = FastAPI(
        title="Interactive Novel",
        version=app_settings.app_version,
        lifespan=_lifespan,
    )
    app.state.settings = app_settings
    app.state.services = services
    app.state.frontend_dist = (frontend_dist or PROJECT_ROOT / "web" / "dist").expanduser().resolve()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
    )
    register_routes(app)

    @app.exception_handler(ApplicationError)
    async def _application_error(_: Request, error: ApplicationError) -> JSONResponse:
        return application_error_response(error)

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, error: HTTPException) -> JSONResponse:
        return http_exception_response(error)

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, error: RequestValidationError) -> JSONResponse:
        return error_response(
            status_code=422,
            code="validation_error",
            message="Request validation failed.",
            details={"errors": error.errors()},
        )

    @app.exception_handler(ProviderError)
    async def _provider_error(_: Request, error: ProviderError) -> JSONResponse:
        return error_response(
            status_code=502,
            code=error.code,
            message=str(error),
            details={
                "provider": error.provider,
                "status_code": error.status_code,
                "request_id": error.request_id,
                "attempts": error.attempts,
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, error: Exception) -> JSONResponse:
        _logger.exception("Unhandled API exception", exc_info=error)
        return error_response(
            status_code=500,
            code="internal_error",
            message="Internal server error.",
        )

    _mount_frontend(app, app.state.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built Vue SPA without shadowing API or documentation routes."""
    resolved_dist = dist.expanduser().resolve()
    assets = resolved_dist / "assets"

    index = resolved_dist / "index.html"

    @app.get("/assets/{asset_path:path}", include_in_schema=False)
    async def _frontend_asset(asset_path: str) -> Response:
        asset = _safe_frontend_path(assets, asset_path)
        if asset is None or not asset.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return _file_response(asset)

    @app.get("/", include_in_schema=False)
    async def _frontend_index() -> Response:
        if index.is_file():
            return _file_response(index)
        return JSONResponse(
            {
                "name": "Interactive Novel",
                "frontend": "missing",
                "message": "Build the frontend with 'uv run build' to enable the GUI.",
            }
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _frontend_fallback(full_path: str) -> Response:
        if _is_reserved_route(full_path):
            raise HTTPException(status_code=404, detail="Not Found")
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Frontend bundle is not built.")
        candidate = (resolved_dist / full_path).resolve()
        try:
            candidate.relative_to(resolved_dist)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Not Found") from error
        if candidate.is_file():
            return _file_response(candidate)
        return _file_response(index)


def _safe_frontend_path(root: Path, relative_path: str) -> Path | None:
    """Resolve a frontend file while rejecting traversal outside its root."""
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return candidate


def _file_response(path: Path) -> Response:
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return Response(content=path.read_bytes(), media_type=media_type)


def _is_reserved_route(full_path: str) -> bool:
    first_segment = full_path.partition("/")[0]
    return first_segment in {"api", "docs", "openapi.json", "redoc"}


__all__ = ["create_app"]
