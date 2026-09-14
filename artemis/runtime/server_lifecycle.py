# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Artemis Server Lifecycle and Process Management.

Provides cross-platform facilities to discover, inspect, terminate,
and restart running Artemis UI / backend server instances regardless
of which terminal or process spawned them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.request

from artemis.config.paths import ROOT_DIR, get_server_info_file
from artemis.runtime.device_lock import DeviceExecutionLock
from artemis.runtime.process_probe import pid_is_alive
from artemis.runtime.supervisor import ProcessSupervisor
from artemis.utils.logger import get_logger

logger = get_logger(__name__)


def is_port_in_use(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Check whether a TCP port is currently listening / occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            return s.connect_ex((host, port)) == 0
        except Exception:
            return False


def _workspace_identity() -> str:
    """Return a stable identifier for this source/install workspace."""
    workspace = os.path.normcase(str(ROOT_DIR.resolve()))
    return hashlib.sha256(workspace.encode("utf-8")).hexdigest()[:16]


def _scoped_server_info_file(port: int) -> Path:
    """Return metadata path scoped to this workspace and TCP port."""
    legacy = get_server_info_file()
    return legacy.with_name(f"{legacy.stem}.{_workspace_identity()}.{port}{legacy.suffix}")


def _metadata_candidates(port: int | None = None) -> list[Path]:
    legacy = get_server_info_file()
    if port is not None:
        return [_scoped_server_info_file(port), legacy]
    pattern = f"{legacy.stem}.{_workspace_identity()}.*{legacy.suffix}"
    scoped = sorted(
        legacy.parent.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True
    )
    return [*scoped, legacy]


def _process_snapshot(pid: int) -> dict[str, Any] | None:
    """Read security-relevant process attributes, failing closed."""
    try:
        import psutil

        proc = psutil.Process(pid)
        return {
            "process_create_time": proc.create_time(),
            "sys_executable": proc.exe(),
            "cmdline": proc.cmdline(),
            "cwd": proc.cwd(),
        }
    except Exception as exc:
        logger.debug(f"Could not inspect process {pid}: {exc}")
        return None


def write_server_info(
    port: int,
    host: str = "127.0.0.1",
    pid: int | None = None,
    lifecycle_token: str | None = None,
) -> Path:
    """Persist current Artemis server runtime metadata to well-known path."""
    info_file = _scoped_server_info_file(port)
    try:
        info_file.parent.mkdir(parents=True, exist_ok=True)
        server_pid = pid or os.getpid()
        snapshot = _process_snapshot(server_pid) or {}
        data = {
            "pid": server_pid,
            "port": port,
            "host": host,
            "started_at": time.time(),
            "workspace": str(ROOT_DIR.resolve()),
            "workspace_id": _workspace_identity(),
            "cwd": snapshot.get("cwd"),
            "sys_executable": snapshot.get("sys_executable"),
            "cmdline": snapshot.get("cmdline"),
            "process_create_time": snapshot.get("process_create_time"),
        }
        if lifecycle_token:
            data["lifecycle_token"] = lifecycle_token
        info_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.debug(f"Saved Artemis server info (PID: {data['pid']}, port: {port}) to {info_file}")
    except Exception as e:
        logger.warning(f"Could not persist server metadata to {info_file}: {e}")
    return info_file


def read_server_info(port: int | None = None) -> dict[str, Any] | None:
    """Read scoped metadata, with a conservative legacy-file fallback."""
    workspace = os.path.normcase(str(ROOT_DIR.resolve()))
    for info_file in _metadata_candidates(port):
        if not info_file.exists():
            continue
        try:
            content = info_file.read_text(encoding="utf-8").strip()
            data = json.loads(content) if content else None
            if not isinstance(data, dict) or not isinstance(data.get("pid"), int):
                continue
            if port is not None and data.get("port") != port:
                continue
            recorded_workspace = data.get("workspace", data.get("cwd"))
            if not isinstance(recorded_workspace, str):
                continue
            if os.path.normcase(str(Path(recorded_workspace).resolve())) != workspace:
                continue
            return data
        except Exception as exc:
            logger.debug(f"Failed to read server info from {info_file}: {exc}")
    return None


def clear_server_info(
    *,
    port: int | None = None,
    lifecycle_token: str | None = None,
) -> None:
    """Remove only metadata belonging to this workspace and requested identity."""
    workspace = os.path.normcase(str(ROOT_DIR.resolve()))
    for info_file in _metadata_candidates(port):
        try:
            if not info_file.exists():
                continue
            data = json.loads(info_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            recorded_workspace = data.get("workspace", data.get("cwd"))
            if not isinstance(recorded_workspace, str) or (
                os.path.normcase(str(Path(recorded_workspace).resolve())) != workspace
            ):
                continue
            if port is not None and data.get("port") != port:
                continue
            if lifecycle_token is not None and not hmac.compare_digest(
                str(data.get("lifecycle_token", "")), lifecycle_token
            ):
                continue
            info_file.unlink()
            logger.debug(f"Cleared server info file at {info_file}")
        except Exception as exc:
            logger.debug(f"Error clearing server info file {info_file}: {exc}")


def _http_identity_matches(info: dict[str, Any], port: int, timeout: float) -> bool:
    """Require the HTTP endpoint to claim the verified metadata PID and port."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/system/lifecycle-identity",
        headers={
            "User-Agent": "Artemis-Lifecycle-Client/1.0",
            "X-Artemis-Lifecycle-Token": str(info.get("lifecycle_token", "")),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace") or "null")
        return (
            response.status == 200
            and isinstance(payload, dict)
            and payload.get("port") == port
            and payload.get("current_pid") == info.get("pid")
        )
    except Exception:
        return False


def request_graceful_shutdown(port: int, timeout: float = 1.5) -> bool:
    """Ask a locally managed Artemis server to run its shutdown lifecycle.

    The per-process token in the server metadata prevents this control request
    from being accepted remotely or accidentally sent to an unrelated service
    using the same port. A missing/stale token simply makes the caller fall back
    to process termination.
    """
    info = read_server_info(port)
    if not info or not _metadata_identity_is_valid(info, port):
        return False
    token = info.get("lifecycle_token")
    if not isinstance(token, str) or not token:
        return False
    if not _http_identity_matches(info, port, timeout=min(timeout, 0.75)):
        return False

    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/system/shutdown",
        method="POST",
        headers={
            "User-Agent": "Artemis-Lifecycle-Client/1.0",
            "X-Artemis-Lifecycle-Token": token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status in (200, 202)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False
    except Exception:
        return False


# Inverted dependency: the session database lives in the application layer
# (apps.admin_console), which this base runtime package must not import.
# The application layer registers its orphan-session reconciler here
# (apps/admin_console/database/repositories/session_repository.py does so on
# import); entry points that stop servers without loading the admin console
# perform that import as part of their assembly. Without a registration,
# reconciliation is skipped -- the admin console re-runs it on next startup.
_session_reconciler: Callable[[], int] | None = None


def register_session_reconciler(reconciler: Callable[[], int]) -> None:
    """Register the app-layer callback that marks orphaned sessions as failed."""
    global _session_reconciler
    _session_reconciler = reconciler


def _reconcile_orphaned_sessions() -> int:
    """Immediately mark sessions whose worker PIDs died during forced stop."""
    if _session_reconciler is None:
        return 0
    try:
        return _session_reconciler()
    except Exception as exc:
        logger.debug(f"Could not reconcile orphaned sessions after server stop: {exc}")
        return 0


def _any_pid_alive(pids: list[int]) -> bool:
    """Return whether any target process is still running (zombies excluded)."""
    return any(pid_is_alive(pid) for pid in pids)


def _listener_pids(port: int) -> set[int]:
    """Return kernel-reported listener PIDs; inability to inspect is unsafe."""
    try:
        import psutil

        return {
            conn.pid
            for conn in psutil.net_connections(kind="inet")
            if conn.pid
            and conn.laddr
            and conn.laddr.port == port
            and conn.status == psutil.CONN_LISTEN
        }
    except Exception as exc:
        logger.debug(f"Could not identify listener on port {port}: {exc}")
        return set()


def _same_path(left: Any, right: Any) -> bool:
    if not isinstance(left, str) or not isinstance(right, str) or not left or not right:
        return False
    try:
        return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(
            str(Path(right).resolve())
        )
    except (OSError, ValueError):
        return False


def _metadata_identity_is_valid(info: dict[str, Any], port: int) -> bool:
    """Verify metadata, process birth identity, listener ownership, and workspace."""
    pid = info.get("pid")
    token = info.get("lifecycle_token")
    if (
        not isinstance(pid, int)
        or pid <= 0
        or info.get("port") != port
        or not isinstance(token, str)
        or not token
        or info.get("workspace_id") != _workspace_identity()
        or not _same_path(info.get("workspace"), str(ROOT_DIR))
        or pid not in _listener_pids(port)
    ):
        return False
    snapshot = _process_snapshot(pid)
    if snapshot is None:
        return False
    recorded_birth = info.get("process_create_time")
    if (
        not isinstance(recorded_birth, (int, float))
        or abs(snapshot["process_create_time"] - recorded_birth) > 0.01
    ):
        return False
    return (
        _same_path(snapshot.get("sys_executable"), info.get("sys_executable"))
        and snapshot.get("cmdline") == info.get("cmdline")
        and _same_path(snapshot.get("cwd"), info.get("cwd"))
    )


def find_server_pids(port: int = 8000) -> list[int]:
    """Return only the PID whose complete Artemis identity is verified."""
    info = read_server_info(port)
    if not info or not _metadata_identity_is_valid(info, port):
        return []
    return [info["pid"]]


def get_server_status(port: int = 8000) -> dict[str, Any]:
    """Retrieve detailed status of the Artemis server on given port."""
    in_use = is_port_in_use(port)
    pids = find_server_pids(port)
    candidate_info = read_server_info(port)
    info = candidate_info if pids and candidate_info and candidate_info.get("pid") in pids else None

    uptime_seconds: float | None = None
    if info and "started_at" in info and isinstance(info["started_at"], (int, float)):
        uptime_seconds = max(0.0, time.time() - info["started_at"])

    # An occupied port or stale metadata is not proof that Artemis owns it.
    is_running = bool(pids)

    return {
        "running": is_running,
        "port": port,
        "pids": pids,
        "active_pid": pids[0] if pids else None,
        "uptime_seconds": uptime_seconds,
        "url": f"http://localhost:{port}" if is_running else None,
        "admin_url": f"http://localhost:{port}/admin" if is_running else None,
        "metadata": info,
        "port_in_use": in_use,
        "identity_verified": is_running,
        "identity_failure": "unverified_listener" if in_use and not is_running else None,
    }


def stop_server(
    port: int = 8000,
    timeout: float = 12.0,
    force: bool = False,
) -> tuple[bool, str, list[int]]:
    """Gracefully terminate any running Artemis server on `port`.

    Args:
        port: TCP port to inspect and terminate.
        timeout: Maximum seconds to wait for the server shutdown lifecycle.
        force: If True, skip the shutdown API and terminate the process tree.

    Returns:
        tuple (success, message, affected_pids)
    """
    pids = find_server_pids(port)

    if not pids and not is_port_in_use(port):
        clear_server_info(port=port)
        DeviceExecutionLock.cleanup_stale_locks()
        return True, f"No active server detected on port {port}.", []

    # Never signal, clean shared state, or erase metadata for an unverified listener.
    if not pids:
        return (
            False,
            f"Port {port} is occupied by a process that could not be verified as Artemis; "
            "refusing to stop it.",
            [],
        )

    stopped_pids: list[int] = []
    current_pid = os.getpid()

    # A normal stop is an application lifecycle request, not an OS signal.
    # This matters on Windows where taskkill /F and os.kill(..., SIGTERM) both
    # bypass FastAPI's shutdown hook. Give Uvicorn enough time to cancel task
    # workers, persist terminal session state, and release IPC/device resources.
    graceful_requested = False
    if not force:
        graceful_requested = request_graceful_shutdown(
            port,
            timeout=min(2.0, max(0.25, timeout)),
        )
        if graceful_requested:
            deadline = time.time() + max(0.25, timeout)
            while time.time() < deadline:
                if not is_port_in_use(port) and not _any_pid_alive(pids):
                    break
                time.sleep(0.1)

            if not is_port_in_use(port) and not _any_pid_alive(pids):
                cleaned_locks = DeviceExecutionLock.cleanup_stale_locks()
                clear_server_info(port=port)
                pid_str = f" (PID: {', '.join(map(str, pids))})" if pids else ""
                msg = f"Artemis server stopped gracefully{pid_str}. Port {port} is released."
                if cleaned_locks:
                    msg += f" Cleaned up {cleaned_locks} device lock(s)."
                return True, msg, pids

            logger.warning(
                f"Artemis server on port {port} did not exit within {timeout}s; "
                "falling back to process-tree termination."
            )

    for pid in pids:
        if pid == current_pid:
            # Don't terminate self during stop_server call
            continue
        try:
            ProcessSupervisor.terminate_tree(
                pid,
                timeout_seconds=0.5 if force or graceful_requested else timeout,
            )
            stopped_pids.append(pid)
        except Exception as e:
            logger.warning(f"Failed to terminate process {pid}: {e}")

    # Wait for the port to actually become free
    deadline = time.time() + max(1.5, timeout)
    while time.time() < deadline:
        if not is_port_in_use(port):
            break
        time.sleep(0.15)

    # Force kill if port is still occupied
    if is_port_in_use(port) and not force:
        remaining_pids = find_server_pids(port)
        for pid in remaining_pids:
            if pid != current_pid:
                try:
                    ProcessSupervisor.terminate_tree(pid, timeout_seconds=0.5)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    # Force-kill is best effort; the port check below reports the outcome.
                    logger.debug(f"Force kill of pid {pid} failed: {exc}", exc_info=True)
        time.sleep(0.3)

    # Cleanup stale device execution locks left by terminated server
    cleaned_locks = DeviceExecutionLock.cleanup_stale_locks()
    reconciled_sessions = _reconcile_orphaned_sessions()
    clear_server_info(port=port)

    port_free = not is_port_in_use(port)
    if port_free:
        pid_str = f" (PID: {', '.join(map(str, stopped_pids))})" if stopped_pids else ""
        msg = f"Artemis server stopped{pid_str}. Port {port} is released."
        if cleaned_locks:
            msg += f" Cleaned up {cleaned_locks} device lock(s)."
        if reconciled_sessions:
            msg += f" Reconciled {reconciled_sessions} interrupted session(s)."
        return True, msg, stopped_pids
    else:
        return (
            False,
            f"Port {port} remains occupied after stop attempt. Some background process may require manual termination.",
            stopped_pids,
        )
