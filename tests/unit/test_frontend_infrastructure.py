# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from artemis.interfaces.cli.commands import doctor


def _load_setup_module():
    setup_path = Path(__file__).parents[2] / "setup.py"
    spec = importlib.util.spec_from_file_location("artemis_setup_contract", setup_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with patch("setuptools.setup"):
        spec.loader.exec_module(module)
    return module


def _source_tree(tmp_path, framework):
    source = tmp_path / "source"
    (source / "config").mkdir(parents=True)
    (source / "config" / "artemis.jsonc").write_text("{}", encoding="utf-8")
    if framework == "next":
        artifact = source / "apps" / "showcase_next" / "out"
    else:
        artifact = source / "apps" / "showcase_ui" / "dist" / "frontend" / "browser"
    artifact.mkdir(parents=True)
    (artifact / "index.html").write_text(framework, encoding="utf-8")
    (artifact / "assets").mkdir()
    (artifact / "assets" / "bundle.js").write_text("bundle", encoding="utf-8")
    return source


@pytest.mark.parametrize(
    ("framework", "resource"),
    [("next", "showcase_next")],
)
def test_setup_copies_selected_frontend_tree_and_manifest(tmp_path, monkeypatch, framework, resource):
    module = _load_setup_module()
    source = _source_tree(tmp_path, framework)
    target = tmp_path / "target"
    (target / "showcase_ui").mkdir(parents=True)
    (target / "showcase_ui" / "stale.js").write_text("stale", encoding="utf-8")
    monkeypatch.setenv("ARTEMIS_FRONTEND_PACKAGE", framework)

    module._copy_release_resources(source, target)

    bundled = target / resource
    assert (bundled / "index.html").is_file()
    assert (bundled / "assets" / "bundle.js").is_file()
    assert not (target / "showcase_ui").exists()
    assert json.loads((bundled / "frontend-manifest.json").read_text(encoding="utf-8"))[
        "framework"
    ] == framework


def test_setup_package_selector_falls_back_to_runtime_selector(monkeypatch):
    module = _load_setup_module()
    monkeypatch.delenv("ARTEMIS_FRONTEND_PACKAGE", raising=False)
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    assert module._selected_frontend() == "next"


def test_doctor_reports_selected_next_export(tmp_path, monkeypatch):
    export = tmp_path / "apps" / "showcase_next" / "out"
    export.mkdir(parents=True)
    (export / "index.html").write_text("next", encoding="utf-8")
    monkeypatch.setattr(doctor, "ROOT_DIR", tmp_path)
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")

    row = doctor._showcase_row()

    assert row.status == "pass"
    assert "Next.js ready" in row.detail


def test_doctor_rejects_invalid_frontend_selection(monkeypatch):
    monkeypatch.setenv("ARTEMIS_FRONTEND", "react")
    row = doctor._showcase_row()
    assert row.status == "missing"
    assert "next" in row.detail
