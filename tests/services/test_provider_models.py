from __future__ import annotations

import httpx
import pytest

from src.application.contracts.providers import ProviderTarget
from src.services.llm.models import get_ollama_account, list_provider_models


@pytest.mark.parametrize(
    ("provider", "payload", "expected"),
    [
        ("ollama", {"models": [{"name": "zeta:latest"}, {"name": "alpha:3b"}]}, ("alpha:3b", "zeta:latest")),
        ("gemini", {"models": [{"name": "models/gemini-flash"}]}, ("gemini-flash",)),
        ("openrouter", {"data": [{"id": "vendor/model"}]}, ("vendor/model",)),
    ],
)
async def test_list_provider_models_parses_each_catalog(
    provider: str,
    payload: dict[str, object],
    expected: tuple[str, ...],
    monkeypatch,
) -> None:
    monkeypatch.setenv("TEST_CATALOG_KEY", "catalog-secret")

    async def handler(request: httpx.Request) -> httpx.Response:
        if provider == "gemini":
            assert request.headers["x-goog-api-key"] == "catalog-secret"
        if provider == "openrouter":
            assert request.headers["authorization"] == "Bearer catalog-secret"
        return httpx.Response(200, json=payload)

    target = ProviderTarget(
        name="catalog",
        provider=provider,
        model="unused",
        base_url="http://provider.test/api",
        api_key_env="TEST_CATALOG_KEY" if provider != "ollama" else None,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await list_provider_models(target, client=client)

    assert models == expected


async def test_list_provider_models_is_best_effort() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "offline"})

    target = ProviderTarget(name="catalog", provider="ollama", model="unused", base_url="http://provider.test/api")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await list_provider_models(target, client=client)

    assert models == ()


@pytest.mark.parametrize(
    ("status_code", "payload", "signed_in", "username", "detail"),
    [
        (200, {"name": "reader@example.com"}, True, "reader@example.com", None),
        (401, {}, False, None, "Not signed in"),
    ],
)
async def test_get_ollama_account_reports_daemon_session(
    status_code: int,
    payload: dict[str, object],
    signed_in: bool,
    username: str | None,
    detail: str | None,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://provider.test/api/me"
        return httpx.Response(status_code, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        account = await get_ollama_account(base_url="http://provider.test/api", client=client)

    assert account.signed_in is signed_in
    assert account.username == username
    assert account.detail == detail
