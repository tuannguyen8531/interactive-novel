from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import ClassVar

import pytest

from src.application.contracts.providers import (
    ConnectivityResult,
    EmbeddingResponse,
    ExecutionMode,
    LogicalRole,
    PrivacyRoutingError,
    ProviderCapability,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderRoute,
    ProviderRoutingConfig,
    ProviderTarget,
    StreamChunk,
    StructuredResponse,
    StructuredSchema,
)
from src.services.llm.factory import ProviderFactory, ProviderRouter


class _FixtureProvider:
    created_targets: ClassVar[list[str]] = []

    def __init__(self, target: ProviderTarget) -> None:
        self.target = target
        self.created_targets.append(target.name)

    @property
    def provider_name(self) -> str:
        return self.target.provider_name

    @property
    def model(self) -> str:
        return self.target.model

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset(ProviderCapability)

    async def generate_text(self, request: ProviderRequest) -> ProviderResponse:
        if self.target.name == "primary":
            raise ProviderError(
                "fixture upstream unavailable",
                provider=self.provider_name,
                fallback_eligible=True,
            )
        return ProviderResponse(
            provider=self.provider_name,
            model=request.model or self.model,
            role=request.role,
            physical_call_id=request.physical_call_id,
            text=f"answer from {self.target.name}",
        )

    async def generate_structured(
        self,
        request: ProviderRequest,
        schema: StructuredSchema,
    ) -> StructuredResponse:
        return StructuredResponse(
            response=await self.generate_text(request),
            data={"schema": schema.name},
        )

    def stream_text(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]:
        async def stream() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(
                provider=self.provider_name,
                model=request.model or self.model,
                role=request.role,
                physical_call_id=request.physical_call_id,
                text=f"stream from {self.target.name}",
                index=0,
                done=True,
            )

        return stream()

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> EmbeddingResponse:
        return EmbeddingResponse(
            provider=self.provider_name,
            model=model or self.model,
            embeddings=tuple((float(index),) for index, _ in enumerate(texts)),
        )

    async def check_connectivity(self) -> ConnectivityResult:
        return ConnectivityResult(
            provider=self.provider_name,
            model=self.model,
            reachable=True,
            latency_ms=0.0,
        )

    async def aclose(self) -> None:
        return None


def _target(name: str, *, provider: str = "ollama", model: str | None = None) -> ProviderTarget:
    return ProviderTarget(
        name=name,
        provider=provider,
        model=model or f"{name}-model",
        api_key="fixture-secret" if provider != "ollama" else None,
    )


def _config(
    *,
    mode: ExecutionMode = ExecutionMode.QUALITY,
    allow_cloud: bool = False,
    targets: dict[str, ProviderTarget] | None = None,
    role_routes: dict[LogicalRole | str, ProviderRoute] | None = None,
) -> ProviderRoutingConfig:
    configured_targets = targets or {"local": _target("local")}
    configured_routes = role_routes or {role: ProviderRoute("local") for role in (*LogicalRole, "embedding")}
    return ProviderRoutingConfig(
        targets=configured_targets,
        role_routes=configured_routes,
        mode=mode,
        allow_cloud=allow_cloud,
    )


def _request(role: LogicalRole) -> ProviderRequest:
    return ProviderRequest(
        system_prompt="Fixture system prompt.",
        user_prompt="Fixture user prompt.",
        role=role,
    )


def _factory() -> ProviderFactory:
    _FixtureProvider.created_targets.clear()
    return ProviderFactory({"ollama": _FixtureProvider, "gemini": _FixtureProvider})


def test_quality_and_fast_plans_keep_each_logical_role_independent() -> None:
    roles = tuple(LogicalRole)
    quality_router = ProviderRouter(_config(), factory=_factory())
    quality = quality_router.physical_call_plan(roles, call_prefix="quality")

    assert len(quality) == 5
    assert tuple(plan.logical_roles[0] for plan in quality) == roles
    assert all(not plan.fused for plan in quality)

    fast_router = ProviderRouter(_config(mode=ExecutionMode.FAST), factory=_factory())
    fast = fast_router.physical_call_plan(roles, call_prefix="fast")

    assert len(fast) == 3
    assert fast[0].logical_roles == (LogicalRole.PLANNER, LogicalRole.SIMULATOR)
    assert fast[0].fused is True
    assert fast[1].logical_roles == (LogicalRole.VALIDATOR,)
    assert fast[2].logical_roles == (LogicalRole.WRITER, LogicalRole.CRITIC)
    assert fast[2].fused is True
    assert {role for plan in fast for role in plan.logical_roles} == set(roles)


def test_fast_plan_splits_roles_when_their_targets_differ() -> None:
    targets = {
        "planner": _target("planner", model="planner-model"),
        "simulator": _target("simulator", model="simulator-model"),
        "validator": _target("validator", model="validator-model"),
        "writer": _target("writer", model="writer-model"),
    }
    routes: dict[LogicalRole | str, ProviderRoute] = {
        LogicalRole.PLANNER: ProviderRoute("planner"),
        LogicalRole.SIMULATOR: ProviderRoute("simulator"),
        LogicalRole.VALIDATOR: ProviderRoute("validator"),
        LogicalRole.WRITER: ProviderRoute("writer"),
        LogicalRole.CRITIC: ProviderRoute("writer"),
        "embedding": ProviderRoute("validator"),
    }
    router = ProviderRouter(
        _config(mode=ExecutionMode.FAST, targets=targets, role_routes=routes),
        factory=_factory(),
    )

    plans = router.physical_call_plan(tuple(LogicalRole))

    assert [(plan.target_name, plan.logical_roles, plan.fused) for plan in plans] == [
        ("planner", (LogicalRole.PLANNER,), False),
        ("simulator", (LogicalRole.SIMULATOR,), False),
        ("validator", (LogicalRole.VALIDATOR,), False),
        ("writer", (LogicalRole.WRITER, LogicalRole.CRITIC), True),
    ]


@pytest.mark.asyncio
async def test_role_routing_changes_model_without_changing_provider_request() -> None:
    targets = {
        "planner": _target("planner", model="planner-model"),
        "writer": _target("writer", model="writer-model"),
    }
    routes: dict[LogicalRole | str, ProviderRoute] = {
        role: ProviderRoute("planner" if role == LogicalRole.PLANNER else "writer") for role in LogicalRole
    }
    routes["embedding"] = ProviderRoute("writer")
    router = ProviderRouter(
        _config(targets=targets, role_routes=routes),
        factory=_factory(),
    )

    planner_response = await router.generate_text(_request(LogicalRole.PLANNER))
    writer_response = await router.generate_text(_request(LogicalRole.WRITER))

    assert planner_response.model == "planner-model"
    assert writer_response.model == "writer-model"
    assert planner_response.role == LogicalRole.PLANNER
    assert writer_response.role == LogicalRole.WRITER


@pytest.mark.asyncio
async def test_fallback_preserves_response_contract_and_records_primary_target() -> None:
    targets = {
        "primary": _target("primary", model="primary-model"),
        "fallback": _target("fallback", model="fallback-model"),
    }
    routes: dict[LogicalRole | str, ProviderRoute] = {role: ProviderRoute("primary", ("fallback",)) for role in LogicalRole}
    routes["embedding"] = ProviderRoute("fallback")
    router = ProviderRouter(
        _config(targets=targets, role_routes=routes),
        factory=_factory(),
    )

    response = await router.generate_text(_request(LogicalRole.WRITER))

    assert response.provider == "ollama"
    assert response.model == "fallback-model"
    assert response.role == LogicalRole.WRITER
    assert response.fallback_from == "primary"


@pytest.mark.asyncio
async def test_cloud_target_is_skipped_until_cloud_routing_is_enabled() -> None:
    targets = {
        "cloud": _target("cloud", provider="gemini", model="cloud-model"),
        "local": _target("local", model="local-model"),
    }
    routes: dict[LogicalRole | str, ProviderRoute] = {role: ProviderRoute("cloud", ("local",)) for role in LogicalRole}
    routes["embedding"] = ProviderRoute("local")
    router = ProviderRouter(
        _config(targets=targets, role_routes=routes, allow_cloud=False),
        factory=_factory(),
    )

    response = await router.generate_text(_request(LogicalRole.WRITER))

    assert response.model == "local-model"
    assert _FixtureProvider.created_targets == ["local"]


@pytest.mark.asyncio
async def test_cloud_only_route_is_rejected_when_cloud_is_disabled() -> None:
    targets = {"cloud": _target("cloud", provider="gemini")}
    routes: dict[LogicalRole | str, ProviderRoute] = {role: ProviderRoute("cloud") for role in LogicalRole}
    routes["embedding"] = ProviderRoute("cloud")
    router = ProviderRouter(
        _config(targets=targets, role_routes=routes, allow_cloud=False),
        factory=_factory(),
    )

    with pytest.raises(PrivacyRoutingError):
        await router.generate_text(_request(LogicalRole.WRITER))
