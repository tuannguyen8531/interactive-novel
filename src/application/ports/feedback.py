"""Inward storage port for explicit alpha feedback."""

from __future__ import annotations

from typing import Protocol

from src.application.contracts.feedback import FeedbackRecord


class FeedbackStore(Protocol):
    def append(self, record: FeedbackRecord) -> None:
        """Store one already-redacted feedback record."""
        ...


__all__ = ["FeedbackStore"]
