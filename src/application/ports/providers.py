"""Inward-facing provider ports implemented by the LLM service adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from src.application.contracts.providers import (
    ConnectivityResult,
    EmbeddingResponse,
    ProviderCapability,
    ProviderRequest,
    ProviderResponse,
    ProviderRoutingConfig,
    StreamChunk,
    StructuredResponse,
    StructuredSchema,
)


class ProviderPort(Protocol):
    """Neutral capability contract shared by Ollama, Gemini and OpenRouter."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[ProviderCapability]: ...

    async def generate_text(self, request: ProviderRequest) -> ProviderResponse: ...

    async def generate_structured(
        self,
        request: ProviderRequest,
        schema: StructuredSchema,
    ) -> StructuredResponse: ...

    def stream_text(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]: ...

    async def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResponse: ...

    async def check_connectivity(self) -> ConnectivityResult: ...

    async def aclose(self) -> None: ...


class ProviderGateway(Protocol):
    """Router-level port used by future graph/application orchestration."""

    async def generate_text(self, request: ProviderRequest) -> ProviderResponse: ...

    async def generate_structured(
        self,
        request: ProviderRequest,
        schema: StructuredSchema,
    ) -> StructuredResponse: ...

    def stream_text(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]: ...

    async def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResponse: ...

    async def check_connectivity(self) -> tuple[ConnectivityResult, ...]: ...

    async def reconfigure(self, config: ProviderRoutingConfig) -> None: ...

    def config_snapshot(self) -> dict[str, object]: ...

    async def aclose(self) -> None: ...


class ProviderSettingsStore(Protocol):
    """Secret-free storage for the active provider routing snapshot."""

    async def get(self) -> dict[str, object] | None: ...

    async def put(self, snapshot: dict[str, object]) -> None: ...


__all__ = ["ProviderGateway", "ProviderPort", "ProviderSettingsStore"]
