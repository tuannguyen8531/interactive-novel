"""OpenRouter OpenAI-compatible REST adapter."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from src.application.contracts.providers import (
    EmbeddingResponse,
    ProviderCapability,
    ProviderProtocolError,
    ProviderRequest,
    ProviderResponse,
    ProviderTarget,
    StreamChunk,
)

from .base import BaseProvider


class OpenRouterProvider(BaseProvider):
    """OpenRouter chat completions, SSE streaming and embeddings adapter."""

    default_base_url = "https://openrouter.ai/api/v1"

    def __init__(self, target: ProviderTarget | None = None, **kwargs: Any) -> None:
        super().__init__(
            target
            or ProviderTarget(
                name="openrouter",
                provider="openrouter",
                model="openai/gpt-4o-mini",
                api_key_env="OPENROUTER_API_KEY",
                base_url=self.default_base_url,
            ),
            **kwargs,
        )

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset(
            {
                ProviderCapability.TEXT,
                ProviderCapability.STRUCTURED,
                ProviderCapability.STREAM,
                ProviderCapability.EMBEDDING,
            }
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key('OPENROUTER_API_KEY')}"}

    def _chat_payload(self, request: ProviderRequest, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        if request.structured_schema is not None:
            if request.structured_schema.json_schema:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": request.structured_schema.name,
                        "strict": True,
                        "schema": dict(request.structured_schema.json_schema),
                    },
                }
            else:
                payload["response_format"] = {"type": "json_object"}
        return payload

    async def _generate_text_once(self, request: ProviderRequest) -> ProviderResponse:
        started = time.monotonic()
        response, payload = await self._request_json(
            "POST",
            f"{self.base_url}/chat/completions",
            request=request,
            headers=self._headers(),
            payload=self._chat_payload(request, stream=False),
        )
        text, finish_reason = _choice_text(payload, self.provider_name, self._request_id(response))
        return ProviderResponse(
            provider=self.provider_name,
            model=str(payload.get("model", request.model or self.model)),
            role=request.role,
            physical_call_id=request.physical_call_id,
            text=text,
            request_id=self._request_id(response),
            usage=self._usage(payload),
            finish_reason=finish_reason,
            latency_ms=(time.monotonic() - started) * 1000,
        )

    async def _stream_text_once(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]:
        model = request.model or self.model
        index = 0
        async with self._stream_request(
            "POST",
            f"{self.base_url}/chat/completions",
            request=request,
            headers=self._headers(),
            payload=self._chat_payload(request, stream=True),
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                if raw == "[DONE]":
                    yield StreamChunk(
                        provider=self.provider_name,
                        model=model,
                        role=request.role,
                        physical_call_id=request.physical_call_id,
                        text="",
                        index=index,
                        done=True,
                        request_id=self._request_id(response),
                    )
                    return
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as error:
                    raise ProviderProtocolError(
                        "OpenRouter stream contained invalid JSON.",
                        provider=self.provider_name,
                        fallback_eligible=True,
                        request_id=self._request_id(response),
                    ) from error
                if not isinstance(payload, Mapping):
                    continue
                choices = payload.get("choices")
                choice = choices[0] if isinstance(choices, list) and choices else {}
                delta = choice.get("delta", {}) if isinstance(choice, Mapping) else {}
                text = delta.get("content", "") if isinstance(delta, Mapping) else ""
                finish_reason = choice.get("finish_reason") if isinstance(choice, Mapping) else None
                yield StreamChunk(
                    provider=self.provider_name,
                    model=str(payload.get("model", model)),
                    role=request.role,
                    physical_call_id=request.physical_call_id,
                    text=text if isinstance(text, str) else "",
                    index=index,
                    done=finish_reason is not None,
                    request_id=self._request_id(response),
                    finish_reason=str(finish_reason) if finish_reason else None,
                    usage=self._usage(payload),
                )
                index += 1

    async def _embed_once(self, texts: Sequence[str], *, model: str | None) -> EmbeddingResponse:
        started = time.monotonic()
        response, payload = await self._request_json(
            "POST",
            f"{self.base_url}/embeddings",
            headers=self._headers(),
            payload={"model": model or self.model, "input": list(texts)},
        )
        data = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(data, list):
            raise ProviderProtocolError(
                "OpenRouter embedding response did not contain data.",
                provider=self.provider_name,
                fallback_eligible=True,
                request_id=self._request_id(response),
            )
        vectors: list[tuple[float, ...]] = []
        for item in data:
            values = item.get("embedding") if isinstance(item, Mapping) else None
            if not isinstance(values, list):
                raise ProviderProtocolError(
                    "OpenRouter embedding item did not contain a vector.",
                    provider=self.provider_name,
                    fallback_eligible=True,
                    request_id=self._request_id(response),
                )
            vectors.append(tuple(float(value) for value in values))
        return EmbeddingResponse(
            provider=self.provider_name,
            model=str(payload.get("model", model or self.model)),
            embeddings=tuple(vectors),
            request_id=self._request_id(response),
            latency_ms=(time.monotonic() - started) * 1000,
        )

    async def _check_connectivity_once(self) -> tuple[int, str | None]:
        response, _ = await self._request_json("GET", f"{self.base_url}/models", headers=self._headers())
        return response.status_code, self._request_id(response)


def _choice_text(payload: Any, provider: str, request_id: str | None) -> tuple[str, str | None]:
    if not isinstance(payload, Mapping):
        raise ProviderProtocolError("OpenRouter response was not an object.", provider=provider, request_id=request_id)
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        raise ProviderProtocolError(
            "OpenRouter response did not contain choices.",
            provider=provider,
            fallback_eligible=True,
            request_id=request_id,
        )
    message = choices[0].get("message")
    text = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(text, str):
        raise ProviderProtocolError(
            "OpenRouter choice did not contain text.",
            provider=provider,
            fallback_eligible=True,
            request_id=request_id,
        )
    finish_reason = choices[0].get("finish_reason")
    return text.strip(), str(finish_reason) if finish_reason else None


__all__ = ["OpenRouterProvider"]
