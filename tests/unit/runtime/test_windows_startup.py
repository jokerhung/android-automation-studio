from unittest.mock import MagicMock, patch

import pytest

from artemis.runtime import windows_startup as startup


@pytest.fixture
def registry(monkeypatch):
    registry = MagicMock()
    registry.QueryValueEx.side_effect = FileNotFoundError
    monkeypatch.setitem(__import__("sys").modules, "winreg", registry)
    monkeypatch.setattr(startup.sys, "platform", "win32")
    return registry


def test_read_does_not_create_startup_entry(registry):
    assert startup.get_startup_status() == {"supported": True, "enabled": False, "port": None}
    registry.SetValueEx.assert_not_called()
    registry.CreateKeyEx.assert_not_called()


def test_enable_uses_pythonw_and_current_port(registry):
    with patch.object(startup, "startup_command", return_value="pythonw.exe runner.py --port 8009"):
        startup.set_startup_enabled(True, 8009)
    assert registry.SetValueEx.call_args.args[1] == "Artemis"
    assert registry.SetValueEx.call_args.args[-1].endswith("--port 8009")
    assert registry.CreateKeyEx.call_args.args[0] == registry.HKEY_CURRENT_USER


def test_disable_only_deletes_owned_value(registry):
    startup.set_startup_enabled(False, 8009)
    assert registry.DeleteValue.call_args.args[1] == "Artemis"
    registry.DeleteKey.assert_not_called()


def test_status_reads_registered_port(registry):
    registry.QueryValueEx.side_effect = None
    registry.QueryValueEx.return_value = ("pythonw.exe runner.py --port 8009", 1)
    assert startup.get_startup_status()["port"] == 8009


def test_command_quotes_paths_without_console_or_browser(registry, tmp_path, monkeypatch):
    root = tmp_path / "Python With Spaces"
    root.mkdir()
    (root / "pythonw.exe").touch()
    monkeypatch.setattr(startup.sys, "executable", str(root / "python.exe"))
    cmd = startup.startup_command(8009)
    assert cmd.startswith('"')
    assert 'pythonw.exe"' in cmd
    assert "--port 8009" in cmd
    assert "--working-directory" in cmd
    assert "restart" not in cmd


def test_unsupported_platform(monkeypatch):
    monkeypatch.setattr(startup.sys, "platform", "linux")
    assert not startup.get_startup_status()["supported"]
    with pytest.raises(NotImplementedError):
        startup.set_startup_enabled(True, 8009)


def test_logon_orchestrates_identity_aware_background_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(
        startup.sys, "argv", ["startup", "--working-directory", str(tmp_path), "--port", "8009"]
    )
    result = MagicMock(ok=True, daemon_started=True, tray_running=True, detail="")
    with (
        patch.object(startup.os, "chdir"),
        patch(
            "artemis.runtime.background_runtime.ensure_background_runtime", return_value=result
        ) as ensure,
        patch("artemis.runtime.background_runtime.WindowsTrayRuntimeAdapter") as tray,
        patch("artemis.runtime.tray_controller.ArtemisLifecycleAdapter") as lifecycle,
        patch("artemis.runtime.tray_launcher._configure_launcher_logging"),
    ):
        startup.main()
    tray.assert_called_once_with(workspace=tmp_path)
    lifecycle.assert_called_once_with(host="127.0.0.1", port=8009)
    ensure.assert_called_once_with(
        host="127.0.0.1",
        port=8009,
        lifecycle=lifecycle.return_value,
        tray=tray.return_value,
        wait_timeout=60.0,
    )
