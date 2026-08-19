"""Application use case for explicit, bounded alpha feedback."""

from __future__ import annotations

from datetime import UTC, datetime

from src.application.contracts.feedback import FeedbackRecord
from src.application.ports.feedback import FeedbackStore


class FeedbackApplicationService:
    def __init__(self, store: FeedbackStore) -> None:
        self._store = store

    def submit(
        self,
        *,
        rating: int,
        comment: str = "",
        category: str = "general",
        turn_run_id: str | None = None,
    ) -> FeedbackRecord:
        record = FeedbackRecord(
            rating=rating,
            comment=comment,
            category=category,
            created_at=datetime.now(UTC),
            turn_run_id=turn_run_id,
        )
        self._store.append(record)
        return record


__all__ = ["FeedbackApplicationService"]
