"""Pydantic contracts exposed by the API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.application.contracts.ai import WorldSeed


class HealthResponse(BaseModel):
    """Public liveness response."""

    status: Literal["ok"]
    service: str
    version: str


class ErrorPayload(BaseModel):
    """Stable machine-readable error body."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Top-level API error envelope."""

    error: ErrorPayload


class WorldCreateRequest(BaseModel):
    """Create a reusable world seed."""

    name: str = Field(min_length=1, max_length=160)
    premise: str = Field(default="", max_length=20_000)
    genre: str = Field(default="", max_length=80)
    tone: str = Field(default="", max_length=80)
    canon_rules: dict[str, Any] = Field(default_factory=dict)
    content_policy: dict[str, Any] = Field(default_factory=dict)


class WorldDraftGenerateRequest(BaseModel):
    """Natural-language request for a transient school-romance WorldSeed."""

    prompt: str = Field(min_length=1, max_length=20_000)


class WorldDraftRequest(BaseModel):
    """Edited WorldSeed sent back for deterministic validation or confirmation."""

    draft: WorldSeed
    world_id: str | None = Field(default=None, min_length=1, max_length=160)


class PlaythroughCreateRequest(BaseModel):
    """Create a playthrough from a confirmed world."""

    world_id: str = Field(min_length=1, max_length=160)
    player_character_id: str | None = Field(default=None, max_length=160)
    root_branch_id: str | None = Field(default=None, max_length=160)
    provider_config_snapshot: dict[str, Any] = Field(default_factory=dict)
    world_clock_minutes: int = Field(default=0, ge=0)
    rng_seed: str | None = Field(default=None, max_length=160)
    rng_state: dict[str, Any] = Field(default_factory=dict)


class RootBranchRequest(BaseModel):
    playthrough_id: str = Field(min_length=1, max_length=160)
    branch_id: str | None = Field(default=None, max_length=160)


class ForkBranchRequest(BaseModel):
    parent_branch_id: str = Field(min_length=1, max_length=160)
    fork_turn_id: str = Field(min_length=1, max_length=160)
    branch_id: str | None = Field(default=None, max_length=160)


class RegenerateBranchRequest(BaseModel):
    branch_id: str = Field(min_length=1, max_length=160)
    turn_id: str = Field(min_length=1, max_length=160)
    new_branch_id: str | None = Field(default=None, max_length=160)


class UndoBranchRequest(BaseModel):
    branch_id: str = Field(min_length=1, max_length=160)
    head_turn_id: str = Field(min_length=1, max_length=160)
    new_branch_id: str | None = Field(default=None, max_length=160)


class BackupCreateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=210)


class BackupRestoreRequest(BaseModel):
    name: str = Field(min_length=1, max_length=210)


class SwitchBranchRequest(BaseModel):
    playthrough_id: str = Field(min_length=1, max_length=160)


class TurnSubmitRequest(BaseModel):
    """Input for one asynchronous turn job."""

    playthrough_id: str = Field(min_length=1, max_length=160)
    branch_id: str = Field(min_length=1, max_length=160)
    raw_input: str = Field(min_length=1, max_length=20_000)
    base_revision: int = Field(ge=0)
    actor_id: str = Field(default="player", min_length=1, max_length=160)
    turn_run_id: str | None = Field(default=None, min_length=1, max_length=160)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    parent_turn_id: str | None = Field(default=None, max_length=160)
    config_snapshot_id: str = Field(default="api-default", min_length=1, max_length=160)


class ProviderTargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    provider: Literal["ollama", "gemini", "openrouter"]
    model: str = Field(min_length=1, max_length=160)
    base_url: str | None = Field(default=None, max_length=2_000)
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=160)
    timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    max_retries: int = Field(default=2, ge=0, le=10)
    backoff_base_seconds: float = Field(default=0.25, ge=0, le=60)


class ProviderRouteRequest(BaseModel):
    primary_target: str = Field(min_length=1, max_length=160)
    fallback_targets: list[str] = Field(default_factory=list, max_length=8)


class ProviderSettingsRequest(BaseModel):
    targets: dict[str, ProviderTargetRequest]
    role_routes: dict[str, ProviderRouteRequest]
    mode: Literal["quality", "fast"] = "quality"
    allow_cloud: bool = False

    @model_validator(mode="after")
    def validate_routing(self) -> ProviderSettingsRequest:
        if not self.targets:
            raise ValueError("At least one provider target is required.")
        for name, target in self.targets.items():
            if name != target.name:
                raise ValueError(f"Provider target key {name} must match its name.")
        required_roles = {
            "planner",
            "simulator",
            "context_validator",
            "writer",
            "critic",
            "world_builder",
            "embedding",
        }
        missing_roles = sorted(required_roles - self.role_routes.keys())
        if missing_roles:
            raise ValueError(f"Missing provider routes: {', '.join(missing_roles)}.")
        for role, route in self.role_routes.items():
            referenced = (route.primary_target, *route.fallback_targets)
            unknown = [name for name in referenced if name not in self.targets]
            if unknown:
                raise ValueError(f"Provider route {role} references unknown target {unknown[0]}.")
            if route.primary_target in route.fallback_targets:
                raise ValueError(f"Provider route {role} repeats its primary target as fallback.")
            if len(set(route.fallback_targets)) != len(route.fallback_targets):
                raise ValueError(f"Provider route {role} contains duplicate fallbacks.")
        return self


class ProviderModelsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["ollama", "gemini", "openrouter"]
    base_url: str | None = Field(default=None, max_length=2_000)
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=160)
    timeout_seconds: float = Field(default=10.0, gt=0, le=600)


class ProviderModelsResponse(BaseModel):
    provider: Literal["ollama", "gemini", "openrouter"]
    models: list[str]


class OllamaAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str | None = Field(default=None, max_length=2_000)
    timeout_seconds: float = Field(default=10.0, gt=0, le=600)


class OllamaAccountResponse(BaseModel):
    signed_in: bool
    username: str | None = None
    detail: str | None = None


class FeedbackRequest(BaseModel):
    """Explicit alpha feedback; it never carries prompts or provider output."""

    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=4_000)
    category: str = Field(default="general", min_length=1, max_length=80)
    turn_run_id: str | None = Field(default=None, max_length=160)


__all__ = [
    "BackupCreateRequest",
    "BackupRestoreRequest",
    "ErrorEnvelope",
    "FeedbackRequest",
    "ErrorPayload",
    "ForkBranchRequest",
    "HealthResponse",
    "PlaythroughCreateRequest",
    "ProviderRouteRequest",
    "ProviderSettingsRequest",
    "ProviderTargetRequest",
    "RegenerateBranchRequest",
    "RootBranchRequest",
    "SwitchBranchRequest",
    "TurnSubmitRequest",
    "UndoBranchRequest",
    "WorldCreateRequest",
    "WorldDraftGenerateRequest",
    "WorldDraftRequest",
]
