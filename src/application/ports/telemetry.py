"""Inward port for recording optional provider telemetry."""

from __future__ import annotations

from typing import Protocol

from src.application.contracts.ai import LLMRunTrace


class TelemetryRecorderPort(Protocol):
    """The graph may emit trace metadata without knowing its storage policy."""

    def record(self, trace: LLMRunTrace) -> None:
        """Record one secret-safe trace, or ignore it when telemetry is disabled."""
        ...


__all__ = ["TelemetryRecorderPort"]
