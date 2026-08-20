"""Stable identifiers for canonical records derived from a confirmed world seed."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5


def opening_location_claim_id(playthrough_id: str, branch_id: str, character_id: str) -> str:
    """Return the stable claim ID for a participant's opening location."""

    value = f"interactive-novel:{playthrough_id}:{branch_id}:opening:{character_id}:location"
    return str(uuid5(NAMESPACE_URL, value))


__all__ = ["opening_location_claim_id"]
