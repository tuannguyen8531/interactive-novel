"""Provider-neutral contracts for text generation and embeddings.

This module owns transport and provider capability boundaries only. AI role schemas
and authoritative proposal models live in their dedicated contracts.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from src.domain.language import StoryLanguage


class ProviderName(StrEnum):
    OLLAMA = "ollama"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class LogicalRole(StrEnum):
    PLANNER = "planner"
    SIMULATOR = "simulator"
    CONTEXT_VALIDATOR = "context_validator"
    WRITER = "writer"
    CRITIC = "critic"


class ExecutionMode(StrEnum):
    QUALITY = "quality"
    FAST = "fast"


class ProviderCapability(StrEnum):
    STRUCTURED = "structured"
    TEXT = "text"
    STREAM = "stream"
    EMBEDDING = "embedding"


class ProviderError(RuntimeError):
    """Safe, machine-readable error crossing the provider port."""

    code = "provider_error"

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        retryable: bool = False,
        fallback_eligible: bool = False,
        status_code: int | None = None,
        request_id: str | None = None,
        retry_after_seconds: float | None = None,
        attempts: int = 0,
    ) -> None:
        self.provider = provider
        self.retryable = retryable
        self.fallback_eligible = fallback_eligible
        self.status_code = status_code
        self.request_id = request_id
        self.retry_after_seconds = retry_after_seconds
        self.attempts = attempts
        super().__init__(message)

    def with_attempts(self, attempts: int) -> ProviderError:
        return type(self)(
            str(self),
            provider=self.provider,
            retryable=self.retryable,
            fallback_eligible=self.fallback_eligible,
            status_code=self.status_code,
            request_id=self.request_id,
            retry_after_seconds=self.retry_after_seconds,
            attempts=attempts,
        )


class ProviderConfigurationError(ProviderError):
    code = "provider_configuration_error"


class ProviderCapabilityError(ProviderError):
    code = "provider_capability_error"


class ProviderTransportError(ProviderError):
    code = "provider_transport_error"


class ProviderTimeoutError(ProviderTransportError):
    code = "provider_timeout"


class ProviderRateLimitError(ProviderError):
    code = "provider_rate_limit"


class ProviderHTTPError(ProviderError):
    code = "provider_http_error"


class ProviderProtocolError(ProviderError):
    code = "provider_protocol_error"


class ProviderRefusalError(ProviderError):
    code = "provider_refusal"


class ProviderCancelledError(ProviderError):
    code = "provider_cancelled"


class StructuredOutputError(ProviderError):
    code = "structured_output_error"


class PrivacyRoutingError(ProviderError):
    code = "privacy_routing_error"


class CancellationToken:
    """Cooperative cancellation token checked at network and retry safe points."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def raise_if_cancelled(self, *, provider: str = "provider") -> None:
        if self.cancelled:
            raise ProviderCancelledError("Provider request was cancelled.", provider=provider)


StructuredValidator = Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class StructuredSchema:
    """Provider-facing JSON schema plus an optional validator hook."""

    name: str
    json_schema: Mapping[str, Any] = field(default_factory=dict)
    validator: StructuredValidator | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Structured schema name cannot be empty.")
        object.__setattr__(self, "json_schema", dict(self.json_schema))

    def validate(self, payload: Any, *, provider: str) -> Any:
        if self.validator is None:
            return payload
        try:
            return self.validator(payload)
        except ProviderError:
            raise
        except Exception as error:
            raise StructuredOutputError(
                f"Structured output failed schema validation for {self.name}.",
                provider=provider,
                fallback_eligible=True,
            ) from error


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    system_prompt: str
    user_prompt: str
    role: LogicalRole | str
    physical_call_id: str = field(default_factory=lambda: str(uuid4()))
    logical_roles: tuple[LogicalRole | str, ...] = ()
    model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    cancellation: CancellationToken | None = field(default=None, compare=False, repr=False)
    structured_schema: StructuredSchema | None = field(default=None, compare=False, repr=False)
    repair_attempt: int = field(default=0, compare=False)

    def __post_init__(self) -> None:
        if not self.system_prompt.strip() and not self.user_prompt.strip():
            raise ValueError("Provider request must contain a system or user prompt.")
        object.__setattr__(self, "logical_roles", tuple(self.logical_roles) or (self.role,))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.temperature is not None and not 0.0 <= self.temperature <= 2.0:
            raise ValueError("Provider temperature must be between 0 and 2.")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("Provider max output tokens must be positive.")
        if self.repair_attempt < 0:
            raise ValueError("Provider repair attempt cannot be negative.")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    provider: str
    model: str
    role: LogicalRole | str
    physical_call_id: str
    text: str
    request_id: str | None = None
    usage: TokenUsage | None = None
    finish_reason: str | None = None
    latency_ms: float = 0.0
    retry_count: int = 0
    fallback_from: str | None = None


@dataclass(frozen=True, slots=True)
class StructuredResponse:
    response: ProviderResponse
    data: Any
    repaired: bool = False
    validation_attempts: int = 1


@dataclass(frozen=True, slots=True)
class StreamChunk:
    provider: str
    model: str
    role: LogicalRole | str
    physical_call_id: str
    text: str
    index: int
    done: bool = False
    request_id: str | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    retry_count: int = 0


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    provider: str
    model: str
    embeddings: tuple[tuple[float, ...], ...]
    request_id: str | None = None
    latency_ms: float = 0.0
    retry_count: int = 0


@dataclass(frozen=True, slots=True)
class ConnectivityResult:
    provider: str
    model: str
    reachable: bool
    latency_ms: float
    status_code: int | None = None
    message: str | None = None
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderTarget:
    """One provider/model target; inline secrets never enter snapshots."""

    name: str
    provider: ProviderName | str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = field(default=None, repr=False, compare=False)
    timeout_seconds: float = 60.0
    max_retries: int = 2
    backoff_base_seconds: float = 0.25
    headers: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.model.strip():
            raise ValueError("Provider target requires a name and model.")
        if self.timeout_seconds <= 0:
            raise ValueError("Provider timeout must be positive.")
        if self.max_retries < 0:
            raise ValueError("Provider max retries cannot be negative.")
        if self.backoff_base_seconds < 0:
            raise ValueError("Provider backoff cannot be negative.")
        object.__setattr__(self, "headers", {str(key): str(value) for key, value in self.headers.items()})

    @property
    def provider_name(self) -> str:
        return str(self.provider)

    @property
    def is_cloud(self) -> bool:
        return self.provider_name in {ProviderName.GEMINI, ProviderName.OPENROUTER}

    def snapshot(self) -> dict[str, Any]:
        """Return safe config metadata without an API key or header values."""
        return {
            "name": self.name,
            "provider": self.provider_name,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "backoff_base_seconds": self.backoff_base_seconds,
            "header_names": sorted(self.headers),
        }


@dataclass(frozen=True, slots=True)
class ProviderRoute:
    primary_target: str
    fallback_targets: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.primary_target.strip():
            raise ValueError("Provider route requires a primary target.")
        object.__setattr__(self, "fallback_targets", tuple(self.fallback_targets))


@dataclass(frozen=True, slots=True)
class ProviderConfigSnapshot:
    """Serializable, secret-free provider routing snapshot."""

    schema_version: int
    mode: ExecutionMode
    allow_cloud: bool
    targets: Mapping[str, Mapping[str, Any]]
    role_routes: Mapping[str, Mapping[str, Any]]
    story_language: StoryLanguage = StoryLanguage.ENGLISH

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode.value,
            "allow_cloud": self.allow_cloud,
            "story_language": StoryLanguage(self.story_language).value,
            "targets": {key: dict(value) for key, value in self.targets.items()},
            "role_routes": {key: dict(value) for key, value in self.role_routes.items()},
        }


@dataclass(frozen=True, slots=True)
class ProviderRoutingConfig:
    targets: Mapping[str, ProviderTarget]
    role_routes: Mapping[LogicalRole | str, ProviderRoute]
    mode: ExecutionMode = ExecutionMode.QUALITY
    allow_cloud: bool = False
    schema_version: int = 1
    story_language: StoryLanguage = StoryLanguage.ENGLISH

    def __post_init__(self) -> None:
        normalized_targets = dict(self.targets)
        if not normalized_targets:
            raise ValueError("Provider routing requires at least one target.")
        if any(key != target.name for key, target in normalized_targets.items()):
            raise ValueError("Provider target map keys must match target names.")
        normalized_routes = {str(role): route for role, route in self.role_routes.items()}
        for role, route in normalized_routes.items():
            for target_name in (route.primary_target, *route.fallback_targets):
                if target_name not in normalized_targets:
                    raise ValueError(f"Provider route {role} references unknown target {target_name}.")
        object.__setattr__(self, "targets", normalized_targets)
        object.__setattr__(self, "role_routes", normalized_routes)
        object.__setattr__(self, "story_language", StoryLanguage(self.story_language))

    def snapshot(self) -> ProviderConfigSnapshot:
        return ProviderConfigSnapshot(
            schema_version=self.schema_version,
            mode=self.mode,
            allow_cloud=self.allow_cloud,
            story_language=self.story_language,
            targets={name: target.snapshot() for name, target in self.targets.items()},
            role_routes={
                role: {
                    "primary_target": route.primary_target,
                    "fallback_targets": list(route.fallback_targets),
                }
                for role, route in self.role_routes.items()
            },
        )


@dataclass(frozen=True, slots=True)
class PhysicalCallPlan:
    physical_call_id: str
    logical_roles: tuple[LogicalRole, ...]
    target_name: str
    mode: ExecutionMode
    fused: bool
    skip_reason: str | None = None


__all__ = [
    "CancellationToken",
    "ConnectivityResult",
    "EmbeddingResponse",
    "ExecutionMode",
    "LogicalRole",
    "PhysicalCallPlan",
    "PrivacyRoutingError",
    "ProviderCapability",
    "ProviderCapabilityError",
    "ProviderCancelledError",
    "ProviderConfigSnapshot",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderHTTPError",
    "ProviderName",
    "ProviderProtocolError",
    "ProviderRateLimitError",
    "ProviderRefusalError",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderRoute",
    "ProviderRoutingConfig",
    "ProviderTarget",
    "ProviderTimeoutError",
    "ProviderTransportError",
    "StreamChunk",
    "StructuredOutputError",
    "StructuredResponse",
    "StoryLanguage",
    "StructuredSchema",
    "TokenUsage",
]
