"""FastAPI application factory for the local-first runtime."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from src.api.errors import application_error_response, error_response, http_exception_response
from src.api.routes import register_routes
from src.application.errors import ApplicationError
from src.config import Settings, get_settings

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Keep lifecycle explicit while Phase 1 has no external resources."""
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct an isolated FastAPI application for runtime and tests."""
    app_settings = settings or get_settings()
    app = FastAPI(
        title="Interactive Novel",
        version=app_settings.app_version,
        lifespan=_lifespan,
    )
    app.state.settings = app_settings
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

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, error: Exception) -> JSONResponse:
        _logger.exception("Unhandled API exception", exc_info=error)
        return error_response(
            status_code=500,
            code="internal_error",
            message="Internal server error.",
        )

    return app


__all__ = ["create_app"]
