"""Local JSONL feedback storage with input bounds and secret redaction."""

from __future__ import annotations

import json
from pathlib import Path

from src.application.contracts.feedback import FeedbackRecord
from src.services.llm.base import redact_secret


class JsonlFeedbackStore:
    def __init__(self, path: Path, *, max_comment_chars: int = 4_000) -> None:
        if max_comment_chars < 1:
            raise ValueError("max_comment_chars must be positive")
        self.path = path.expanduser().resolve()
        self.max_comment_chars = max_comment_chars

    def append(self, record: FeedbackRecord) -> None:
        comment = redact_secret(" ".join(record.comment.split()), max_length=None)[: self.max_comment_chars]
        payload = {**record.as_dict(), "comment": comment}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


__all__ = ["JsonlFeedbackStore"]
