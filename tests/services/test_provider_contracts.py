from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from src.application.contracts.providers import (
    CancellationToken,
    LogicalRole,
    ProviderCancelledError,
    ProviderHTTPError,
    ProviderRequest,
    ProviderTarget,
    StructuredSchema,
)
from src.services.llm.base import BaseProvider
from src.services.llm.gemini import GeminiProvider
from src.services.llm.ollama import OllamaProvider
from src.services.llm.openrouter import OpenRouterProvider

ProviderClass = type[BaseProvider]
PROVIDERS: tuple[tuple[str, ProviderClass], ...] = (
    ("ollama", OllamaProvider),
    ("gemini", GeminiProvider),
    ("openrouter", OpenRouterProvider),
)


def _target(provider: str, *, max_retries: int = 1) -> ProviderTarget:
    base_urls = {
        "ollama": "http://provider.test/api",
        "gemini": "http://provider.test/v1beta",
        "openrouter": "http://provider.test/api/v1",
    }
    return ProviderTarget(
        name=provider,
        provider=provider,
        model="fixture-model",
        base_url=base_urls[provider],
        api_key_env=f"{provider.upper()}_API_KEY" if provider != "ollama" else None,
        api_key="fixture-secret" if provider != "ollama" else None,
        max_retries=max_retries,
        backoff_base_seconds=0,
    )


def _provider(provider: str, client: httpx.AsyncClient, *, max_retries: int = 1) -> BaseProvider:
    classes = dict(PROVIDERS)
    return classes[provider](_target(provider, max_retries=max_retries), client=client)


def _request(*, cancellation: CancellationToken | None = None, structured: StructuredSchema | None = None) -> ProviderRequest:
    return ProviderRequest(
        system_prompt="You are a fixture provider.",
        user_prompt="Return a small answer.",
        role=LogicalRole.WRITER,
        cancellation=cancellation,
        structured_schema=structured,
    )


def _text_payload(provider: str, text: str) -> dict[str, Any]:
    if provider == "ollama":
        return {"model": "fixture-model", "message": {"content": text}, "done": True}
    if provider == "gemini":
        return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}
    return {
        "id": "fixture-response",
        "model": "fixture-model",
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
    }


async def _response_handler(provider: str, request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=_text_payload(provider, "hello"), headers={"x-request-id": "request-1"})


@pytest.mark.parametrize("provider", [name for name, _ in PROVIDERS])
async def test_all_adapters_share_text_contract(provider: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return await _response_handler(provider, request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _provider(provider, client).generate_text(_request())

    assert result.provider == provider
    assert result.model == "fixture-model"
    assert result.text == "hello"
    assert result.request_id == "request-1"


@pytest.mark.parametrize("provider", [name for name, _ in PROVIDERS])
async def test_all_adapters_parse_and_repair_structured_output(provider: str) -> None:
    calls = 0
    schema = StructuredSchema(
        name="fixture_output",
        json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        validator=lambda payload: payload if payload.get("ok") is True else (_ for _ in ()).throw(ValueError()),
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        text = "not-json" if calls == 1 else '{"ok": true}'
        return httpx.Response(200, json=_text_payload(provider, text))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _provider(provider, client).generate_structured(_request(), schema)

    assert result.data == {"ok": True}
    assert result.repaired is True
    assert result.validation_attempts == 2
    assert calls == 2


@pytest.mark.parametrize("provider", [name for name, _ in PROVIDERS])
async def test_all_adapters_embed_and_check_connectivity(provider: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"models": []}, headers={"x-request-id": "health-1"})
        if provider == "ollama":
            payload = {"model": "fixture-model", "embeddings": [[0.1, 0.2]]}
        elif provider == "gemini":
            payload = {"embedding": {"values": [0.1, 0.2]}}
        else:
            payload = {"model": "fixture-model", "data": [{"embedding": [0.1, 0.2]}]}
        return httpx.Response(200, json=payload, headers={"x-request-id": "embed-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = _provider(provider, client)
        embeddings = await adapter.embed(["hello"])
        connectivity = await adapter.check_connectivity()

    assert embeddings.embeddings == ((0.1, 0.2),)
    assert embeddings.request_id == "embed-1"
    assert connectivity.reachable is True
    assert connectivity.request_id == "health-1"


@pytest.mark.parametrize("provider", [name for name, _ in PROVIDERS])
async def test_all_adapters_retry_rate_limit_and_timeout(provider: str) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": {"message": "rate limited"}}, headers={"retry-after": "0"})
        return httpx.Response(200, json=_text_payload(provider, "after-retry"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _provider(provider, client).generate_text(_request())

    assert result.text == "after-retry"
    assert result.retry_count == 1
    assert calls == 2

    timeout_calls = 0

    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_calls
        timeout_calls += 1
        if timeout_calls == 1:
            raise httpx.ReadTimeout("fixture timeout", request=request)
        return httpx.Response(200, json=_text_payload(provider, "after-timeout"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        result = await _provider(provider, client).generate_text(_request())

    assert result.text == "after-timeout"
    assert timeout_calls == 2


class _InterruptedStream(httpx.AsyncByteStream):
    def __init__(self, first_chunk: bytes) -> None:
        self._first_chunk = first_chunk

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self._first_chunk
        raise httpx.ReadError("fixture stream interruption")

    async def aclose(self) -> None:
        return None


def _stream_chunk(provider: str) -> bytes:
    if provider == "ollama":
        return b'{"model":"fixture-model","message":{"content":"hello"},"done":false}\n'
    if provider == "gemini":
        return b'data: {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}\n\n'
    return b'data: {"model":"fixture-model","choices":[{"delta":{"content":"hello"}}]}\n\n'


@pytest.mark.parametrize("provider", [name for name, _ in PROVIDERS])
async def test_stream_interruption_is_not_retried_after_partial_output(provider: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=_InterruptedStream(_stream_chunk(provider)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = _provider(provider, client, max_retries=2)
        stream = adapter.stream_text(_request())
        first = await anext(stream)
        with pytest.raises(Exception, match="stream request failed|stream interruption"):
            await anext(stream)

    assert first.text == "hello"


@pytest.mark.parametrize("provider", [name for name, _ in PROVIDERS])
async def test_cancellation_is_honored_before_network_call(provider: str) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_text_payload(provider, "unexpected"))

    token = CancellationToken()
    token.cancel()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderCancelledError):
            await _provider(provider, client).generate_text(_request(cancellation=token))

    assert calls == 0


def test_provider_config_snapshot_excludes_secrets() -> None:
    target = ProviderTarget(
        name="cloud",
        provider="gemini",
        model="fixture-model",
        api_key="super-secret",
        api_key_env="GEMINI_API_KEY",
        headers={"Authorization": "Bearer super-secret"},
    )

    snapshot = json.dumps(target.snapshot(), sort_keys=True)

    assert "super-secret" not in snapshot
    assert "Authorization" in snapshot


async def test_async_client_lifecycle_and_error_redaction() -> None:
    target = _target("gemini", max_retries=0)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "provider echoed fixture-secret"}})

    external_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GeminiProvider(target, client=external_client)
    with pytest.raises(ProviderHTTPError) as error_info:
        await adapter.generate_text(_request())

    assert "fixture-secret" not in str(error_info.value)
    await adapter.aclose()
    assert external_client.is_closed is False
    await external_client.aclose()

    owned_adapter = GeminiProvider(target)
    owned_client = await owned_adapter._get_client()
    assert owned_client.is_closed is False
    await owned_adapter.aclose()
    assert owned_client.is_closed is True
