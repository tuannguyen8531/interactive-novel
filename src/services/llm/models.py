"""Best-effort model discovery for provider settings screens."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import httpx

from src.application.contracts.providers import ProviderTarget

from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider


async def list_provider_models(
    target: ProviderTarget,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, ...]:
    """Return available model IDs, or an empty tuple when discovery fails."""

    owned_client = client is None
    http = client or httpx.AsyncClient(timeout=min(target.timeout_seconds, 10.0))
    try:
        provider = target.provider_name.lower().strip()
        base_url = _base_url(target, provider)
        headers: dict[str, str] = {}
        if provider == "ollama":
            url = f"{base_url}/tags"
        elif provider == "gemini":
            api_key = _api_key(target, "GEMINI_API_KEY")
            if not api_key:
                return ()
            url = f"{base_url}/models"
            headers["x-goog-api-key"] = api_key
        elif provider == "openrouter":
            api_key = _api_key(target, "OPENROUTER_API_KEY")
            if not api_key:
                return ()
            url = f"{base_url}/models"
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            return ()

        response = await http.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        return tuple(sorted(_model_ids(provider, payload)))
    except httpx.HTTPError, OSError, TypeError, ValueError:
        return ()
    finally:
        if owned_client:
            await http.aclose()


def _base_url(target: ProviderTarget, provider: str) -> str:
    defaults = {
        "ollama": OllamaProvider.default_base_url,
        "gemini": GeminiProvider.default_base_url,
        "openrouter": OpenRouterProvider.default_base_url,
    }
    return (target.base_url or defaults[provider]).rstrip("/")


def _api_key(target: ProviderTarget, default_env: str) -> str:
    return target.api_key or (os.getenv(target.api_key_env or default_env) or "")


def _model_ids(provider: str, payload: Any) -> set[str]:
    if not isinstance(payload, Mapping):
        return set()
    items = payload.get("data" if provider == "openrouter" else "models")
    if not isinstance(items, list):
        return set()
    key = "id" if provider == "openrouter" else "name"
    values = {
        str(item.get(key, "")).removeprefix("models/").strip() for item in items if isinstance(item, Mapping) and item.get(key)
    }
    return {value for value in values if value}


__all__ = ["list_provider_models"]
