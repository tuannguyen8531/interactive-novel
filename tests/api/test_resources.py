from types import SimpleNamespace

import httpx
import pytest

from src.api.factory import create_app
from src.application.errors import ResourceNotFoundError
from src.config import Settings


class _WorldService:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete_world(self, world_id: str) -> None:
        if world_id == "missing":
            raise ResourceNotFoundError(f"World {world_id} does not exist.")
        self.deleted.append(world_id)


@pytest.mark.asyncio
async def test_delete_world_returns_no_content_and_maps_missing_resources() -> None:
    worlds = _WorldService()
    app = create_app(
        Settings(app_name="resources-api-test"),
        services=SimpleNamespace(worlds=worlds),  # type: ignore[arg-type]
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        deleted = await client.delete("/api/worlds/world-1")
        missing = await client.delete("/api/worlds/missing")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert worlds.deleted == ["world-1"]
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
