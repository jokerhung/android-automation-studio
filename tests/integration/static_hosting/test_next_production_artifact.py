# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

"""Production-artifact smoke tests for Next export hosted by FastAPI."""

from pathlib import Path
import re

import pytest
from httpx import ASGITransport, AsyncClient

from apps.admin_console import server

pytestmark = pytest.mark.integration


@pytest.fixture
def next_export(monkeypatch):
    export = Path(__file__).parents[3] / "apps" / "showcase_next" / "out"
    if not (export / "index.html").is_file():
        pytest.skip("production export missing; run npm run build in apps/showcase_next")
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    monkeypatch.setattr(server, "_get_showcase_dist", lambda framework=None: export)
    return export


async def get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=server.app), base_url="http://localhost"
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path, marker",
    [
        ("/", "ARTEMIS"),
        ("/workspace/", "Workspace"),
        ("/task-schedule/", "Task Schedule"),
        ("/settings/", "Settings"),
        ("/check/", "Legacy Check"),
    ],
)
async def test_direct_routes_serve_exported_html(next_export, path, marker):
    response = await get(path)
    assert response.status_code == 200
    assert marker in response.text
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_settings_query_and_emitted_next_asset(next_export):
    settings = await get("/settings/?tab=models")
    assert settings.status_code == 200
    assert "Settings" in settings.text

    match = re.search(r'(?:src|href)="(/_next/static/[^"]+)"', settings.text)
    assert match, "expected an emitted _next asset reference"
    asset = await get(match.group(1))
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.asyncio
async def test_ui_asset_api_404s_and_admin_priority(next_export):
    ui = await get("/not-an-exported-page")
    asset = await get("/_next/static/chunks/definitely-missing.js")
    api = await get("/api/definitely-missing")
    admin = await get("/admin")

    assert ui.status_code == 404 and "Page not found" in ui.text
    assert asset.status_code == 404 and "Page not found" not in asset.text
    assert api.status_code == 404 and "Page not found" not in api.text
    assert admin.status_code == 200 and "Artemis Debug UI" in admin.text
    assert "Page not found" not in admin.text


def test_export_contains_prepaint_preference_bootstrap(next_export):
    html = (next_export / "index.html").read_text(encoding="utf-8")
    bootstrap = html.find("artemis.ui.preferences.v1")
    head_end = html.find("</head>")
    body_start = html.find("<body")
    assert bootstrap >= 0
    assert "document.documentElement.dataset.theme" in html
    assert "document.documentElement.lang" in html
    assert bootstrap < head_end < body_start
