"""Provider adapter for the transient AI World Builder draft."""

from __future__ import annotations

import json
from uuid import uuid4

from src.application.contracts.ai import AIPromptRole, WorldSeed
from src.application.contracts.providers import ProviderRequest
from src.application.ports.providers import ProviderGateway
from src.services.ai.contracts import AIContractRegistry
from src.services.prompts import PromptRegistry


class ProviderWorldDraftGenerator:
    """Turn a natural-language request into a validated, non-persistent WorldSeed."""

    def __init__(
        self,
        provider: ProviderGateway,
        *,
        prompts: PromptRegistry | None = None,
        contracts: AIContractRegistry | None = None,
    ) -> None:
        self._provider = provider
        self._prompts = prompts or PromptRegistry()
        self._contracts = contracts or AIContractRegistry()

    async def generate_world_draft(self, prompt: str) -> WorldSeed:
        definition = self._prompts.get(AIPromptRole.WORLD_BUILDER)
        run_id = str(uuid4())
        physical_call_id = str(uuid4())
        input_envelope = {
            "schema_version": "world-builder-input-1",
            "role": AIPromptRole.WORLD_BUILDER.value,
            "run_id": run_id,
            "template": "school_romance",
            "prompt": prompt.strip(),
            "presets": {
                "tone": "warm, reflective",
                "rating": "teen_14_plus",
                "violence_ceiling": "none",
                "adult_explicit_opt_in": False,
            },
        }
        request = ProviderRequest(
            system_prompt=(
                "You are the local-first World Builder. Return only a strict JSON object; "
                "the result is a draft and has no persistence authority."
            ),
            user_prompt=definition.render({"input_json": json.dumps(input_envelope, ensure_ascii=False, sort_keys=True)}),
            role=AIPromptRole.WORLD_BUILDER,
            physical_call_id=physical_call_id,
            logical_roles=(AIPromptRole.WORLD_BUILDER,),
            temperature=0.4,
            max_output_tokens=16_000,
            metadata={
                "prompt_version": definition.semantic_version,
                "output_schema_version": definition.output_schema_version,
                "template_hash": definition.template_hash,
            },
        )
        response = await self._provider.generate_structured(
            request,
            self._contracts.structured_schema(
                AIPromptRole.WORLD_BUILDER,
                authoritative_metadata={
                    "schema_version": definition.output_schema_version,
                    "role": AIPromptRole.WORLD_BUILDER.value,
                    "run_id": run_id,
                    "prompt_version": definition.semantic_version,
                    "physical_call_id": physical_call_id,
                },
            ),
        )
        if isinstance(response.data, WorldSeed):
            return response.data
        return self._contracts.parse(AIPromptRole.WORLD_BUILDER, response.data)  # type: ignore[return-value]


__all__ = ["ProviderWorldDraftGenerator"]
