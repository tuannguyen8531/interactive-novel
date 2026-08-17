"""Ollama REST adapter."""

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
    TokenUsage,
)

from .base import BaseProvider


class OllamaProvider(BaseProvider):
    """Local-first Ollama adapter using `/api/chat` and `/api/embed`."""

    default_base_url = "http://localhost:11434/api"

    def __init__(self, target: ProviderTarget | None = None, **kwargs: Any) -> None:
        super().__init__(
            target
            or ProviderTarget(
                name="ollama",
                provider="ollama",
                model="gemma3",
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

    def _chat_payload(self, request: ProviderRequest, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": stream,
        }
        options: dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            options["num_predict"] = request.max_output_tokens
        if options:
            payload["options"] = options
        if request.structured_schema is not None:
            payload["format"] = dict(request.structured_schema.json_schema) or "json"
            payload["think"] = False
        return payload

    async def _generate_text_once(self, request: ProviderRequest) -> ProviderResponse:
        started = time.monotonic()
        response, payload = await self._request_json(
            "POST",
            f"{self.base_url}/chat",
            request=request,
            payload=self._chat_payload(request, stream=False),
        )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("message"), Mapping):
            raise ProviderProtocolError(
                "Ollama response did not contain a message.",
                provider=self.provider_name,
                fallback_eligible=True,
                request_id=self._request_id(response),
            )
        message = payload["message"]
        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderProtocolError(
                "Ollama response message did not contain text.",
                provider=self.provider_name,
                fallback_eligible=True,
                request_id=self._request_id(response),
            )
        prompt_tokens = _int(payload.get("prompt_eval_count"))
        completion_tokens = _int(payload.get("eval_count"))
        usage: TokenUsage | None = None
        if prompt_tokens is not None or completion_tokens is not None:
            usage = TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        return ProviderResponse(
            provider=self.provider_name,
            model=str(payload.get("model", request.model or self.model)),
            role=request.role,
            physical_call_id=request.physical_call_id,
            text=content.strip(),
            request_id=self._request_id(response),
            usage=usage,
            finish_reason=str(payload.get("done_reason")) if payload.get("done_reason") else None,
            latency_ms=(time.monotonic() - started) * 1000,
        )

    async def _stream_text_once(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]:
        index = 0
        async with self._stream_request(
            "POST",
            f"{self.base_url}/chat",
            request=request,
            payload=self._chat_payload(request, stream=True),
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ProviderProtocolError(
                        "Ollama stream contained invalid JSON.",
                        provider=self.provider_name,
                        fallback_eligible=True,
                        request_id=self._request_id(response),
                    ) from error
                if not isinstance(payload, Mapping):
                    continue
                message = payload.get("message")
                text = message.get("content", "") if isinstance(message, Mapping) else ""
                if not isinstance(text, str):
                    text = ""
                done = bool(payload.get("done", False))
                yield StreamChunk(
                    provider=self.provider_name,
                    model=str(payload.get("model", request.model or self.model)),
                    role=request.role,
                    physical_call_id=request.physical_call_id,
                    text=text,
                    index=index,
                    done=done,
                    request_id=self._request_id(response),
                    finish_reason=str(payload.get("done_reason")) if payload.get("done_reason") else None,
                    usage=TokenUsage(
                        prompt_tokens=_int(payload.get("prompt_eval_count")),
                        completion_tokens=_int(payload.get("eval_count")),
                    )
                    if done
                    else None,
                )
                index += 1
                if done:
                    return

    async def _embed_once(self, texts: Sequence[str], *, model: str | None) -> EmbeddingResponse:
        started = time.monotonic()
        response, payload = await self._request_json(
            "POST",
            f"{self.base_url}/embed",
            payload={"model": model or self.model, "input": list(texts)},
        )
        embeddings = payload.get("embeddings") if isinstance(payload, Mapping) else None
        if not isinstance(embeddings, list) or not all(isinstance(item, list) for item in embeddings):
            raise ProviderProtocolError(
                "Ollama embedding response did not contain vectors.",
                provider=self.provider_name,
                fallback_eligible=True,
                request_id=self._request_id(response),
            )
        return EmbeddingResponse(
            provider=self.provider_name,
            model=str(payload.get("model", model or self.model)),
            embeddings=tuple(tuple(float(value) for value in item) for item in embeddings),
            request_id=self._request_id(response),
            latency_ms=(time.monotonic() - started) * 1000,
        )

    async def _check_connectivity_once(self) -> tuple[int, str | None]:
        response, _ = await self._request_json("GET", f"{self.base_url}/tags")
        return response.status_code, self._request_id(response)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["OllamaProvider"]
