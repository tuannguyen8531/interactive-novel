from __future__ import annotations

import os

from src.api.container import _default_provider_config
from src.config import Settings, load_environment


def test_dotenv_values_are_available_to_provider_secret_lookup(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("TEST_PROVIDER_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("TEST_PROVIDER_API_KEY", raising=False)

    load_environment(env_path)

    assert os.getenv("TEST_PROVIDER_API_KEY") == "from-dotenv"


def test_local_provider_defaults_separate_completion_and_embedding_models() -> None:
    settings = Settings(ollama_model="completion-model", ollama_embedding_model="embedding-model")
    config = _default_provider_config(settings)

    assert config.targets["local"].model == "completion-model"
    assert config.targets["local-embedding"].model == "embedding-model"
    assert config.role_routes["embedding"].primary_target == "local-embedding"


def test_provider_routing_defaults_include_env_configurable_cloud_targets() -> None:
    settings = Settings(
        llm_provider="gemini",
        fallback_provider="openrouter",
        execution_mode="fast",
        allow_cloud_routing=True,
        gemini_model="gemini-from-env",
        openrouter_model="openrouter-from-env",
    )

    config = _default_provider_config(settings)

    assert config.targets["gemini"].model == "gemini-from-env"
    assert config.targets["gemini"].api_key_env == "GEMINI_API_KEY"
    assert config.targets["openrouter"].model == "openrouter-from-env"
    assert config.targets["openrouter"].api_key_env == "OPENROUTER_API_KEY"
    assert config.role_routes["writer"].primary_target == "gemini"
    assert config.role_routes["writer"].fallback_targets == ("openrouter",)
    assert config.role_routes["embedding"].primary_target == "local-embedding"
    assert config.mode == "fast"
    assert config.allow_cloud is True


def test_settings_read_first_run_provider_values_from_dotenv(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            (
                "LLM_PROVIDER=openrouter",
                "FALLBACK_PROVIDER=ollama",
                "EXECUTION_MODE=fast",
                "ALLOW_CLOUD_ROUTING=true",
                "OLLAMA_MODEL=ollama-from-env",
                "GEMINI_MODEL=gemini-from-env",
                "OPENROUTER_MODEL=openrouter-from-env",
            )
        ),
        encoding="utf-8",
    )
    for name in (
        "LLM_PROVIDER",
        "FALLBACK_PROVIDER",
        "EXECUTION_MODE",
        "ALLOW_CLOUD_ROUTING",
        "OLLAMA_MODEL",
        "GEMINI_MODEL",
        "OPENROUTER_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    load_environment(env_path)
    settings = Settings()
    config = _default_provider_config(settings)

    assert settings.ollama_model == "ollama-from-env"
    assert config.role_routes["planner"].primary_target == "openrouter"
    assert config.role_routes["planner"].fallback_targets == ("local",)
    assert config.targets["gemini"].model == "gemini-from-env"
    assert config.targets["openrouter"].model == "openrouter-from-env"
    assert config.mode == "fast"
    assert config.allow_cloud is True
