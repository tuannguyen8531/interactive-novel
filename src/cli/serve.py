"""Run the FastAPI application with Uvicorn."""

from __future__ import annotations

import uvicorn

from src.config import get_settings


def main() -> int:
    """Start the local development server."""
    settings = get_settings()
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
