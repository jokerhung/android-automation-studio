# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""UI-independent system-tray lifecycle state machine and safe adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import threading
import time
from typing import Callable, Protocol


class DaemonPresence(str, Enum):
    STOPPED = "stopped"
    ARTEMIS = "artemis"
    PORT_CONFLICT = "port_conflict"
    UNVERIFIED = "unverified"


class TrayState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPING = "stopping"
    PORT_CONFLICT = "port_conflict"
    ERROR = "error"
    EXITED = "exited"


class DrainChoice(str, Enum):
    WAIT = "wait"
    STOP_NOW = "stop_now"
    CANCEL = "cancel"


@dataclass(frozen=True)
class LifecycleStatus:
    presence: DaemonPresence
    detail: str = ""

    @property
    def identity_verified(self) -> bool:
        return self.presence is DaemonPresence.ARTEMIS


@dataclass(frozen=True)
class WorkloadStatus:
    active_tasks: int = 0
    queued_tasks: int = 0
    sending_email: bool = False
    paused_tasks: int = 0

    @property
    def busy(self) -> bool:
        return bool(
            self.active_tasks or self.queued_tasks or self.sending_email or self.paused_tasks
        )


@dataclass(frozen=True)
class TraySnapshot:
    state: TrayState
    port: int
    detail: str = ""
    operation_id: int = 0
    exit_requested: bool = False

    @property
    def homepage_url(self) -> str:
        return f"http://localhost:{self.port}/"


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    snapshot: TraySnapshot
    detail: str = ""
    opened_url: str | None = None


class LifecycleAdapter(Protocol):
    def status(self) -> LifecycleStatus: ...
    def start(self) -> bool: ...
    def stop(self, *, timeout: float) -> bool: ...


class DrainAdapter(Protocol):
    def workload(self) -> WorkloadStatus: ...
    def begin_drain(self) -> bool: ...
    def wait_drained(self, *, timeout: float) -> bool: ...
    def cancel_unfinished(self) -> bool: ...


class DrainConfirmation(Protocol):
    def choose(self, workload: WorkloadStatus, *, for_exit: bool) -> DrainChoice: ...
    def choose_after_timeout(self, workload: WorkloadStatus, *, for_exit: bool) -> DrainChoice: ...


class BrowserAdapter(Protocol):
    def open(self, url: str) -> bool: ...


class OpenConfirmation(Protocol):
    def confirm_start_and_open(self) -> bool: ...


class ArtemisLifecycleAdapter:
    """Fail-closed adapter over daemon primitives; never kills a port owner."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8000,
        poll_interval: float = 0.1,
        port_probe: Callable[[int, str, float], bool] | None = None,
        identity_probe: Callable[[str, int, float], bool] | None = None,
        spawn: Callable[..., object | None] | None = None,
        shutdown: Callable[[int, float], bool] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        from artemis.runtime.daemon_client import is_artemis_daemon, spawn_daemon
        from artemis.runtime.server_lifecycle import is_port_in_use, request_graceful_shutdown

        self.host, self.port, self.poll_interval = host, port, poll_interval
        self._port_probe = port_probe or is_port_in_use
        self._identity_probe = identity_probe or is_artemis_daemon
        self._spawn = spawn or spawn_daemon
        self._shutdown = shutdown or request_graceful_shutdown
        self._sleep, self._monotonic = sleep, monotonic

    def status(self) -> LifecycleStatus:
        if not self._port_probe(self.port, self.host, 0.5):
            return LifecycleStatus(DaemonPresence.STOPPED)
        if self._identity_probe(self.host, self.port, 0.5):
            return LifecycleStatus(DaemonPresence.ARTEMIS)
        return LifecycleStatus(
            DaemonPresence.PORT_CONFLICT,
            f"Port {self.port} is occupied by a process not verified as ARTEMIS.",
        )

    def start(self) -> bool:
        status = self.status()
        if status.presence is DaemonPresence.ARTEMIS:
            return True
        if status.presence is not DaemonPresence.STOPPED:
            return False
        return self._spawn(host=self.host, port=self.port) is not None

    def wait_running(self, *, timeout: float) -> LifecycleStatus:
        deadline = self._monotonic() + max(0.0, timeout)
        while self._monotonic() < deadline:
            status = self.status()
            if status.presence is not DaemonPresence.STOPPED:
                return status
            self._sleep(self.poll_interval)
        return self.status()

    def stop(self, *, timeout: float) -> bool:
        status = self.status()
        if status.presence is DaemonPresence.STOPPED:
            return True
        if not status.identity_verified:
            return False
        if not self._shutdown(self.port, min(2.0, max(0.25, timeout))):
            return False
        deadline = self._monotonic() + max(0.0, timeout)
        while self._monotonic() < deadline:
            status = self.status()
            if status.presence is DaemonPresence.STOPPED:
                return True
            if status.presence is not DaemonPresence.ARTEMIS:
                return False
            self._sleep(self.poll_interval)
        return self.status().presence is DaemonPresence.STOPPED


class TrayController:
    """Serialized synchronous controller intended to run outside the UI thread."""

    def __init__(
        self,
        *,
        port: int,
        lifecycle: LifecycleAdapter,
        drain: DrainAdapter,
        confirmation: DrainConfirmation,
        browser: BrowserAdapter,
        open_confirmation: OpenConfirmation,
        startup_timeout: float = 60.0,
        stop_timeout: float = 30.0,
        on_change: Callable[[TraySnapshot], None] | None = None,
    ) -> None:
        self.lifecycle, self.drain = lifecycle, drain
        self.confirmation, self.browser = confirmation, browser
        self.open_confirmation = open_confirmation
        self.startup_timeout, self.stop_timeout = startup_timeout, stop_timeout
        self._on_change = on_change
        self._operation_lock, self._snapshot_lock = threading.Lock(), threading.Lock()
        self._snapshot = TraySnapshot(TrayState.STOPPED, port)
        self._generation = 0

    @property
    def snapshot(self) -> TraySnapshot:
        with self._snapshot_lock:
            return self._snapshot

    def _publish(
        self, state: TrayState, detail: str = "", *, exit_requested: bool | None = None
    ) -> TraySnapshot:
        with self._snapshot_lock:
            self._snapshot = replace(
                self._snapshot,
                state=state,
                detail=detail,
                operation_id=self._generation,
                exit_requested=self._snapshot.exit_requested
                if exit_requested is None
                else exit_requested,
            )
            snapshot = self._snapshot
        if self._on_change:
            self._on_change(snapshot)
        return snapshot

    def _publish_status(self, status: LifecycleStatus) -> TraySnapshot:
        states = {
            DaemonPresence.ARTEMIS: TrayState.RUNNING,
            DaemonPresence.STOPPED: TrayState.STOPPED,
            DaemonPresence.PORT_CONFLICT: TrayState.PORT_CONFLICT,
            DaemonPresence.UNVERIFIED: TrayState.ERROR,
        }
        return self._publish(states[status.presence], status.detail)

    def _busy(self) -> OperationResult:
        return OperationResult(False, self.snapshot, "Another lifecycle operation is running.")

    def refresh(self) -> TraySnapshot:
        if not self._operation_lock.acquire(blocking=False):
            return self.snapshot
        try:
            return self._publish_status(self.lifecycle.status())
        finally:
            self._operation_lock.release()

    def start(self) -> OperationResult:
        if not self._operation_lock.acquire(blocking=False):
            return self._busy()
        try:
            self._generation += 1
            status = self.lifecycle.status()
            if status.presence is DaemonPresence.ARTEMIS:
                return OperationResult(
                    True, self._publish(TrayState.RUNNING), "Attached to daemon."
                )
            if status.presence is not DaemonPresence.STOPPED:
                return OperationResult(False, self._publish_status(status), status.detail)
            self._publish(TrayState.STARTING)
            if not self.lifecycle.start():
                status = self.lifecycle.status()
                return OperationResult(
                    False, self._publish_status(status), status.detail or "Start failed."
                )
            waiter = getattr(self.lifecycle, "wait_running", None)
            status = waiter(timeout=self.startup_timeout) if waiter else self.lifecycle.status()
            snapshot = self._publish_status(status)
            return OperationResult(
                status.identity_verified,
                snapshot,
                status.detail
                or ("Daemon is running." if status.identity_verified else "Startup failed."),
            )
        finally:
            self._operation_lock.release()

    def stop(self) -> OperationResult:
        return self._stop_or_exit(for_exit=False)

    def exit(self) -> OperationResult:
        return self._stop_or_exit(for_exit=True)

    def _stop_or_exit(self, *, for_exit: bool) -> OperationResult:
        if not self._operation_lock.acquire(blocking=False):
            return self._busy()
        try:
            self._generation += 1
            status = self.lifecycle.status()
            if status.presence is DaemonPresence.STOPPED:
                state = TrayState.EXITED if for_exit else TrayState.STOPPED
                return OperationResult(True, self._publish(state, exit_requested=for_exit))
            if status.presence is not DaemonPresence.ARTEMIS:
                return OperationResult(
                    False,
                    self._publish_status(status),
                    status.detail or "Refusing to stop an unverified process.",
                )
            workload = self.drain.workload()
            choice = (
                self.confirmation.choose(workload, for_exit=for_exit)
                if workload.busy
                else DrainChoice.WAIT
            )
            if choice is DrainChoice.CANCEL:
                return OperationResult(
                    False, self._publish(TrayState.RUNNING, "Stop cancelled."), "Stop cancelled."
                )
            if choice is DrainChoice.WAIT:
                self._publish(TrayState.DRAINING)
                if not self.drain.begin_drain():
                    snap = self._publish(TrayState.ERROR, "Could not begin drain.")
                    return OperationResult(False, snap, snap.detail)
                if not self.drain.wait_drained(timeout=self.stop_timeout):
                    choice = self.confirmation.choose_after_timeout(
                        self.drain.workload(), for_exit=for_exit
                    )
                    if choice is not DrainChoice.STOP_NOW:
                        snap = self._publish(
                            TrayState.RUNNING, "Drain timed out; server remains running."
                        )
                        return OperationResult(False, snap, snap.detail)
            if choice is DrainChoice.STOP_NOW and not self.drain.cancel_unfinished():
                snap = self._publish(TrayState.ERROR, "Could not cancel unfinished work.")
                return OperationResult(False, snap, snap.detail)
            self._publish(TrayState.STOPPING)
            if not self.lifecycle.stop(timeout=self.stop_timeout):
                status = self.lifecycle.status()
                snap = self._publish_status(status)
                if snap.state is TrayState.RUNNING:
                    snap = self._publish(TrayState.ERROR, "Daemon did not stop.")
                return OperationResult(False, snap, snap.detail)
            final = self.lifecycle.status()
            if final.presence is not DaemonPresence.STOPPED:
                return OperationResult(False, self._publish_status(final), "Stop was not verified.")
            state = TrayState.EXITED if for_exit else TrayState.STOPPED
            return OperationResult(True, self._publish(state, exit_requested=for_exit))
        finally:
            self._operation_lock.release()

    def open_homepage(self) -> OperationResult:
        if not self._operation_lock.acquire(blocking=False):
            return self._busy()
        try:
            self._generation += 1
            status = self.lifecycle.status()
            if status.presence is DaemonPresence.STOPPED:
                if not self.open_confirmation.confirm_start_and_open():
                    return OperationResult(
                        False,
                        self._publish(TrayState.STOPPED, "Open cancelled."),
                        "Open cancelled.",
                    )
                self._publish(TrayState.STARTING)
                if not self.lifecycle.start():
                    return OperationResult(
                        False, self._publish_status(self.lifecycle.status()), "Start failed."
                    )
                waiter = getattr(self.lifecycle, "wait_running", None)
                status = waiter(timeout=self.startup_timeout) if waiter else self.lifecycle.status()
            if status.presence is not DaemonPresence.ARTEMIS:
                return OperationResult(
                    False, self._publish_status(status), status.detail or "Daemon unavailable."
                )
            url = self.snapshot.homepage_url
            if not self.browser.open(url):
                snap = self._publish(TrayState.RUNNING, "Default browser could not be opened.")
                return OperationResult(False, snap, snap.detail)
            return OperationResult(True, self._publish(TrayState.RUNNING), opened_url=url)
        finally:
            self._operation_lock.release()
