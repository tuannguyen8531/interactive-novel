"""JSON conversion helpers for persistence-neutral application records."""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder


def public_json(value: Any) -> Any:
    """Encode dataclasses and typed records without returning ORM objects."""
    return jsonable_encoder(value)


__all__ = ["public_json"]
