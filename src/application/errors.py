"""Application errors translated by API and CLI adapters."""

from __future__ import annotations

from typing import Any, ClassVar


class ApplicationError(Exception):
    """Base error that can safely cross an application boundary."""

    code: ClassVar[str] = "application_error"
    public_message: ClassVar[str] = "Application error."
    status_code: ClassVar[int] = 500

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.public_message)
        self.message = message or self.public_message
        self.details = details or {}


class ApplicationValidationError(ApplicationError):
    """The caller supplied an invalid application command."""

    code = "validation_error"
    public_message = "Request validation failed."
    status_code = 422


class ResourceNotFoundError(ApplicationError):
    """A requested resource does not exist."""

    code = "not_found"
    public_message = "Resource not found."
    status_code = 404


class ResourceConflictError(ApplicationError):
    """A request conflicts with current state."""

    code = "conflict"
    public_message = "Resource conflict."
    status_code = 409


__all__ = [
    "ApplicationError",
    "ApplicationValidationError",
    "ResourceConflictError",
    "ResourceNotFoundError",
]
