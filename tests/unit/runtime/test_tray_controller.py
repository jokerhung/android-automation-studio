import threading

from artemis.runtime.tray_controller import (
    ArtemisLifecycleAdapter,
    DaemonPresence,
    DrainChoice,
    LifecycleStatus,
    TrayController,
    TrayState,
    WorkloadStatus,
)


class FakeLifecycle:
    def __init__(self, presence=DaemonPresence.STOPPED):
        self.presence = presence
        self.start_calls = 0
        self.stop_calls = 0
        self.wait_entered = threading.Event()
        self.wait_release = threading.Event()
        self.wait_release.set()

    def status(self):
        return LifecycleStatus(
            self.presence, "conflict" if self.presence is DaemonPresence.PORT_CONFLICT else ""
        )

    def start(self):
        self.start_calls += 1
        return True

    def wait_running(self, *, timeout):
        self.wait_entered.set()
        self.wait_release.wait(1)
        self.presence = DaemonPresence.ARTEMIS
        return self.status()

    def stop(self, *, timeout):
        self.stop_calls += 1
        self.presence = DaemonPresence.STOPPED
        return True


class FakeDrain:
    def __init__(self, workload=WorkloadStatus(), drained=True):
        self.value, self.drained = workload, drained
        self.begin_calls = self.cancel_calls = 0

    def workload(self):
        return self.value

    def begin_drain(self):
        self.begin_calls += 1
        return True

    def wait_drained(self, *, timeout):
        return self.drained

    def cancel_unfinished(self):
        self.cancel_calls += 1
        return True


class FakeConfirmation:
    def __init__(self, choice=DrainChoice.WAIT, timeout_choice=DrainChoice.CANCEL):
        self.choice, self.timeout_choice = choice, timeout_choice

    def choose(self, workload, *, for_exit):
        return self.choice

    def choose_after_timeout(self, workload, *, for_exit):
        return self.timeout_choice


class FakeBrowser:
    def __init__(self):
        self.urls = []

    def open(self, url):
        self.urls.append(url)
        return True


class FakeOpenConfirmation:
    def __init__(self, answer=True):
        self.answer = answer

    def confirm_start_and_open(self):
        return self.answer


def controller(lifecycle=None, drain=None, confirmation=None, open_confirmation=None):
    return TrayController(
        port=8009,
        lifecycle=lifecycle or FakeLifecycle(),
        drain=drain or FakeDrain(),
        confirmation=confirmation or FakeConfirmation(),
        browser=FakeBrowser(),
        open_confirmation=open_confirmation or FakeOpenConfirmation(),
        startup_timeout=0.1,
        stop_timeout=0.1,
    )


def test_start_attaches_without_duplicate_spawn():
    life = FakeLifecycle(DaemonPresence.ARTEMIS)
    result = controller(lifecycle=life).start()
    assert result.ok and result.snapshot.state is TrayState.RUNNING
    assert life.start_calls == 0


def test_start_refuses_port_conflict_without_spawn():
    life = FakeLifecycle(DaemonPresence.PORT_CONFLICT)
    result = controller(lifecycle=life).start()
    assert not result.ok and result.snapshot.state is TrayState.PORT_CONFLICT
    assert life.start_calls == 0


def test_serialized_double_start_only_spawns_once():
    life = FakeLifecycle()
    life.wait_release.clear()
    tray = controller(lifecycle=life)
    first = []
    thread = threading.Thread(target=lambda: first.append(tray.start()))
    thread.start()
    assert life.wait_entered.wait(1)
    second = tray.start()
    life.wait_release.set()
    thread.join()
    assert not second.ok and "operation" in second.detail
    assert first[0].ok and life.start_calls == 1


def test_busy_stop_waits_for_drain_then_stops():
    life = FakeLifecycle(DaemonPresence.ARTEMIS)
    drain = FakeDrain(WorkloadStatus(active_tasks=1))
    result = controller(lifecycle=life, drain=drain).stop()
    assert result.ok and result.snapshot.state is TrayState.STOPPED
    assert drain.begin_calls == 1 and life.stop_calls == 1


def test_stop_now_cancels_work_before_graceful_stop():
    life = FakeLifecycle(DaemonPresence.ARTEMIS)
    drain = FakeDrain(WorkloadStatus(queued_tasks=2))
    result = controller(
        lifecycle=life, drain=drain, confirmation=FakeConfirmation(DrainChoice.STOP_NOW)
    ).stop()
    assert result.ok and drain.cancel_calls == 1 and life.stop_calls == 1


def test_cancel_keeps_server_running():
    life = FakeLifecycle(DaemonPresence.ARTEMIS)
    drain = FakeDrain(WorkloadStatus(active_tasks=1))
    result = controller(
        lifecycle=life, drain=drain, confirmation=FakeConfirmation(DrainChoice.CANCEL)
    ).exit()
    assert not result.ok and result.snapshot.state is TrayState.RUNNING
    assert life.stop_calls == 0 and not result.snapshot.exit_requested


def test_drain_timeout_requires_explicit_stop_now():
    life = FakeLifecycle(DaemonPresence.ARTEMIS)
    drain = FakeDrain(WorkloadStatus(paused_tasks=1), drained=False)
    result = controller(
        lifecycle=life,
        drain=drain,
        confirmation=FakeConfirmation(timeout_choice=DrainChoice.CANCEL),
    ).stop()
    assert not result.ok and result.snapshot.state is TrayState.RUNNING
    assert life.stop_calls == 0


def test_exit_only_marks_exited_after_verified_stop():
    life = FakeLifecycle(DaemonPresence.ARTEMIS)
    result = controller(lifecycle=life).exit()
    assert result.ok and result.snapshot.state is TrayState.EXITED
    assert result.snapshot.exit_requested


def test_open_stopped_starts_then_opens_configured_url():
    life = FakeLifecycle()
    tray = controller(lifecycle=life)
    result = tray.open_homepage()
    assert result.ok and result.opened_url == "http://localhost:8009/"
    assert tray.browser.urls == ["http://localhost:8009/"]


def test_open_stopped_can_be_cancelled_without_spawn():
    life = FakeLifecycle()
    result = controller(
        lifecycle=life, open_confirmation=FakeOpenConfirmation(False)
    ).open_homepage()
    assert not result.ok and life.start_calls == 0


def test_real_adapter_classifies_conflict_and_never_spawns():
    spawned = []
    adapter = ArtemisLifecycleAdapter(
        port=8009,
        port_probe=lambda *a: True,
        identity_probe=lambda *a: False,
        spawn=lambda **kw: spawned.append(kw),
    )
    assert adapter.status().presence is DaemonPresence.PORT_CONFLICT
    assert not adapter.start() and not adapter.stop(timeout=1)
    assert spawned == []


def test_real_adapter_stop_uses_token_shutdown_only_after_identity():
    occupied = [True]
    calls = []
    adapter = ArtemisLifecycleAdapter(
        port=8009,
        poll_interval=0,
        port_probe=lambda *a: occupied[0],
        identity_probe=lambda *a: True,
        shutdown=lambda port, timeout: (
            calls.append((port, timeout)) or occupied.__setitem__(0, False) or True
        ),
        sleep=lambda _: None,
    )
    assert adapter.stop(timeout=1)
    assert calls == [(8009, 1)]
