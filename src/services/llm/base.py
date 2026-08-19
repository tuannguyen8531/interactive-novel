"""Shared async HTTP lifecycle, retry and response handling for providers."""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any, TypeVar

import httpx

from src.application.contracts.providers import (
    CancellationToken,
    ConnectivityResult,
    EmbeddingResponse,
    ProviderCapability,
    ProviderCapabilityError,
    ProviderConfigurationError,
    ProviderError,
    ProviderHTTPError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRequest,
    ProviderResponse,
    ProviderTarget,
    ProviderTimeoutError,
    ProviderTransportError,
    StreamChunk,
    StructuredOutputError,
    StructuredResponse,
    StructuredSchema,
    TokenUsage,
)

from .structured import parse_structured_text

T = TypeVar("T")
_SECRET_PATTERN = re.compile(
    r"(?ix)"
    r"(bearer\s+|api[_-]?key[=:]\s*)([^\s,;]+)"
    r"|(\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,})\b)"
)


def redact_secret(value: str, *, max_length: int | None = 500) -> str:
    """Remove common bearer/API-key forms before an error reaches logs."""
    redacted = _SECRET_PATTERN.sub(lambda match: f"{match.group(1) or ''}[REDACTED]", value)
    return redacted if max_length is None else redacted[:max_length]


class BaseProvider(ABC):
    """Provider adapter base implementing the inward-facing provider port."""

    default_base_url = ""

    def __init__(
        self,
        target: ProviderTarget,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.target = target
        self._client = client
        self._owns_client = client is None
        self._sleep = sleep or asyncio.sleep

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[ProviderCapability]:
        """Capabilities guaranteed by this adapter."""
        ...

    @property
    def provider_name(self) -> str:
        return self.target.provider_name

    @property
    def model(self) -> str:
        return self.target.model

    @property
    def base_url(self) -> str:
        return (self.target.base_url or self.default_base_url).rstrip("/")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.target.timeout_seconds)
        return self._client

    def _request_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", **self.target.headers}

    def _raise_capability(self, capability: ProviderCapability) -> None:
        if capability not in self.capabilities:
            raise ProviderCapabilityError(
                f"{self.provider_name} does not support {capability.value}.",
                provider=self.provider_name,
            )

    def _check_cancelled(self, request: ProviderRequest | None = None) -> None:
        if request is not None and request.cancellation is not None:
            request.cancellation.raise_if_cancelled(provider=self.provider_name)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        request: ProviderRequest | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[httpx.Response, Any]:
        self._check_cancelled(request)
        client = await self._get_client()
        try:
            response = await client.request(
                method,
                url,
                headers={**self._request_headers(), **(headers or {})},
                params=params,
                json=payload,
            )
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError(
                f"{self.provider_name} request timed out.",
                provider=self.provider_name,
                retryable=True,
                fallback_eligible=True,
            ) from error
        except httpx.RequestError as error:
            raise ProviderTransportError(
                f"{self.provider_name} network request failed.",
                provider=self.provider_name,
                retryable=True,
                fallback_eligible=True,
            ) from error
        self._raise_for_status(response)
        try:
            return response, response.json()
        except (TypeError, ValueError) as error:
            raise ProviderProtocolError(
                f"{self.provider_name} returned a non-JSON response.",
                provider=self.provider_name,
                fallback_eligible=True,
                request_id=self._request_id(response),
            ) from error

    @asynccontextmanager
    async def _stream_request(
        self,
        method: str,
        url: str,
        *,
        request: ProviderRequest,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[httpx.Response]:
        self._check_cancelled(request)
        client = await self._get_client()
        try:
            async with client.stream(
                method,
                url,
                headers={**self._request_headers(), **(headers or {})},
                params=params,
                json=payload,
            ) as response:
                self._raise_for_status(response)
                yield response
        except ProviderError:
            raise
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError(
                f"{self.provider_name} stream timed out.",
                provider=self.provider_name,
                retryable=True,
                fallback_eligible=True,
            ) from error
        except httpx.RequestError as error:
            raise ProviderTransportError(
                f"{self.provider_name} stream request failed.",
                provider=self.provider_name,
                retryable=True,
                fallback_eligible=True,
            ) from error

    async def _with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        cancellation: CancellationToken | None = None,
    ) -> tuple[T, int]:
        for attempt in range(self.target.max_retries + 1):
            if cancellation is not None:
                cancellation.raise_if_cancelled(provider=self.provider_name)
            try:
                result = await operation()
                return result, attempt
            except ProviderError as error:
                if not error.retryable or attempt >= self.target.max_retries:
                    raise error.with_attempts(attempt + 1) from error
                delay = self._retry_delay(error, attempt)
                await self._sleep(delay)
                if cancellation is not None:
                    cancellation.raise_if_cancelled(provider=self.provider_name)
        raise AssertionError("retry loop must return or raise")

    async def generate_text(self, request: ProviderRequest) -> ProviderResponse:
        self._raise_capability(ProviderCapability.TEXT)
        result, retry_count = await self._with_retry(
            lambda: self._generate_text_once(request),
            cancellation=request.cancellation,
        )
        return replace(result, retry_count=retry_count)

    async def generate_structured(
        self,
        request: ProviderRequest,
        schema: StructuredSchema,
    ) -> StructuredResponse:
        self._raise_capability(ProviderCapability.STRUCTURED)
        structured_request = replace(request, structured_schema=schema)
        response = await self.generate_text(structured_request)
        try:
            data = parse_structured_text(response.text, schema, provider=self.provider_name)
            return StructuredResponse(response=response, data=data)
        except StructuredOutputError as first_error:
            if request.repair_attempt >= 1:
                raise first_error
            repair_request = replace(
                structured_request,
                system_prompt=(
                    "Return only valid JSON matching the requested schema. Do not include Markdown fences or commentary."
                ),
                user_prompt=(f"Repair this invalid structured response for schema {schema.name}:\n{response.text}"),
                repair_attempt=1,
            )
            repaired_response = await self.generate_text(repair_request)
            try:
                repaired_data = parse_structured_text(
                    repaired_response.text,
                    schema,
                    provider=self.provider_name,
                )
            except StructuredOutputError as error:
                raise error from first_error
            return StructuredResponse(
                response=repaired_response,
                data=repaired_data,
                repaired=True,
                validation_attempts=2,
            )

    async def _stream_with_retry(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]:
        self._raise_capability(ProviderCapability.STREAM)
        emitted = False
        for attempt in range(self.target.max_retries + 1):
            try:
                async for chunk in self._stream_text_once(request):
                    self._check_cancelled(request)
                    emitted = True
                    yield replace(chunk, retry_count=attempt)
                return
            except ProviderError as error:
                if emitted or not error.retryable or attempt >= self.target.max_retries:
                    raise error.with_attempts(attempt + 1) from error
                delay = self._retry_delay(error, attempt)
                self._check_cancelled(request)
                await self._sleep(delay)
                self._check_cancelled(request)

    def stream_text(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]:
        return self._stream_with_retry(request)

    async def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResponse:
        self._raise_capability(ProviderCapability.EMBEDDING)
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Embedding input must contain non-empty texts.")
        result, retry_count = await self._with_retry(lambda: self._embed_once(tuple(texts), model=model))
        return replace(result, retry_count=retry_count)

    async def check_connectivity(self) -> ConnectivityResult:
        started = time.monotonic()
        try:
            status_code, request_id = await self._check_connectivity_once()
            return ConnectivityResult(
                provider=self.provider_name,
                model=self.model,
                reachable=True,
                latency_ms=(time.monotonic() - started) * 1000,
                status_code=status_code,
                request_id=request_id,
            )
        except ProviderError as error:
            return ConnectivityResult(
                provider=self.provider_name,
                model=self.model,
                reachable=False,
                latency_ms=(time.monotonic() - started) * 1000,
                status_code=error.status_code,
                message=str(error),
                request_id=error.request_id,
            )

    async def aclose(self) -> None:
        if self._client is None:
            return
        if self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BaseProvider:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        status = response.status_code
        request_id = self._request_id(response)
        message = self._safe_error_message(response)
        retry_after = self._retry_after(response)
        if status == 429:
            raise ProviderRateLimitError(
                f"{self.provider_name} rate limit exceeded.",
                provider=self.provider_name,
                retryable=True,
                fallback_eligible=True,
                status_code=status,
                request_id=request_id,
                retry_after_seconds=retry_after,
            )
        if status in {401, 403}:
            raise ProviderConfigurationError(
                f"{self.provider_name} authentication or permission failed.",
                provider=self.provider_name,
                status_code=status,
                request_id=request_id,
            )
        retryable = status == 408 or status >= 500
        raise ProviderHTTPError(
            f"{self.provider_name} request failed with HTTP {status}: {message}",
            provider=self.provider_name,
            retryable=retryable,
            fallback_eligible=retryable,
            status_code=status,
            request_id=request_id,
            retry_after_seconds=retry_after,
        )

    def _retry_delay(self, error: ProviderError, attempt: int) -> float:
        if error.retry_after_seconds is not None:
            return error.retry_after_seconds
        maximum = self.target.backoff_base_seconds * (2**attempt)
        return random.uniform(0.0, maximum) if maximum > 0 else 0.0

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        for name in ("x-request-id", "request-id", "x-generation-id"):
            value = response.headers.get(name)
            if value:
                return value
        return None

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    def _safe_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, Mapping):
                error = payload.get("error")
                if isinstance(error, Mapping):
                    return self._redact_known_secrets(str(error.get("message", "request failed")))
                return self._redact_known_secrets(str(payload.get("message", "request failed")))
        except TypeError, ValueError:
            pass
        return self._redact_known_secrets(response.text or "request failed")

    def _redact_known_secrets(self, value: str) -> str:
        redacted = redact_secret(value)
        known_secrets = {
            self.target.api_key,
            os.getenv(self.target.api_key_env or ""),
            *self.target.headers.values(),
        }
        for secret in known_secrets:
            if secret and len(secret) >= 4:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted[:500]

    @staticmethod
    def _usage(payload: Mapping[str, Any]) -> TokenUsage | None:
        usage = payload.get("usage") or payload.get("usageMetadata")
        if not isinstance(usage, Mapping):
            return None
        return TokenUsage(
            prompt_tokens=_integer_or_none(usage.get("prompt_tokens", usage.get("promptTokenCount"))),
            completion_tokens=_integer_or_none(usage.get("completion_tokens", usage.get("candidatesTokenCount"))),
            total_tokens=_integer_or_none(usage.get("total_tokens", usage.get("totalTokenCount"))),
        )

    def _api_key(self, env_name: str) -> str:
        key = self.target.api_key or (os.getenv(self.target.api_key_env or env_name) or "")
        if not key:
            raise ProviderConfigurationError(
                f"{self.provider_name} API key is not configured.",
                provider=self.provider_name,
            )
        return key

    @abstractmethod
    async def _generate_text_once(self, request: ProviderRequest) -> ProviderResponse: ...

    @abstractmethod
    def _stream_text_once(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]: ...

    @abstractmethod
    async def _embed_once(self, texts: Sequence[str], *, model: str | None) -> EmbeddingResponse: ...

    @abstractmethod
    async def _check_connectivity_once(self) -> tuple[int, str | None]: ...


def _integer_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["BaseProvider", "redact_secret"]
