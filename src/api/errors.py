"""Map application and transport failures to one API error envelope."""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from src.api.schemas import ErrorEnvelope, ErrorPayload
from src.application.errors import ApplicationError


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a JSON response with the public error contract."""
    payload = ErrorEnvelope(error=ErrorPayload(code=code, message=message, details=details or {}))
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


def application_error_response(error: ApplicationError) -> JSONResponse:
    """Translate an application exception without exposing internals."""
    return error_response(
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


def http_exception_response(error: HTTPException) -> JSONResponse:
    """Translate Starlette/FastAPI HTTP exceptions to the same envelope."""
    detail = error.detail
    if isinstance(detail, dict) and "code" in detail:
        code = str(detail.get("code"))
        message = str(detail.get("message", "HTTP request failed."))
        details = detail.get("details", {})
        if not isinstance(details, dict):
            details = {"value": details}
    else:
        code = "http_error"
        message = str(error.detail)
        details = {}
    return error_response(status_code=error.status_code, code=code, message=message, details=details)


__all__ = ["application_error_response", "error_response", "http_exception_response"]
