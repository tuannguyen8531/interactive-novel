"""Google Gemini REST adapter."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from src.application.contracts.providers import (
    EmbeddingResponse,
    ProviderCapability,
    ProviderProtocolError,
    ProviderRefusalError,
    ProviderRequest,
    ProviderResponse,
    ProviderTarget,
    StreamChunk,
)

from .base import BaseProvider


class GeminiProvider(BaseProvider):
    """Gemini `generateContent`, SSE streaming and `embedContent` adapter."""

    default_base_url = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, target: ProviderTarget | None = None, **kwargs: Any) -> None:
        super().__init__(
            target
            or ProviderTarget(
                name="gemini",
                provider="gemini",
                model="gemini-2.5-flash",
                api_key_env="GEMINI_API_KEY",
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
        return {"x-goog-api-key": self._api_key("GEMINI_API_KEY")}

    def _generate_payload(self, request: ProviderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": {},
        }
        if request.system_prompt.strip():
            payload["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}
        generation_config = payload["generationConfig"]
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_output_tokens
        if request.structured_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            if request.structured_schema.json_schema:
                generation_config["responseJsonSchema"] = dict(request.structured_schema.json_schema)
        return payload

    def _model_url(self, model: str, action: str) -> str:
        return f"{self.base_url}/models/{model}:{action}"

    def _model_resource_url(self, model: str) -> str:
        return f"{self.base_url}/models/{model}"

    async def _generate_text_once(self, request: ProviderRequest) -> ProviderResponse:
        started = time.monotonic()
        model = request.model or self.model
        response, payload = await self._request_json(
            "POST",
            self._model_url(model, "generateContent"),
            request=request,
            headers=self._headers(),
            payload=self._generate_payload(request),
        )
        text, finish_reason = _candidate_text(payload, self.provider_name, self._request_id(response))
        return ProviderResponse(
            provider=self.provider_name,
            model=model,
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
            self._model_url(model, "streamGenerateContent"),
            request=request,
            headers=self._headers(),
            params={"alt": "sse"},
            payload=self._generate_payload(request),
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as error:
                    raise ProviderProtocolError(
                        "Gemini stream contained invalid JSON.",
                        provider=self.provider_name,
                        fallback_eligible=True,
                        request_id=self._request_id(response),
                    ) from error
                text, finish_reason = _candidate_text(payload, self.provider_name, self._request_id(response))
                yield StreamChunk(
                    provider=self.provider_name,
                    model=model,
                    role=request.role,
                    physical_call_id=request.physical_call_id,
                    text=text,
                    index=index,
                    done=finish_reason is not None,
                    request_id=self._request_id(response),
                    finish_reason=finish_reason,
                    usage=self._usage(payload),
                )
                index += 1

    async def _embed_once(self, texts: Sequence[str], *, model: str | None) -> EmbeddingResponse:
        started = time.monotonic()
        vectors: list[tuple[float, ...]] = []
        selected_model = model or self.model
        request_id: str | None = None
        for text in texts:
            response, payload = await self._request_json(
                "POST",
                self._model_url(selected_model, "embedContent"),
                headers=self._headers(),
                payload={"content": {"parts": [{"text": text}]}},
            )
            request_id = self._request_id(response) or request_id
            embedding = payload.get("embedding") if isinstance(payload, Mapping) else None
            values = embedding.get("values") if isinstance(embedding, Mapping) else None
            if not isinstance(values, list):
                raise ProviderProtocolError(
                    "Gemini embedding response did not contain values.",
                    provider=self.provider_name,
                    fallback_eligible=True,
                    request_id=request_id,
                )
            vectors.append(tuple(float(value) for value in values))
        return EmbeddingResponse(
            provider=self.provider_name,
            model=selected_model,
            embeddings=tuple(vectors),
            request_id=request_id,
            latency_ms=(time.monotonic() - started) * 1000,
        )

    async def _check_connectivity_once(self) -> tuple[int, str | None]:
        response, _ = await self._request_json(
            "GET",
            self._model_resource_url(self.model),
            headers=self._headers(),
        )
        return response.status_code, self._request_id(response)


def _candidate_text(payload: Any, provider: str, request_id: str | None) -> tuple[str, str | None]:
    if not isinstance(payload, Mapping):
        raise ProviderProtocolError("Gemini response was not an object.", provider=provider, request_id=request_id)
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        feedback = payload.get("promptFeedback")
        reason = feedback.get("blockReason") if isinstance(feedback, Mapping) else None
        if reason:
            raise ProviderRefusalError(
                f"Gemini refused the request: {reason}.",
                provider=provider,
                request_id=request_id,
            )
        raise ProviderProtocolError(
            "Gemini response did not contain candidates.",
            provider=provider,
            fallback_eligible=True,
            request_id=request_id,
        )
    candidate = candidates[0]
    if not isinstance(candidate, Mapping):
        raise ProviderProtocolError("Gemini candidate was malformed.", provider=provider, request_id=request_id)
    content = candidate.get("content")
    parts = content.get("parts", []) if isinstance(content, Mapping) else []
    text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, Mapping) and not part.get("thought", False))
    finish_reason = candidate.get("finishReason")
    if not text and finish_reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"}:
        raise ProviderRefusalError(
            f"Gemini refused the request: {finish_reason}.",
            provider=provider,
            request_id=request_id,
        )
    return text.strip(), str(finish_reason) if finish_reason else None


__all__ = ["GeminiProvider"]
