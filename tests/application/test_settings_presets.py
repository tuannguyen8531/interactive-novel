import json
from unittest.mock import AsyncMock

import pytest

from src.application.contracts.providers import ExecutionMode, ProviderRoute, ProviderRoutingConfig, ProviderTarget
from src.application.errors import ResourceConflictError, ResourceNotFoundError
from src.application.services.provider_settings import ProviderSettingsApplicationService
from src.services.provider_settings import JsonProviderPresetStore, JsonProviderSettingsStore


@pytest.mark.asyncio
async def test_presets_survive_restart_and_restore_full_config(tmp_path):
    gateway = AsyncMock()
    store = JsonProviderSettingsStore(tmp_path / "settings.json")
    presets = JsonProviderPresetStore(tmp_path / "presets")
    service = ProviderSettingsApplicationService(store, gateway=gateway, presets_store=presets)
    config = ProviderRoutingConfig(
        targets={"local": ProviderTarget(name="local", provider="ollama", model="test")},
        role_routes={"writer": ProviderRoute(primary_target="local")},
    )
    await service.save_preset(" Local ", config)
    assert (tmp_path / "presets" / "local.json").is_file()
    gateway.reconfigure.assert_not_awaited()
    assert await store.get() is None
    service = ProviderSettingsApplicationService(store, gateway=gateway, presets_store=presets)
    assert await service.list_presets() == ["Local"]
    assert await service.apply_preset("Local") == config.snapshot()
    assert await store.get() == config.snapshot().as_dict()
    assert await service.active_preset() == "Local"
    gateway.reconfigure.assert_awaited_once()

    updated = ProviderRoutingConfig(
        targets=config.targets,
        role_routes=config.role_routes,
        mode=ExecutionMode.FAST,
    )
    await service.save_preset("Local", updated)
    assert await service.active_preset() is None
    assert (await service.apply_preset("Local")).mode is ExecutionMode.FAST
    assert await service.delete_preset("Local") == []
    assert await service.active_preset() is None
    with pytest.raises(ResourceNotFoundError):
        await service.apply_preset("Missing")
    with pytest.raises(ResourceNotFoundError):
        await service.delete_preset("Missing")


@pytest.mark.asyncio
async def test_preset_file_name_is_slugified_and_collisions_are_rejected(tmp_path):
    presets = JsonProviderPresetStore(tmp_path / "presets")
    service = ProviderSettingsApplicationService(presets_store=presets)
    config = ProviderRoutingConfig(
        targets={"local": ProviderTarget(name="local", provider="ollama", model="test")},
        role_routes={"writer": ProviderRoute(primary_target="local")},
    )

    await service.save_preset("Local 1", config)

    preset_path = tmp_path / "presets" / "local-1.json"
    assert preset_path.is_file()
    document = json.loads(preset_path.read_text(encoding="utf-8"))
    assert document["name"] == "Local 1"
    assert document["settings"] == config.snapshot().as_dict()
    with pytest.raises(ResourceConflictError):
        await service.save_preset("local-1", config)
