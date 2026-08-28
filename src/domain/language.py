"""Supported languages for player-facing story content."""

from __future__ import annotations

from enum import StrEnum


class StoryLanguage(StrEnum):
    """A stable language code persisted with a story world.

    The UI may remain English; this value controls narrative content produced
    for the player, including names, prose, dialogue and suggested actions.
    """

    ENGLISH = "en"
    VIETNAMESE = "vi"


__all__ = ["StoryLanguage"]
