"""Pydantic contracts exposed by the Phase 1 API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Public liveness response."""

    status: Literal["ok"]
    service: str
    version: str


class ErrorPayload(BaseModel):
    """Stable machine-readable error body."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Top-level API error envelope."""

    error: ErrorPayload


__all__ = ["ErrorEnvelope", "ErrorPayload", "HealthResponse"]
