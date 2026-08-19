"""Application settings for the Phase 1 runtime shell."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings with safe local-first defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "interactive-novel"
    app_version: str = "0.1.0"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_log_level: str = "info"
    cors_origins: str = "http://localhost:5173"
    # Avoid colliding with deployment environments that reserve DEBUG for a
    # non-boolean release/profile label. Use INTERACTIVE_NOVEL_DEBUG instead.
    debug: bool = Field(default=False, validation_alias="INTERACTIVE_NOVEL_DEBUG")
    runtime_dir: Path = Path("runtime")
    database_busy_timeout_ms: int = Field(default=5_000, ge=0)
    database_echo: bool = False
    turn_max_concurrency: int = Field(default=2, ge=1, le=32)
    sse_history_size: int = Field(default=256, ge=1, le=10_000)

    def cors_origin_list(self) -> list[str]:
        """Return configured exact CORS origins in stable order."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache process settings."""
    return Settings()


__all__ = ["Settings", "get_settings"]
