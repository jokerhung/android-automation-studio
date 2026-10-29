# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

"""Unit contract tests for Angular/Next static hosting."""

from pathlib import Path
import shutil
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from apps.admin_console import server


@pytest.fixture
def artifact_root():
    root = Path.cwd() / "test_outputs" / f"static-host-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


async def _get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=server.app), base_url="http://localhost"
    ) as client:
        return await client.get(path)


def _next_export(root: Path) -> Path:
    for route in ("workspace", "task-schedule", "settings", "check"):
        page = root / route / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(f"<html>{route}</html>", encoding="utf-8")
    (root / "index.html").write_text("<html>home</html>", encoding="utf-8")
    (root / "404.html").write_text("<html>next-not-found</html>", encoding="utf-8")
    asset = root / "_next" / "static" / "chunks" / "app-abc123.js"
    asset.parent.mkdir(parents=True)
    asset.write_text("next-asset", encoding="utf-8")
    return root


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "marker"),
    [
        ("/", "home"),
        ("/workspace", "workspace"),
        ("/workspace/", "workspace"),
        ("/task-schedule", "task-schedule"),
        ("/settings/", "settings"),
        ("/check", "check"),
    ],
)
async def test_next_maps_only_exported_routes(artifact_root, monkeypatch, url, marker):
    export = _next_export(artifact_root / "out")
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    monkeypatch.setattr(server, "_get_showcase_dist", lambda framework=None: export)

    response = await _get(url)

    assert response.status_code == 200
    assert marker in response.text
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_next_serves_hashed_assets_and_missing_assets_are_404(artifact_root, monkeypatch):
    export = _next_export(artifact_root / "out")
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    monkeypatch.setattr(server, "_get_showcase_dist", lambda framework=None: export)

    found = await _get("/_next/static/chunks/app-abc123.js")
    missing = await _get("/_next/static/chunks/missing.js")

    assert found.status_code == 200
    assert found.text == "next-asset"
    assert found.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert missing.status_code == 404
    assert "home" not in missing.text


@pytest.mark.asyncio
async def test_next_unknown_route_uses_exported_404_with_404_status(artifact_root, monkeypatch):
    export = _next_export(artifact_root / "out")
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    monkeypatch.setattr(server, "_get_showcase_dist", lambda framework=None: export)

    response = await _get("/not-an-exported-page")

    assert response.status_code == 404
    assert "next-not-found" in response.text
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_next_does_not_intercept_api_or_allow_traversal(artifact_root, monkeypatch):
    export = _next_export(artifact_root / "out")
    secret = artifact_root / "secret.txt"
    secret.write_text("do-not-leak", encoding="utf-8")
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    monkeypatch.setattr(server, "_get_showcase_dist", lambda framework=None: export)

    api = await _get("/api/definitely-missing")
    traversal = await _get("/%2e%2e/secret.txt")

    assert api.status_code == 404
    assert "next-not-found" not in api.text
    assert traversal.status_code == 404
    assert "do-not-leak" not in traversal.text


@pytest.mark.asyncio
async def test_next_is_default_without_selector(artifact_root, monkeypatch):
    export = _next_export(artifact_root / "next-default")
    monkeypatch.delenv("ARTEMIS_FRONTEND", raising=False)
    monkeypatch.setattr(server, "_get_showcase_dist", lambda framework=None: export)
    assert server._get_frontend_framework() == "next"
    assert (await _get("/settings/")).status_code == 200
    assert (await _get("/legacy-client-route")).status_code == 404


def test_angular_selection_is_rejected(monkeypatch):
    monkeypatch.setenv("ARTEMIS_FRONTEND", "angular")
    with pytest.raises(RuntimeError, match="removed"):
        server._get_frontend_framework()


@pytest.mark.asyncio
async def test_missing_next_build_fallback_names_correct_source_and_output(artifact_root, monkeypatch):
    missing = artifact_root / "showcase_next" / "out"
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    monkeypatch.setattr(server, "_get_showcase_dist", lambda framework=None: missing)

    response = await _get("/")

    assert response.status_code == 200
    assert "apps/showcase_next" in response.text
    assert "apps/showcase_next/out" in response.text
    assert response.headers["cache-control"] == "no-cache"
