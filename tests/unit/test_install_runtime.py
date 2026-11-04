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


@pytest.fixture
def settings_install(isolated_install, monkeypatch):
    import artemis.config.paths as paths
    from artemis.config.sqlite_store import MODEL_ENV_KEYS, SettingsStore

    env, config = isolated_install / ".env", isolated_install / "artemis.jsonc"
    config.write_text('{"default":{"provider":"openai","model":"install-default"}}')
    monkeypatch.setattr(paths, "get_env_file", lambda: env)
    monkeypatch.setattr(paths, "get_config_path", lambda _: config)
    monkeypatch.setenv("DATA_ENGINE_DB_PATH", str(isolated_install / "data" / "settings.db"))
    monkeypatch.setenv("APPDATA", str(isolated_install / "appdata"))
    monkeypatch.delenv("ARTEMIS_ARTEMIS_JSONC", raising=False)
    for key in MODEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return env, config, SettingsStore()


@pytest.mark.parametrize("platform_name", ["win32", "linux", "darwin"])
def test_fresh_install_creates_sqlite_defaults_without_dotenv(
    settings_install, monkeypatch, platform_name
):
    import apps.admin_console.services.email_settings_service as email

    env, _, store = settings_install
    # Fresh Ubuntu/macOS installs must not require Windows DPAPI.
    monkeypatch.setattr(email.sys, "platform", platform_name)
    secret_store = MagicMock()
    secret_store.get.return_value = None
    factory = MagicMock(return_value=secret_store)
    monkeypatch.setattr(email, "create_secret_store", factory)
    installer.initialize_config()
    assert store.path.is_file()
    assert not env.exists()
    model, version = store.model()
    assert version == 1
    assert model["config"]["default"]["model"] == "install-default"
    assert not any(model["credentials"].values())
    document, version = store.get_or_import("email", lambda: pytest.fail("missing email"))
    assert version == 1
    assert document["password"] is None
    assert document["settings"] == {
        "smtp_host": "",
        "smtp_port": 587,
        "security": "starttls",
        "smtp_username": "",
        "sender_email": "",
        "sender_name": "Artemis",
        "enabled": False,
        "version": 0,
    }
    assert factory.call_count == (1 if platform_name == "win32" else 0)


def test_install_preserves_sqlite_and_imports_legacy_once(settings_install):
    env, config, store = settings_install
    env.write_text("OPENAI_API_KEY=legacy-test-key\n")
    installer.initialize_config()
    assert store.model()[0]["credentials"]["OPENAI_API_KEY"] == "legacy-test-key"
    store.update("model", lambda doc: {**doc, "credentials": {"OPENAI_API_KEY": "db-test-key"}})
    store.update("email", lambda doc: {**doc, "password": "preserved-encrypted-password"})
    before_model = store.model()
    before_email = store.get_or_import("email", lambda: None)
    env.write_text("OPENAI_API_KEY=changed-test-key\n")
    config.write_text('{"default":{"provider":"google","model":"changed"}}')
    installer.initialize_config()
    assert store.model() == before_model
    assert store.get_or_import("email", lambda: None) == before_email
    assert env.read_text() == "OPENAI_API_KEY=changed-test-key\n"
    config.write_text("{invalid-json-with-secret")
    with pytest.raises(installer.InstallError) as failure:
        installer.initialize_config()
    assert failure.value.code == 6
    assert "secret" not in str(failure.value)
    assert store.model() == before_model


def test_cached_rerun_skips_sync_build_and_preserves_port(isolated_install, monkeypatch):
    create_export(isolated_install)
    state = {
        "schema": 1,
        "source": "jokerhung/android-automation-studio",
        "dependencies": "deps",
        "frontend": "web",
        "port": 8123,
        "runtime_env": {
            "ARTEMIS_APP_DIR": str(isolated_install / "user-data"),
            "DATA_ENGINE_DB_PATH": str(isolated_install / "custom.db"),
        },
    }
    monkeypatch.delenv("ARTEMIS_APP_DIR", raising=False)
    monkeypatch.delenv("DATA_ENGINE_DB_PATH", raising=False)
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
    run.assert_called_once()
    assert "_configure" in run.call_args.args[0]
    assert "--non-interactive" in run.call_args.args[0]
    assert json.loads(installer.STATE.read_text())["port"] == 8123
    assert json.loads(installer.STATE.read_text())["runtime_env"]["ARTEMIS_APP_DIR"] == str(
        isolated_install / "user-data"
    )
    assert "_finish" in call.call_args.args[0]
    assert installer.read_state()["runtime_env"]["DATA_ENGINE_DB_PATH"] == str(
        isolated_install / "custom.db"
    )


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
