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
