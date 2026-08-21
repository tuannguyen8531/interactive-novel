"""Explicit alpha feedback contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class FeedbackRecord:
    rating: int
    comment: str
    category: str
    created_at: datetime
    turn_run_id: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.rating <= 5:
            raise ValueError("feedback rating must be between 1 and 5")
        if self.created_at.tzinfo is None:
            raise ValueError("feedback timestamp must be timezone-aware")
        if not self.category.strip():
            raise ValueError("feedback category cannot be blank")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "feedback",
            "rating": self.rating,
            "comment": self.comment,
            "category": self.category,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "turn_run_id": self.turn_run_id,
        }


__all__ = ["FeedbackRecord"]
