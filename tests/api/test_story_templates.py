from __future__ import annotations

import httpx
import pytest

from src.api.factory import create_app
from src.config import Settings


@pytest.mark.asyncio
async def test_story_template_catalog_endpoint_returns_bundled_templates() -> None:
    app = create_app(Settings(app_name="story-template-api-test"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/story-templates")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        "school_romance",
        "mystery",
        "fantasy_adventure",
    ]
