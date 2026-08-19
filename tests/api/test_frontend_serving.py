from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from src.api.factory import create_app


@pytest.mark.asyncio
async def test_built_spa_serves_index_assets_and_client_routes(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html><body><div id='app'>alpha</div></body></html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('alpha')", encoding="utf-8")
    app = create_app(frontend_dist=dist)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        index = await client.get("/")
        asset = await client.get("/assets/app.js")
        client_route = await client.get("/playthrough/root")
        api_missing = await client.get("/api/missing")

    assert index.status_code == 200
    assert "id='app'" in index.text
    assert asset.status_code == 200
    assert "console.log" in asset.text
    assert client_route.status_code == 200
    assert "id='app'" in client_route.text
    assert api_missing.status_code == 404
    assert api_missing.json()["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_root_explains_when_frontend_has_not_been_built(tmp_path: Path) -> None:
    app = create_app(frontend_dist=tmp_path / "missing-dist")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json()["frontend"] == "missing"
