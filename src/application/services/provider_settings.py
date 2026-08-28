"""Provider settings use cases with secret-free snapshots and connectivity checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.application.contracts.providers import (
    ConnectivityResult,
    ExecutionMode,
    ProviderConfigSnapshot,
    ProviderRoute,
    ProviderRoutingConfig,
    ProviderTarget,
)
from src.application.errors import ApplicationValidationError
from src.application.ports.providers import ProviderGateway, ProviderSettingsStore
from src.domain.language import StoryLanguage


class InMemoryProviderSettingsStore:
    """Small default store for the single-user local runtime."""

    def __init__(self) -> None:
        self._snapshot: dict[str, object] | None = None

    async def get(self) -> dict[str, object] | None:
        return None if self._snapshot is None else dict(self._snapshot)

    async def put(self, snapshot: dict[str, object]) -> None:
        self._snapshot = dict(snapshot)


class ProviderSettingsApplicationService:
    """Validate and expose routing metadata without returning credentials."""

    def __init__(
        self,
        store: ProviderSettingsStore | None = None,
        *,
        gateway: ProviderGateway | None = None,
    ) -> None:
        self._store = store or InMemoryProviderSettingsStore()
        self._gateway = gateway

    async def get_provider_settings(self) -> dict[str, object] | None:
        return await self._store.get()

    async def initialize(self, default: ProviderRoutingConfig) -> ProviderConfigSnapshot:
        stored = await self._store.get()
        if stored is None:
            return await self.update_provider_settings(default)
        config = _config_from_snapshot(stored)
        if self._gateway is not None:
            await self._gateway.reconfigure(config)
        return config.snapshot()

    async def update_provider_settings(self, config: ProviderRoutingConfig) -> ProviderConfigSnapshot:
        snapshot = config.snapshot()
        if self._gateway is not None:
            await self._gateway.reconfigure(config)
        await self._store.put(snapshot.as_dict())
        return snapshot

    async def test_provider_connection(self) -> tuple[ConnectivityResult, ...]:
        if self._gateway is None:
            raise ApplicationValidationError("Provider connectivity gateway is not configured.")
        return await self._gateway.check_connectivity()


def _config_from_snapshot(snapshot: Mapping[str, Any]) -> ProviderRoutingConfig:
    targets_value = snapshot.get("targets", {})
    routes_value = snapshot.get("role_routes", {})
    if not isinstance(targets_value, Mapping) or not isinstance(routes_value, Mapping):
        raise ApplicationValidationError("Stored provider settings are malformed.")
    try:
        targets: dict[str, ProviderTarget] = {}
        for name, value in targets_value.items():
            if not isinstance(value, Mapping):
                raise TypeError("Provider target must be an object.")
            targets[str(name)] = ProviderTarget(
                name=str(value["name"]),
                provider=str(value["provider"]),
                model=str(value["model"]),
                base_url=None if value.get("base_url") is None else str(value["base_url"]),
                api_key_env=None if value.get("api_key_env") is None else str(value["api_key_env"]),
                timeout_seconds=float(value.get("timeout_seconds", 60.0)),
                max_retries=int(value.get("max_retries", 2)),
                backoff_base_seconds=float(value.get("backoff_base_seconds", 0.25)),
            )
        routes: dict[str, ProviderRoute] = {}
        for role, value in routes_value.items():
            if not isinstance(value, Mapping):
                raise TypeError("Provider route must be an object.")
            routes[str(role)] = ProviderRoute(
                primary_target=str(value["primary_target"]),
                fallback_targets=tuple(str(item) for item in value.get("fallback_targets", ())),
            )
        return ProviderRoutingConfig(
            targets=targets,
            role_routes=routes,
            mode=ExecutionMode(str(snapshot.get("mode", ExecutionMode.QUALITY))),
            allow_cloud=bool(snapshot.get("allow_cloud", False)),
            story_language=StoryLanguage(str(snapshot.get("story_language", StoryLanguage.ENGLISH.value))),
            schema_version=int(snapshot.get("schema_version", 1)),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ApplicationValidationError("Stored provider settings are invalid.") from error


__all__ = ["InMemoryProviderSettingsStore", "ProviderSettingsApplicationService"]
