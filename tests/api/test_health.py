import httpx
import pytest

from src.api.factory import create_app
from src.config import Settings


@pytest.mark.asyncio
async def test_health_endpoint_returns_service_metadata() -> None:
    app = create_app(Settings(app_name="test-novel", app_version="9.9.9"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "test-novel",
        "version": "9.9.9",
    }


@pytest.mark.asyncio
async def test_unknown_route_uses_error_envelope() -> None:
    app = create_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Not Found",
            "details": {},
        }
    }
