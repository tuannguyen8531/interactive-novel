"""Provider settings use cases with secret-free snapshots and connectivity checks."""

from __future__ import annotations

from src.application.contracts.providers import ConnectivityResult, ProviderConfigSnapshot, ProviderRoutingConfig
from src.application.errors import ApplicationValidationError
from src.application.ports.providers import ProviderGateway, ProviderSettingsStore


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

    async def update_provider_settings(self, config: ProviderRoutingConfig) -> ProviderConfigSnapshot:
        snapshot = config.snapshot()
        await self._store.put(snapshot.as_dict())
        return snapshot

    async def test_provider_connection(self) -> tuple[ConnectivityResult, ...]:
        if self._gateway is None:
            raise ApplicationValidationError("Provider connectivity gateway is not configured.")
        return await self._gateway.check_connectivity()


__all__ = ["InMemoryProviderSettingsStore", "ProviderSettingsApplicationService"]
