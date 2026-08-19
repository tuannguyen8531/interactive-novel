from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import src.api.routes.providers as provider_routes
from src.api.factory import create_app
from src.application.contracts.providers import ConnectivityResult, ProviderRoutingConfig
from src.config import Settings
from src.services.llm.models import OllamaAccountStatus


class FakeProviderSettings:
    def __init__(self) -> None:
        self.updated: ProviderRoutingConfig | None = None

    async def get_provider_settings(self) -> dict[str, object] | None:
        return None

    async def update_provider_settings(self, config: ProviderRoutingConfig):
        self.updated = config
        return config.snapshot()

    async def test_provider_connection(self) -> tuple[ConnectivityResult, ...]:
        return (ConnectivityResult(provider="ollama", model="fixture", reachable=True, latency_ms=1.0),)


def _payload() -> dict[str, Any]:
    roles = {
        role: {"primary_target": "local", "fallback_targets": []}
        for role in (
            "planner",
            "simulator",
            "context_validator",
            "writer",
            "critic",
            "world_builder",
            "embedding",
        )
    }
    return {
        "targets": {
            "local": {
                "name": "local",
                "provider": "ollama",
                "model": "llama3.2:3b",
                "base_url": "http://localhost:11434/api",
                "api_key_env": None,
            }
        },
        "role_routes": roles,
        "mode": "quality",
        "allow_cloud": False,
    }


@pytest.mark.asyncio
async def test_provider_settings_endpoint_updates_complete_routing_and_tests_connection() -> None:
    service = FakeProviderSettings()
    app = create_app(
        Settings(app_name="provider-api-test"),
        services=SimpleNamespace(provider_settings=service),  # type: ignore[arg-type]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        updated = await client.put("/api/providers/settings", json=_payload())
        tested = await client.post("/api/providers/test")

    assert updated.status_code == 200
    assert service.updated is not None
    assert service.updated.targets["local"].model == "llama3.2:3b"
    assert tested.status_code == 200
    assert tested.json()[0]["reachable"] is True


@pytest.mark.asyncio
async def test_provider_settings_reject_inline_secrets_and_incomplete_routes() -> None:
    service = FakeProviderSettings()
    app = create_app(
        Settings(app_name="provider-api-test"),
        services=SimpleNamespace(provider_settings=service),  # type: ignore[arg-type]
    )
    transport = httpx.ASGITransport(app=app)
    payload = _payload()
    payload["targets"]["local"]["api_key"] = "must-not-cross-api"
    payload["role_routes"].pop("embedding")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put("/api/providers/settings", json=payload)

    assert response.status_code == 422
    assert service.updated is None


@pytest.mark.asyncio
async def test_provider_models_endpoint_returns_discovered_models(monkeypatch) -> None:
    async def fake_list_provider_models(target):
        assert target.provider_name == "ollama"
        assert target.base_url == "http://ollama.test/api"
        return ("alpha:3b", "embedding:latest")

    monkeypatch.setattr(provider_routes, "list_provider_models", fake_list_provider_models)
    app = create_app(
        Settings(app_name="provider-api-test"),
        services=SimpleNamespace(provider_settings=FakeProviderSettings()),  # type: ignore[arg-type]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/providers/models",
            json={
                "provider": "ollama",
                "base_url": "http://ollama.test/api",
                "api_key_env": None,
                "timeout_seconds": 5,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"provider": "ollama", "models": ["alpha:3b", "embedding:latest"]}


@pytest.mark.asyncio
async def test_ollama_account_endpoint_returns_safe_status(monkeypatch) -> None:
    async def fake_get_ollama_account(*, base_url, timeout_seconds):
        assert base_url == "http://ollama.test/api"
        assert timeout_seconds == 5
        return OllamaAccountStatus(signed_in=True, username="fixture-user")

    monkeypatch.setattr(provider_routes, "get_ollama_account", fake_get_ollama_account)
    app = create_app(
        Settings(app_name="provider-api-test"),
        services=SimpleNamespace(provider_settings=FakeProviderSettings()),  # type: ignore[arg-type]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/providers/ollama/account",
            json={"base_url": "http://ollama.test/api", "timeout_seconds": 5},
        )

    assert response.status_code == 200
    assert response.json() == {"signed_in": True, "username": "fixture-user", "detail": None}
