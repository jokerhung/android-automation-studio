# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0
"""UI-free orchestration for tray and daemon background runtime."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Protocol, TypeVar

from artemis.runtime.tray_controller import DaemonPresence, LifecycleAdapter, LifecycleStatus

T = TypeVar("T")


class TrayRuntimeAdapter(Protocol):
    def available(self) -> bool: ...
    def ensure_running(self, *, host: str, port: int) -> bool: ...


class WindowsTrayRuntimeAdapter:
    """Launch or attach to the tray for one user/workspace/port target."""

    def __init__(
        self,
        *,
        workspace: str | Path,
        popen: Callable[..., object] = subprocess.Popen,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self._popen = popen

    def available(self) -> bool:
        if sys.platform != "win32":
            return False
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        return pythonw.is_file() and bool(os.environ.get("USERPROFILE"))

    def ensure_running(self, *, host: str, port: int) -> bool:
        from artemis.runtime.tray_instance import (
            TrayInstanceUnavailable,
            TrayTarget,
            attach_existing,
        )

        target = TrayTarget.create(self.workspace, port)
        try:
            if attach_existing(target, "show"):
                return True
        except TrayInstanceUnavailable:
            return False

        pythonw = Path(sys.executable).with_name("pythonw.exe")
        command = [
            str(pythonw),
            "-m",
            "artemis.runtime.tray_launcher",
            "--host",
            host,
            "--port",
            str(port),
            "--workspace",
            str(self.workspace),
        ]
        kwargs = {
            "cwd": str(self.workspace),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        }
        try:
            self._popen(command, **kwargs)
        except OSError:
            return False
        return True


@dataclass(frozen=True)
class BackgroundRuntimeResult:
    tray_available: bool
    tray_running: bool
    daemon_status: LifecycleStatus
    daemon_started: bool = False
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.daemon_status.presence is DaemonPresence.ARTEMIS


def ensure_background_runtime(
    *,
    host: str,
    port: int,
    lifecycle: LifecycleAdapter,
    tray: TrayRuntimeAdapter | None = None,
    wait_timeout: float = 60.0,
) -> BackgroundRuntimeResult:
    """Ensure tray when available, then attach to or start one verified daemon.

    Port conflicts are returned without spawning or terminating anything.  Tray
    failure is non-fatal so non-interactive sessions can still run the daemon.
    """
    tray_available = bool(tray and tray.available())
    tray_running = False
    detail_parts: list[str] = []
    if tray_available and tray:
        tray_running = tray.ensure_running(host=host, port=port)
        if not tray_running:
            detail_parts.append("Tray could not be started.")
    elif tray is not None:
        detail_parts.append("Tray is unavailable in this session.")

    status = lifecycle.status()
    if status.presence is DaemonPresence.ARTEMIS:
        return BackgroundRuntimeResult(
            tray_available, tray_running, status, detail=" ".join(detail_parts)
        )
    if status.presence is not DaemonPresence.STOPPED:
        return BackgroundRuntimeResult(
            tray_available,
            tray_running,
            status,
            detail=status.detail or "Target port is unavailable.",
        )
    if not lifecycle.start():
        final = lifecycle.status()
        return BackgroundRuntimeResult(
            tray_available,
            tray_running,
            final,
            detail=final.detail or "Daemon could not be started.",
        )
    waiter = getattr(lifecycle, "wait_running", None)
    final = waiter(timeout=wait_timeout) if waiter else lifecycle.status()
    return BackgroundRuntimeResult(
        tray_available,
        tray_running,
        final,
        daemon_started=final.presence is DaemonPresence.ARTEMIS,
        detail=final.detail or " ".join(detail_parts),
    )


class BackgroundOperationRunner:
    """Single-worker dispatcher keeping blocking controller work off a UI loop."""

    def __init__(self, *, thread_name_prefix: str = "artemis-tray") -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=thread_name_prefix)
        self._closed = False

    def submit(self, operation: Callable[[], T]) -> Future[T]:
        if self._closed:
            raise RuntimeError("Background operation runner is closed.")
        return self._executor.submit(operation)

    def close(self, *, wait: bool = True, cancel_pending: bool = False) -> None:
        self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=cancel_pending)

    def __enter__(self) -> BackgroundOperationRunner:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
