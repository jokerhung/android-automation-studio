# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import FastAPI


SCRIPT = Path(__file__).parents[2] / "scripts" / "measure_frontend_artifacts.py"
spec = importlib.util.spec_from_file_location("measure_frontend_artifacts", SCRIPT)
assert spec is not None and spec.loader is not None
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


def test_inventory_is_sorted_and_counts_exact_bytes(tmp_path):
    root = tmp_path / "out"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_bytes(b"html")
    (root / "assets" / "z.js").write_bytes(b"12345")
    (root / "assets" / "a.css").write_bytes(b"123")
    (root / "ignored.txt").write_bytes(b"xx")

    result = measure.inventory("next", root)

    assert result["status"] == "ok"
    assert result["file_count"] == 4
    assert result["total_bytes"] == 14
    assert result["bytes_by_type"] == {"html": 4, "css": 3, "js": 5}
    assert [item["path"] for item in result["files"]] == [
        "assets/a.css", "assets/z.js", "ignored.txt", "index.html"
    ]


def test_missing_artifact_is_clear_json_and_nonzero(tmp_path, capsys):
    angular = tmp_path / "angular"
    angular.mkdir()
    (angular / "index.html").write_text("ok", encoding="utf-8")

    exit_code = measure.main(["--angular-root", str(angular), "--next-root", str(tmp_path / "missing")])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert output["comparison"] is None
    assert output["artifacts"]["next"]["status"] == "missing"
    assert "does not exist" in output["artifacts"]["next"]["error"]
    assert output["scope"]["browser_performance"] is False


@pytest.mark.asyncio
async def test_asgi_measurement_uses_multiple_first_and_subsequent_samples(monkeypatch):
    app = FastAPI()

    @app.get("/")
    async def root():
        return {"ok": True}

    ticks = iter(range(0, 18_000_000, 1_000_000))
    rss = iter([100, 140])
    monkeypatch.setenv("ARTEMIS_FRONTEND", "original")

    result = await measure.measure_asgi_selector(
        "next",
        app,
        samples=3,
        subsequent_requests=2,
        path="/",
        clock_ns=lambda: next(ticks),
        rss_reader=lambda: next(rss),
    )

    assert result["first_response"]["samples_ms"] == [1.0, 1.0, 1.0]
    assert result["subsequent_response"]["samples_ms"] == [1.0] * 6
    assert result["process_rss"]["delta_bytes"] == 40
    assert result["status_codes"] == [200]
    assert "no network/server/browser" in result["transport"]
    assert __import__("os").environ["ARTEMIS_FRONTEND"] == "original"
