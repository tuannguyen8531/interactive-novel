"""Errors raised by pure domain validation and authorization rules."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base error with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        operation_index: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.operation_index = operation_index
        super().__init__(f"{code}: {message}")

    @property
    def reason_code(self) -> str:
        """Compatibility alias used by policy and fixture assertions."""
        return self.code


class DomainValidationError(DomainError, ValueError):
    """A value object or entity is malformed."""


class GuardRejected(DomainError):
    """A proposed state operation is not authorized for the current state."""


__all__ = ["DomainError", "DomainValidationError", "GuardRejected"]
