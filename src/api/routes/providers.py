"""Secret-safe provider settings and connectivity endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.container import ApplicationContainer
from src.api.dependencies import get_services
from src.api.schemas import ProviderSettingsRequest
from src.api.serialization import public_json
from src.application.contracts.providers import ExecutionMode, ProviderRoute, ProviderRoutingConfig, ProviderTarget

router = APIRouter(prefix="/providers", tags=["providers"])
_services_dependency = Depends(get_services)


@router.get("/settings")
async def get_provider_settings(services: ApplicationContainer = _services_dependency):
    return public_json(await services.provider_settings.get_provider_settings())


@router.put("/settings")
async def update_provider_settings(
    payload: ProviderSettingsRequest,
    services: ApplicationContainer = _services_dependency,
):
    config = ProviderRoutingConfig(
        targets={name: ProviderTarget(**target.model_dump()) for name, target in payload.targets.items()},
        role_routes={
            role: ProviderRoute(
                primary_target=route.primary_target,
                fallback_targets=tuple(route.fallback_targets),
            )
            for role, route in payload.role_routes.items()
        },
        mode=ExecutionMode(payload.mode),
        allow_cloud=payload.allow_cloud,
    )
    snapshot = await services.provider_settings.update_provider_settings(config)
    return public_json(snapshot)


@router.post("/test")
async def test_provider_connection(services: ApplicationContainer = _services_dependency):
    return public_json(await services.provider_settings.test_provider_connection())


__all__ = ["router"]
