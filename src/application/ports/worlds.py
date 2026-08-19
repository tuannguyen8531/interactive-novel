"""Port for the provider-backed world draft generator."""

from __future__ import annotations

from typing import Protocol

from src.application.contracts.ai import WorldSeed


class WorldDraftGenerator(Protocol):
    async def generate_world_draft(self, prompt: str) -> WorldSeed: ...


__all__ = ["WorldDraftGenerator"]
