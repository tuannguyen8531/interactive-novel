"""Provider construction and routed execution with privacy-safe fallback."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import replace

from src.application.contracts.providers import (
    ConnectivityResult,
    EmbeddingResponse,
    ExecutionMode,
    LogicalRole,
    PhysicalCallPlan,
    PrivacyRoutingError,
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
from src.application.ports.providers import ProviderGateway, ProviderPort

from .base import BaseProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider

ProviderConstructor = Callable[[ProviderTarget], ProviderPort]


class ProviderFactory:
    """Build adapters without exposing provider SDKs to application code."""

    _constructors: Mapping[str, type[BaseProvider]] = {
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
    }

    def __init__(self, constructors: Mapping[str, ProviderConstructor] | None = None) -> None:
        self._custom_constructors = dict(constructors or {})

    def create(self, target: ProviderTarget) -> ProviderPort:
        custom = self._custom_constructors.get(target.provider_name)
        if custom is not None:
            return custom(target)
        constructor = self._constructors.get(target.provider_name)
        if constructor is None:
            raise ValueError(f"Unknown provider: {target.provider_name}")
        return constructor(target)


class PhysicalCallPlanner:
    """Map logical roles to traceable physical calls under Quality/Fast policy."""

    def plan(
        self,
        roles: Sequence[LogicalRole | str],
        *,
        target_by_role: Mapping[str, str],
        mode: ExecutionMode,
        call_prefix: str | None = None,
    ) -> tuple[PhysicalCallPlan, ...]:
        normalized = tuple(LogicalRole(role) for role in roles)
        if not normalized:
            return ()
        groups = self._groups(normalized, mode)
        plans: list[PhysicalCallPlan] = []
        for index, group in enumerate(groups):
            target_names = {target_by_role.get(role.value) for role in group}
            target_names.discard(None)
            if len(target_names) != 1:
                for role in group:
                    target_name = target_by_role.get(role.value)
                    if target_name is None:
                        raise ValueError(f"No provider target configured for role {role.value}.")
                    plans.append(
                        PhysicalCallPlan(
                            physical_call_id=f"{call_prefix or 'call'}-{index}-{role.value}",
                            logical_roles=(role,),
                            target_name=target_name,
                            mode=mode,
                            fused=False,
                        )
                    )
                continue
            target_name = next(iter(target_names))
            if target_name is None:
                raise AssertionError("a fused role group must have a provider target")
            plans.append(
                PhysicalCallPlan(
                    physical_call_id=f"{call_prefix or 'call'}-{index}",
                    logical_roles=group,
                    target_name=target_name,
                    mode=mode,
                    fused=len(group) > 1,
                )
            )
        return tuple(plans)

    @staticmethod
    def _groups(roles: tuple[LogicalRole, ...], mode: ExecutionMode) -> tuple[tuple[LogicalRole, ...], ...]:
        if mode == ExecutionMode.QUALITY:
            return tuple((role,) for role in roles)
        fused_groups = (
            (LogicalRole.PLANNER, LogicalRole.SIMULATOR),
            (LogicalRole.CONTEXT_VALIDATOR,),
            (LogicalRole.WRITER, LogicalRole.CRITIC),
        )
        remaining = list(roles)
        groups: list[tuple[LogicalRole, ...]] = []
        for candidate in fused_groups:
            selected = tuple(role for role in candidate if role in remaining)
            if selected:
                groups.append(selected)
                remaining = [role for role in remaining if role not in selected]
        groups.extend((role,) for role in remaining)
        return tuple(groups)


class ProviderRouter(ProviderGateway):
    """Route logical calls and apply fallback without changing output contracts."""

    def __init__(
        self,
        config: ProviderRoutingConfig,
        *,
        factory: ProviderFactory | None = None,
        planner: PhysicalCallPlanner | None = None,
    ) -> None:
        self.config = config
        self._factory = factory or ProviderFactory()
        self._planner = planner or PhysicalCallPlanner()
        self._providers: dict[str, ProviderPort] = {}

    def _route(self, role: LogicalRole | str) -> ProviderRoute:
        route = self.config.role_routes.get(str(role))
        if route is None:
            raise ValueError(f"No provider route configured for role {role}.")
        return route

    def _candidates(self, role: LogicalRole | str) -> tuple[tuple[str, ProviderTarget], ...]:
        route = self._route(role)
        candidates: list[tuple[str, ProviderTarget]] = []
        for target_name in (route.primary_target, *route.fallback_targets):
            target = self.config.targets[target_name]
            if target.is_cloud and not self.config.allow_cloud:
                continue
            candidates.append((target_name, target))
        if not candidates:
            primary = self.config.targets[route.primary_target]
            raise PrivacyRoutingError(
                "Cloud provider routing is disabled for this configuration.",
                provider=primary.provider_name,
            )
        return tuple(candidates)

    def _provider(self, target_name: str, target: ProviderTarget) -> ProviderPort:
        provider = self._providers.get(target_name)
        if provider is None:
            provider = self._factory.create(target)
            self._providers[target_name] = provider
        return provider

    async def generate_text(self, request: ProviderRequest) -> ProviderResponse:
        primary_name: str | None = None
        last_error: ProviderError | None = None
        for target_name, target in self._candidates(request.role):
            primary_name = primary_name or target_name
            try:
                response = await self._provider(target_name, target).generate_text(request)
                return replace(response, fallback_from=primary_name if target_name != primary_name else None)
            except ProviderError as error:
                last_error = error
                if not error.fallback_eligible:
                    raise
        if last_error is not None:
            raise last_error
        raise AssertionError("provider candidates must not be empty")

    async def generate_structured(
        self,
        request: ProviderRequest,
        schema: StructuredSchema,
    ) -> StructuredResponse:
        primary_name: str | None = None
        last_error: ProviderError | None = None
        for target_name, target in self._candidates(request.role):
            primary_name = primary_name or target_name
            try:
                response = await self._provider(target_name, target).generate_structured(request, schema)
                if target_name != primary_name:
                    response = replace(response, response=replace(response.response, fallback_from=primary_name))
                return response
            except ProviderError as error:
                last_error = error
                if not error.fallback_eligible:
                    raise
        if last_error is not None:
            raise last_error
        raise AssertionError("provider candidates must not be empty")

    async def _stream_with_fallback(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]:
        emitted = False
        last_error: ProviderError | None = None
        for target_name, target in self._candidates(request.role):
            try:
                async for chunk in self._provider(target_name, target).stream_text(request):
                    emitted = True
                    yield replace(chunk, retry_count=chunk.retry_count)
                return
            except ProviderError as error:
                last_error = error
                if emitted or not error.fallback_eligible:
                    raise
        if last_error is not None:
            raise last_error

    def stream_text(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]:
        return self._stream_with_fallback(request)

    async def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResponse:
        primary_name: str | None = None
        last_error: ProviderError | None = None
        for target_name, target in self._candidates("embedding"):
            primary_name = primary_name or target_name
            try:
                return await self._provider(target_name, target).embed(texts, model=model)
            except ProviderError as error:
                last_error = error
                if not error.fallback_eligible:
                    raise
        if last_error is not None:
            raise last_error
        raise AssertionError("provider candidates must not be empty")

    async def check_connectivity(self) -> tuple[ConnectivityResult, ...]:
        results: list[ConnectivityResult] = []
        for target_name, target in self.config.targets.items():
            if target.is_cloud and not self.config.allow_cloud:
                results.append(
                    ConnectivityResult(
                        provider=target.provider_name,
                        model=target.model,
                        reachable=False,
                        latency_ms=0.0,
                        message="cloud routing disabled",
                    )
                )
                continue
            results.append(await self._provider(target_name, target).check_connectivity())
        return tuple(results)

    def physical_call_plan(
        self,
        roles: Sequence[LogicalRole | str],
        *,
        call_prefix: str | None = None,
    ) -> tuple[PhysicalCallPlan, ...]:
        target_by_role = {role: route.primary_target for role, route in self.config.role_routes.items() if role != "embedding"}
        return self._planner.plan(
            roles,
            target_by_role=target_by_role,
            mode=self.config.mode,
            call_prefix=call_prefix,
        )

    def config_snapshot(self) -> dict[str, object]:
        return self.config.snapshot().as_dict()

    async def aclose(self) -> None:
        for provider in self._providers.values():
            await provider.aclose()
        self._providers.clear()

    async def __aenter__(self) -> ProviderRouter:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()


__all__ = ["PhysicalCallPlanner", "ProviderFactory", "ProviderRouter"]
