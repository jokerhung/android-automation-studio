"""Host installer contracts. No Android device or device actions are used."""

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import MagicMock

import pytest

from scripts import install_runtime as installer
from artemis.runtime.tray_controller import ArtemisLifecycleAdapter, DaemonPresence


@pytest.fixture
def isolated_install(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "ROOT", tmp_path)
    monkeypatch.setattr(installer, "STATE", tmp_path / ".artemis-install.json")
    monkeypatch.setattr(installer, "OUT", tmp_path / "out")
    monkeypatch.setattr(installer, "LOG", tmp_path / "install.log")
    monkeypatch.setattr(installer, "FRONTEND", tmp_path / "frontend")
    monkeypatch.setattr(installer, "PYTHON", tmp_path / "python")
    return tmp_path


def create_export(root):
    out = root / "out"
    for route in ("index.html", "settings/index.html"):
        page = out / route
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text('<html><script src="/_next/static/app.js"></script></html>')
    asset = out / "_next/static/app.js"
    asset.parent.mkdir(parents=True)
    asset.write_text('console.log("artemis")')
    return out


@contextmanager
def http_server(out, *, fallback=False):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = out / self.path.lstrip("/")
            if self.path.endswith("/"):
                path /= "index.html"
            body = b"<html>Not Built</html>" if fallback else path.read_bytes()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_wildcard_bind_is_verified_via_loopback_but_spawn_retains_bind():
    port_probe = MagicMock(return_value=True)
    identity = MagicMock(return_value=True)
    adapter = ArtemisLifecycleAdapter(
        host="0.0.0.0", port=8123, port_probe=port_probe, identity_probe=identity
    )
    assert adapter.status().presence is DaemonPresence.ARTEMIS
    port_probe.assert_called_once_with(8123, "127.0.0.1", 0.5)
    identity.assert_called_once_with("127.0.0.1", 8123, 0.5)
    spawn = MagicMock(return_value=object())
    stopped = ArtemisLifecycleAdapter(
        host="0.0.0.0", port=8123, port_probe=lambda *_: False, spawn=spawn
    )
    assert stopped.start()
    spawn.assert_called_once_with(host="0.0.0.0", port=8123)


def test_graceful_stop_waits_for_socket_after_identity_metadata_disappears():
    # Initial identity check succeeds. During shutdown the port remains open
    # briefly after metadata disappears; this must not return failure early.
    ports = iter([True, True, False])
    identities = iter([True, False])
    adapter = ArtemisLifecycleAdapter(
        port_probe=lambda *_: next(ports),
        identity_probe=lambda *_: next(identities),
        shutdown=lambda *_: True,
        sleep=lambda _: None,
    )
    assert adapter.stop(timeout=1)


def test_artifact_validation_and_real_http_reject_200_fallback(isolated_install):
    out = create_export(isolated_install)
    assets = installer.frontend_assets()
    with http_server(out) as port:
        assert installer.http_frontend_ready(port, assets)
    with http_server(out, fallback=True) as port:
        assert not installer.http_frontend_ready(port, assets)
    (out / "_next/static/app.js").unlink()
    with pytest.raises(installer.InstallError) as failure:
        installer.frontend_assets()
    assert failure.value.code == 7


def test_unverified_server_cannot_pass_readiness_even_with_real_frontend(isolated_install):
    out = create_export(isolated_install)
    adapter = MagicMock()
    adapter.status.return_value.presence = DaemonPresence.PORT_CONFLICT
    with http_server(out) as port, pytest.raises(installer.InstallError) as failure:
        installer.wait_ready(adapter, port, installer.frontend_assets(), timeout=0.05)
    assert failure.value.code == 8


def test_noninteractive_conflict_never_prompts_or_stops(isolated_install, monkeypatch):
    adapter = MagicMock()
    adapter.status.return_value.presence = DaemonPresence.PORT_CONFLICT
    monkeypatch.setattr(installer, "lifecycle", lambda *_: adapter)
    with pytest.raises(installer.InstallError) as failure:
        installer.choose_port(argparse.Namespace(port=None, non_interactive=True), {}, "0.0.0.0")
    assert failure.value.code == 8
    adapter.stop.assert_not_called()


def test_configuration_is_exclusively_created_and_preserved(isolated_install, monkeypatch):
    import artemis.config.paths as paths

    env, config = isolated_install / ".env", isolated_install / "artemis.jsonc"
    config.write_text('{"agent": {}}')
    (isolated_install / ".env.example").write_text("OPENAI_API_KEY=\n")
    monkeypatch.setattr(paths, "get_env_file", lambda: env)
    monkeypatch.setattr(paths, "get_config_path", lambda _: config)
    installer.initialize_config()
    env.write_text("OPENAI_API_KEY=preserved-secret\n")
    installer.initialize_config()
    assert env.read_text() == "OPENAI_API_KEY=preserved-secret\n"
    config.write_text("{invalid-json-with-secret")
    with pytest.raises(installer.InstallError) as failure:
        installer.initialize_config()
    assert failure.value.code == 6
    assert "secret" not in str(failure.value)
    assert env.read_text() == "OPENAI_API_KEY=preserved-secret\n"


def test_cached_rerun_skips_sync_build_and_preserves_port(isolated_install, monkeypatch):
    create_export(isolated_install)
    state = {
        "dependencies": "deps",
        "frontend": "web",
        "port": 8123,
        "runtime_env": {"ARTEMIS_APP_DIR": str(isolated_install / "user-data")},
    }
    monkeypatch.delenv("ARTEMIS_APP_DIR", raising=False)
    monkeypatch.setattr(installer, "fingerprint", lambda _: "deps")
    monkeypatch.setattr(installer, "frontend_fingerprint", lambda: "web")
    monkeypatch.setattr(installer, "dependencies_current", lambda *_: True)
    run = MagicMock()
    monkeypatch.setattr(installer, "run", run)
    call = MagicMock(return_value=0)
    monkeypatch.setattr(installer.subprocess, "call", call)
    args = argparse.Namespace(
        uv="uv", port=None, local_only=False, non_interactive=True, open=False
    )
    assert installer.prepare(args, state) == 0
    run.assert_not_called()
    assert json.loads(installer.STATE.read_text())["port"] == 8123
    assert json.loads(installer.STATE.read_text())["runtime_env"]["ARTEMIS_APP_DIR"] == str(
        isolated_install / "user-data"
    )
    assert "_finish" in call.call_args.args[0]


def test_native_failure_and_timeout_stop_pipeline(isolated_install):
    with pytest.raises(installer.InstallError) as failure:
        installer.run([sys.executable, "-c", "raise SystemExit(7)"], cwd=isolated_install, code=7)
    assert failure.value.code == 7
    with pytest.raises(installer.InstallError) as failure:
        installer.run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=isolated_install,
            timeout=0.05,
            code=5,
        )
    assert failure.value.code == 5


def test_output_has_actual_port_and_local_only_has_no_lan(isolated_install, monkeypatch, capsys):
    import artemis.runtime.network_urls as network

    monkeypatch.setattr(network, "lan_addresses", lambda: [("Wi-Fi", "192.168.1.7", False)])
    installer.show_access(8123, "0.0.0.0")
    output = capsys.readouterr().out
    assert "http://localhost:8123" in output
    assert "http://127.0.0.1:8123" in output
    assert "http://192.168.1.7:8123" in output
    assert "http://0.0.0.0" not in output
    installer.show_access(8123, "127.0.0.1")
    assert "192.168.1.7" not in capsys.readouterr().out


def test_default_install_bind_ignores_stale_loopback_state():
    assert installer.bind_host(argparse.Namespace(local_only=False)) == "0.0.0.0"
    assert installer.bind_host(argparse.Namespace(local_only=True)) == "127.0.0.1"
