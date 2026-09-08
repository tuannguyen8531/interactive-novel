"""Build secret-safe LLM run metadata from provider and prompt contracts."""

from __future__ import annotations

from src.application.contracts.ai import AIPromptRole, LLMRunTrace, ParseStatus, TokenUsageSnapshot
from src.application.contracts.providers import ProviderResponse
from src.services.prompts.registry import PromptDefinition


def build_llm_run_trace(
    response: ProviderResponse,
    *,
    run_id: str,
    role: AIPromptRole | str,
    prompt: PromptDefinition,
    config_snapshot_id: str | None = None,
    parse_status: ParseStatus = "not_parsed",
) -> LLMRunTrace:
    """Join provider metadata with prompt/schema versions for later persistence."""

    usage = response.usage
    token_usage = (
        TokenUsageSnapshot(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )
        if usage is not None
        else None
    )
    return LLMRunTrace(
        run_id=run_id,
        logical_role=AIPromptRole(role),
        physical_call_id=response.physical_call_id,
        provider=response.provider,
        model=response.model,
        request_id=response.request_id,
        prompt_version=prompt.semantic_version,
        template_hash=prompt.template_hash,
        output_schema_version=prompt.output_schema_version,
        config_snapshot_id=config_snapshot_id,
        latency_ms=response.latency_ms,
        token_usage=token_usage,
        finish_reason=response.finish_reason,
        retry_count=response.retry_count,
        fallback_from=response.fallback_from,
        parse_status=parse_status,
    )


__all__ = ["build_llm_run_trace"]
