"""Application settings for the runtime shell."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.paths import PROJECT_ROOT

ENV_FILE = PROJECT_ROOT / ".env"
# Pydantic reads declared application fields from .env. Provider adapters use
# os.getenv(api_key_env), so load the same file into the process environment
# without overriding variables explicitly supplied by the shell.


def load_environment(path: Path = ENV_FILE) -> None:
    load_dotenv(path, override=False)


load_environment()


class Settings(BaseSettings):
    """Environment-backed settings with safe local-first defaults."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "interactive-novel"
    app_version: str = "0.1.0"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_log_level: str = "info"
    log_retention_days: int = Field(default=30, ge=1, le=3_650)
    cors_origins: str = "http://localhost:5173"
    # Avoid colliding with deployment environments that reserve DEBUG for a
    # non-boolean release/profile label. Use INTERACTIVE_NOVEL_DEBUG instead.
    debug: bool = Field(default=False, validation_alias="INTERACTIVE_NOVEL_DEBUG")
    runtime_dir: Path = Path("runtime")
    database_busy_timeout_ms: int = Field(default=5_000, ge=0)
    database_echo: bool = False
    turn_max_concurrency: int = Field(default=2, ge=1, le=32)
    sse_history_size: int = Field(default=256, ge=1, le=10_000)
    telemetry_enabled: bool = False
    telemetry_prompt_cost_per_1k_tokens: float = Field(default=0.0, ge=0.0)
    telemetry_completion_cost_per_1k_tokens: float = Field(default=0.0, ge=0.0)
    telemetry_max_samples: int = Field(default=10_000, ge=1, le=1_000_000)
    input_max_chars: int = Field(default=20_000, ge=256, le=100_000)
    llm_provider: Literal["ollama", "gemini", "openrouter"] = "ollama"
    fallback_provider: Literal["", "ollama", "gemini", "openrouter"] = ""
    execution_mode: Literal["quality", "fast"] = "quality"
    allow_cloud_routing: bool = False
    ollama_base_url: str = "http://localhost:11434/api"
    ollama_model: str = "llama3.2:3b"
    ollama_embedding_model: str = "nomic-embed-text:latest"
    gemini_model: str = "gemini-2.5-flash"
    openrouter_model: str = "qwen/qwen3-8b"

    def cors_origin_list(self) -> list[str]:
        """Return configured exact CORS origins in stable order."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache process settings."""
    return Settings()


__all__ = ["ENV_FILE", "Settings", "get_settings", "load_environment"]
