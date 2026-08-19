"""Run the FastAPI application with Uvicorn."""

from __future__ import annotations

import uvicorn

from src.config import get_settings
from src.paths import get_runtime_paths
from src.services.logger import configure_provider_logging


def main() -> int:
    """Start the local development server."""
    settings = get_settings()
    configure_provider_logging(
        get_runtime_paths(settings.runtime_dir).logs,
        retention_days=settings.log_retention_days,
    )
    display_host = "127.0.0.1" if settings.api_host in {"0.0.0.0", "::"} else settings.api_host
    display_url = f"http://{display_host}:{settings.api_port}"
    print(f"Starting service at {display_url}", flush=True)
    uvicorn.run(
        "src.api.factory:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.api_log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
