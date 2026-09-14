import threading
from unittest.mock import MagicMock, patch

from artemis.runtime.background_runtime import (
    BackgroundOperationRunner,
    WindowsTrayRuntimeAdapter,
    ensure_background_runtime,
)
from artemis.runtime.tray_controller import DaemonPresence, LifecycleStatus


class FakeLifecycle:
    def __init__(self, presence):
        self.presence = presence
        self.starts = 0

    def status(self):
        return LifecycleStatus(
            self.presence, "port conflict" if self.presence is DaemonPresence.PORT_CONFLICT else ""
        )

    def start(self):
        self.starts += 1
        return True

    def wait_running(self, *, timeout):
        self.presence = DaemonPresence.ARTEMIS
        return self.status()


class FakeTray:
    def __init__(self, available=True, succeeds=True):
        self.is_available = available
        self.succeeds = succeeds
        self.calls = []

    def available(self):
        return self.is_available

    def ensure_running(self, *, host, port):
        self.calls.append((host, port))
        return self.succeeds


def test_orchestration_attaches_existing_daemon_and_ensures_tray():
    life = FakeLifecycle(DaemonPresence.ARTEMIS)
    tray = FakeTray()
    result = ensure_background_runtime(host="127.0.0.1", port=8009, lifecycle=life, tray=tray)
    assert result.ok and not result.daemon_started and life.starts == 0
    assert tray.calls == [("127.0.0.1", 8009)]


def test_orchestration_refuses_conflict_without_spawn():
    life = FakeLifecycle(DaemonPresence.PORT_CONFLICT)
    result = ensure_background_runtime(host="127.0.0.1", port=8009, lifecycle=life, tray=FakeTray())
    assert not result.ok and life.starts == 0
    assert result.daemon_status.presence is DaemonPresence.PORT_CONFLICT


def test_orchestration_starts_daemon_without_interactive_tray():
    life = FakeLifecycle(DaemonPresence.STOPPED)
    result = ensure_background_runtime(
        host="127.0.0.1", port=8009, lifecycle=life, tray=FakeTray(available=False)
    )
    assert result.ok and result.daemon_started and life.starts == 1
    assert not result.tray_available


def test_background_runner_serializes_operations_on_one_worker():
    entered = threading.Event()
    release = threading.Event()
    order = []

    def first():
        entered.set()
        release.wait(1)
        order.append("first")

    def second():
        order.append("second")

    with BackgroundOperationRunner() as runner:
        one = runner.submit(first)
        assert entered.wait(1)
        two = runner.submit(second)
        assert not two.done()
        release.set()
        one.result(timeout=1)
        two.result(timeout=1)
    assert order == ["first", "second"]


def test_windows_tray_adapter_attaches_without_spawning(tmp_path, monkeypatch):
    adapter = WindowsTrayRuntimeAdapter(workspace=tmp_path, popen=MagicMock())
    monkeypatch.setattr("artemis.runtime.background_runtime.sys.platform", "win32")
    with patch("artemis.runtime.tray_instance.attach_existing", return_value=True) as attach:
        assert adapter.ensure_running(host="127.0.0.1", port=8009)
    attach.assert_called_once()
    adapter._popen.assert_not_called()


def test_windows_tray_adapter_spawns_targeted_launcher(tmp_path):
    popen = MagicMock()
    adapter = WindowsTrayRuntimeAdapter(workspace=tmp_path, popen=popen)
    with patch("artemis.runtime.tray_instance.attach_existing", return_value=False):
        assert adapter.ensure_running(host="127.0.0.1", port=8009)
    command = popen.call_args.args[0]
    assert command[1:3] == ["-m", "artemis.runtime.tray_launcher"]
    assert command[-4:] == ["--port", "8009", "--workspace", str(tmp_path.resolve())]
