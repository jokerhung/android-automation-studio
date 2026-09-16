# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

import io
import os
import subprocess
import sys

import pytest
from rich.console import Console
import typer

from artemis.interfaces.cli.commands import ui
from artemis.interfaces.cli.commands.ui import (
    _frontend_framework,
    _npm_install_required,
    _resolve_npm_executable,
    _run_build_step,
    _showcase_build_required,
    ensure_showcase_built,
)


def test_resolve_npm_executable_prefers_windows_command_shim(monkeypatch):
    paths = {
        "npm.cmd": r"C:\Program Files\nodejs\npm.cmd",
        "npm.exe": None,
        "npm": r"C:\Program Files\nodejs\npm.cmd",
    }
    monkeypatch.setattr(ui.shutil, "which", paths.get)

    assert _resolve_npm_executable("win32") == paths["npm.cmd"]


def test_resolve_npm_executable_uses_npm_on_posix(monkeypatch):
    monkeypatch.setattr(
        ui.shutil,
        "which",
        lambda command: "/usr/local/bin/npm" if command == "npm" else None,
    )

    assert _resolve_npm_executable("linux") == "/usr/local/bin/npm"


def test_showcase_build_required_when_source_is_newer(tmp_path):
    showcase_dir = tmp_path / "showcase_next"
    source_file = showcase_dir / "src" / "app" / "agent.service.ts"
    built_index = showcase_dir / "out" / "index.html"
    source_file.parent.mkdir(parents=True)
    built_index.parent.mkdir(parents=True)
    source_file.write_text("source", encoding="utf-8")
    built_index.write_text("build", encoding="utf-8")

    os.utime(built_index, (100, 100))
    os.utime(source_file, (200, 200))

    assert _showcase_build_required(showcase_dir) is True


def test_showcase_build_not_required_when_build_is_current(tmp_path):
    showcase_dir = tmp_path / "showcase_next"
    source_file = showcase_dir / "src" / "app" / "agent.service.ts"
    built_index = showcase_dir / "out" / "index.html"
    source_file.parent.mkdir(parents=True)
    built_index.parent.mkdir(parents=True)
    source_file.write_text("source", encoding="utf-8")
    built_index.write_text("build", encoding="utf-8")

    os.utime(source_file, (100, 100))
    os.utime(built_index, (200, 200))

    assert _showcase_build_required(showcase_dir) is False


def _showcase_with_manifests(tmp_path, *, stamp_mtime=None):
    showcase_dir = tmp_path / "showcase_next"
    showcase_dir.mkdir()
    for name in ("package.json", "package-lock.json"):
        path = showcase_dir / name
        path.write_text("{}", encoding="utf-8")
        os.utime(path, (100, 100))
    if stamp_mtime is not None:
        stamp = showcase_dir / "node_modules" / ".package-lock.json"
        stamp.parent.mkdir()
        stamp.write_text("{}", encoding="utf-8")
        os.utime(stamp, (stamp_mtime, stamp_mtime))
    return showcase_dir


def test_npm_install_required_when_node_modules_missing(tmp_path):
    assert _npm_install_required(_showcase_with_manifests(tmp_path)) is True


def test_npm_install_not_required_when_lock_stamp_is_current(tmp_path):
    assert _npm_install_required(_showcase_with_manifests(tmp_path, stamp_mtime=200)) is False


def test_npm_install_required_when_package_lock_is_newer(tmp_path):
    showcase_dir = _showcase_with_manifests(tmp_path, stamp_mtime=200)
    os.utime(showcase_dir / "package-lock.json", (300, 300))

    assert _npm_install_required(showcase_dir) is True


def _recording_console():
    return Console(file=io.StringIO(), force_terminal=False, width=120)


def test_ensure_showcase_built_skips_install_when_deps_current(monkeypatch):
    steps = []
    monkeypatch.setattr(
        ui, "_showcase_build_required", lambda showcase_dir, framework="next": True
    )
    monkeypatch.setattr(ui, "_npm_install_required", lambda showcase_dir: False)
    monkeypatch.setattr(ui, "_resolve_npm_executable", lambda: "npm")
    monkeypatch.setattr(
        ui, "_run_build_step", lambda console, label, cmd, cwd: steps.append((label, cmd))
    )
    console = _recording_console()

    ensure_showcase_built(console)

    assert [label for label, _ in steps] == ["② next build (static export)"]
    assert steps[0][1] == ["npm", "run", "build"]
    assert "Next.js Showcase UI built in" in console.file.getvalue()


def test_ensure_showcase_built_runs_install_first_when_deps_changed(monkeypatch):
    steps = []
    monkeypatch.setattr(
        ui, "_showcase_build_required", lambda showcase_dir, framework="next": True
    )
    monkeypatch.setattr(ui, "_npm_install_required", lambda showcase_dir: True)
    monkeypatch.setattr(ui, "_resolve_npm_executable", lambda: "npm")
    monkeypatch.setattr(
        ui, "_run_build_step", lambda console, label, cmd, cwd: steps.append((label, cmd))
    )

    ensure_showcase_built(_recording_console())

    assert [label for label, _ in steps] == [
        "① npm ci (dependencies changed)",
        "② next build (static export)",
    ]
    assert steps[0][1] == ["npm", "ci", "--no-audit", "--no-fund", "--loglevel=warn"]


def test_ensure_showcase_built_reports_failure_with_manual_command(monkeypatch):
    monkeypatch.setattr(
        ui, "_showcase_build_required", lambda showcase_dir, framework="next": True
    )
    monkeypatch.setattr(ui, "_npm_install_required", lambda showcase_dir: False)
    monkeypatch.setattr(ui, "_resolve_npm_executable", lambda: "npm")

    def failing_step(console, label, cmd, cwd):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(ui, "_run_build_step", failing_step)
    console = _recording_console()

    with pytest.raises(typer.Exit):
        ensure_showcase_built(console)

    output = console.file.getvalue()
    assert "Failed to auto-build Next.js Showcase UI" in output
    assert "npm ci && npm run build" in output


def test_run_build_step_streams_child_output_and_raises_on_failure(tmp_path):
    console = _recording_console()
    cmd = [sys.executable, "-c", "print('hello from child'); import sys; sys.exit(3)"]

    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        _run_build_step(console, "② next build (static export)", cmd, tmp_path)

    assert excinfo.value.returncode == 3
    output = console.file.getvalue()
    assert "② next build (static export)" in output
    assert "hello from child" in output


def test_run_build_step_strips_ansi_and_succeeds(tmp_path):
    console = _recording_console()
    cmd = [sys.executable, "-c", "print('\\x1b[32mdone\\x1b[0m')"]

    _run_build_step(console, "step", cmd, tmp_path)

    output = console.file.getvalue()
    assert "done" in output
    assert "\x1b[32m" not in output

def test_frontend_framework_defaults_to_next_and_accepts_next(monkeypatch):
    monkeypatch.delenv("ARTEMIS_FRONTEND", raising=False)
    assert _frontend_framework() == "next"
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    assert _frontend_framework() == "next"


def test_frontend_framework_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("ARTEMIS_FRONTEND", "react")
    with pytest.raises(ValueError, match="next"):
        _frontend_framework()


def test_next_showcase_build_uses_out_index(tmp_path):
    showcase_dir = tmp_path / "showcase_next"
    source_file = showcase_dir / "src" / "app" / "page.tsx"
    built_index = showcase_dir / "out" / "index.html"
    source_file.parent.mkdir(parents=True)
    built_index.parent.mkdir(parents=True)
    source_file.write_text("source", encoding="utf-8")
    built_index.write_text("build", encoding="utf-8")
    os.utime(source_file, (100, 100))
    os.utime(built_index, (200, 200))

    assert _showcase_build_required(showcase_dir, "next") is False


def test_ensure_showcase_built_selects_next_app(monkeypatch):
    steps = []
    monkeypatch.setenv("ARTEMIS_FRONTEND", "next")
    monkeypatch.setattr(ui, "_showcase_build_required", lambda path, framework: True)
    monkeypatch.setattr(ui, "_npm_install_required", lambda path: False)
    monkeypatch.setattr(ui, "_resolve_npm_executable", lambda: "npm")
    monkeypatch.setattr(
        ui, "_run_build_step", lambda console, label, cmd, cwd: steps.append((label, cmd, cwd))
    )

    ensure_showcase_built(_recording_console())

    assert steps[0][0] == "② next build (static export)"
    assert steps[0][1] == ["npm", "run", "build"]
    assert steps[0][2].name == "showcase_next"

def test_showcase_build_required_when_public_asset_is_newer(tmp_path):
    showcase_dir = tmp_path / "showcase_next"
    asset = showcase_dir / "public" / "logo.svg"
    built_index = showcase_dir / "out" / "index.html"
    asset.parent.mkdir(parents=True)
    built_index.parent.mkdir(parents=True)
    asset.write_text("asset", encoding="utf-8")
    built_index.write_text("build", encoding="utf-8")
    os.utime(built_index, (100, 100))
    os.utime(asset, (200, 200))

    assert _showcase_build_required(showcase_dir, "next") is True


def test_ui_frontend_option_sets_selected_environment(monkeypatch):
    from typer.testing import CliRunner
    from artemis.interfaces.cli.main import app

    monkeypatch.setattr(ui, "ensure_showcase_built", lambda console: (_ for _ in ()).throw(typer.Exit()))
    result = CliRunner().invoke(app, ["ui", "--frontend", "next", "--no-open"])

    assert result.exit_code == 0
    assert os.environ["ARTEMIS_FRONTEND"] == "next"
