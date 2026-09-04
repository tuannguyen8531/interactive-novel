"""Canonical locations discovered while a story unfolds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Location:
    """A stable, story-facing place registered in one canonical branch."""

    location_id: str
    name: str
    description: str


__all__ = ["Location"]
