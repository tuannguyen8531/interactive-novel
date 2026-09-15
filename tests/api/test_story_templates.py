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
    assert all(item["starter_prompt"] != item["description"] for item in response.json() if item["id"] != "custom")
    assert response.json()[0]["starter_prompt"] == (
        "A gentle school romance around a culture club preparing for its first festival. A new member teams up "
        "with the dependable but quietly overwhelmed club president to save a troubled festival project. Shared "
        "errands, late afternoon rehearsals, and a misplaced handwritten note bring them closer, while each "
        "hesitates to say what the festival really means to them."
    )
    assert [item["id"] for item in response.json()] == [
        "school_romance",
        "mystery",
        "fantasy_adventure",
        "custom",
    ]
