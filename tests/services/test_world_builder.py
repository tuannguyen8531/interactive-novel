from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.application.contracts.ai import AIPromptRole, WorldSeed
from src.application.contracts.providers import ProviderResponse, StructuredResponse
from src.services.ai.world_builder import ProviderWorldDraftGenerator

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ai" / "role_outputs.json"


class _Provider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.request: Any = None

    async def generate_structured(self, request: Any, schema: Any) -> StructuredResponse:
        self.request = request
        response = ProviderResponse(
            provider="fixture",
            model="fixture-model",
            role=request.role,
            physical_call_id=request.physical_call_id,
            text=json.dumps(self.payload),
        )
        return StructuredResponse(response=response, data=schema.validate(self.payload, provider="fixture"))


@pytest.mark.asyncio
async def test_provider_world_builder_renders_versioned_school_romance_prompt() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["world_builder"]
    provider = _Provider(payload)
    generator = ProviderWorldDraftGenerator(provider)  # type: ignore[arg-type]

    result = await generator.generate_world_draft("A quiet club prepares for a festival.")

    assert isinstance(result, WorldSeed)
    assert result.title == "The Quiet Courtyard"
    assert provider.request.role == AIPromptRole.WORLD_BUILDER
    assert '"template": "school_romance"' in provider.request.user_prompt
    assert '"player_character"' in provider.request.user_prompt
    assert '"opening_scene"' in provider.request.user_prompt
    assert provider.request.metadata["output_schema_version"] == "world-seed-1"
    assert result.prompt_version == "1.1.0"
    assert result.run_id != payload["run_id"]
