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

"""Unit tests for Artemis Server Lifecycle Management and API Endpoints."""

import asyncio
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from apps.admin_console import server as server_module
from apps.admin_console.server import LIFECYCLE_TOKEN, app
from artemis.runtime.server_lifecycle import (
    clear_server_info,
    find_server_pids,
    get_server_status,
    is_port_in_use,
    read_server_info,
    request_graceful_shutdown,
    stop_server,
    write_server_info,
)


def test_write_read_clear_server_info(tmp_path, monkeypatch):
    """Verify write, read, and clear round-trip for server metadata file."""
    fake_info_file = tmp_path / "test_server.json"
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.get_server_info_file", lambda: fake_info_file
    )

    # Initial read should be None
    assert read_server_info() is None

    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle._process_snapshot",
        lambda pid: {
            "process_create_time": 123.0,
            "sys_executable": "python",
            "cmdline": ["python", "-m", "apps.admin_console.server"],
            "cwd": str(tmp_path),
        },
    )
    monkeypatch.setattr("artemis.runtime.server_lifecycle.ROOT_DIR", tmp_path)

    # Write info to the workspace+port scoped path.
    written = write_server_info(port=8888, host="127.0.0.1", pid=99999)
    assert written != fake_info_file
    assert written.exists()

    # Read back
    info = read_server_info()
    assert info is not None
    assert info["pid"] == 99999
    assert info["port"] == 8888
    assert info["host"] == "127.0.0.1"
    assert "started_at" in info

    # A stop targeting another port must not erase this server's metadata.
    clear_server_info(port=9999)
    assert written.exists()

    # Clear matching info
    clear_server_info(port=8888)
    assert not written.exists()
    assert read_server_info() is None


def test_find_server_pids_from_verified_metadata(tmp_path, monkeypatch):
    """PID discovery requires every persisted and live identity attribute."""
    monkeypatch.setattr("artemis.runtime.server_lifecycle.ROOT_DIR", tmp_path)
    snapshot = {
        "process_create_time": 100.0,
        "sys_executable": str(tmp_path / "python.exe"),
        "cmdline": ["python", "-m", "apps.admin_console.server"],
        "cwd": str(tmp_path),
    }
    monkeypatch.setattr("artemis.runtime.server_lifecycle._process_snapshot", lambda pid: snapshot)
    monkeypatch.setattr("artemis.runtime.server_lifecycle._listener_pids", lambda port: {4321})
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.get_server_info_file", lambda: tmp_path / "server.json"
    )
    write_server_info(port=8000, pid=4321, lifecycle_token="secret")

    assert find_server_pids(8000) == [4321]

    monkeypatch.setattr("artemis.runtime.server_lifecycle._listener_pids", lambda port: {9999})
    assert find_server_pids(8000) == []


def _valid_identity(tmp_path):
    snapshot = {
        "process_create_time": 100.0,
        "sys_executable": str(tmp_path / "python.exe"),
        "cmdline": ["python", "-m", "apps.admin_console.server"],
        "cwd": str(tmp_path),
    }
    info = {
        "pid": 4321,
        "port": 8000,
        "lifecycle_token": "secret",
        "workspace": str(tmp_path),
        "workspace_id": "workspace-id",
        **snapshot,
    }
    return info, snapshot


@pytest.mark.parametrize(
    ("mutation", "listener_pids"),
    [
        ({"lifecycle_token": ""}, {4321}),
        ({"port": 8001}, {4321}),
        ({"pid": 4322}, {4321}),
        ({"workspace_id": "other"}, {4321}),
        ({"workspace": "other"}, {4321}),
        ({"process_create_time": 101.0}, {4321}),
        ({"sys_executable": "other-python"}, {4321}),
        ({"cmdline": ["python", "foreign.py"]}, {4321}),
        ({"cwd": "other"}, {4321}),
        ({}, {9999}),
    ],
)
def test_identity_validation_fails_closed(tmp_path, monkeypatch, mutation, listener_pids):
    from artemis.runtime import server_lifecycle

    info, snapshot = _valid_identity(tmp_path)
    info.update(mutation)
    monkeypatch.setattr(server_lifecycle, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(server_lifecycle, "_workspace_identity", lambda: "workspace-id")
    monkeypatch.setattr(server_lifecycle, "_listener_pids", lambda port: listener_pids)
    monkeypatch.setattr(server_lifecycle, "_process_snapshot", lambda pid: snapshot)

    assert server_lifecycle._metadata_identity_is_valid(info, 8000) is False


def test_read_server_info_accepts_safe_legacy_file(tmp_path, monkeypatch):
    legacy = tmp_path / "server.json"
    legacy.write_text(
        json.dumps({"pid": 7, "port": 8000, "cwd": str(tmp_path)}), encoding="utf-8"
    )
    monkeypatch.setattr("artemis.runtime.server_lifecycle.ROOT_DIR", tmp_path)
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.get_server_info_file", lambda: legacy
    )

    assert read_server_info(8000)["pid"] == 7
    assert read_server_info(8001) is None


def test_stop_server_refuses_unverified_listener(monkeypatch):
    terminate = MagicMock()
    cleanup = MagicMock()
    clear = MagicMock()
    monkeypatch.setattr("artemis.runtime.server_lifecycle.find_server_pids", lambda port: [])
    monkeypatch.setattr("artemis.runtime.server_lifecycle.is_port_in_use", lambda port: True)
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.ProcessSupervisor.terminate_tree", terminate
    )
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.DeviceExecutionLock.cleanup_stale_locks", cleanup
    )
    monkeypatch.setattr("artemis.runtime.server_lifecycle.clear_server_info", clear)

    success, message, stopped = stop_server(8000, timeout=0)

    assert success is False
    assert stopped == []
    assert "refusing" in message
    terminate.assert_not_called()
    cleanup.assert_not_called()
    clear.assert_not_called()


def test_get_server_status_offline(monkeypatch):
    """Verify get_server_status returns correct structure when server is offline."""
    monkeypatch.setattr("artemis.runtime.server_lifecycle.is_port_in_use", lambda port, **k: False)
    monkeypatch.setattr("artemis.runtime.server_lifecycle.find_server_pids", lambda port: [])
    monkeypatch.setattr("artemis.runtime.server_lifecycle.read_server_info", lambda port=None: None)

    status = get_server_status(8000)
    assert status["running"] is False
    assert status["port"] == 8000
    assert status["pids"] == []
    assert status["url"] is None


def test_get_server_status_online(monkeypatch):
    """Verify get_server_status returns correct structure when server is online."""
    monkeypatch.setattr("artemis.runtime.server_lifecycle.is_port_in_use", lambda port, **k: True)
    monkeypatch.setattr("artemis.runtime.server_lifecycle.find_server_pids", lambda port: [12345])
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.read_server_info",
        lambda port=None: {"pid": 12345, "port": 8000, "started_at": 1000.0},
    )

    status = get_server_status(8000)
    assert status["running"] is True
    assert status["port"] == 8000
    assert status["pids"] == [12345]
    assert status["active_pid"] == 12345
    assert status["url"] == "http://localhost:8000"
    assert status["admin_url"] == "http://localhost:8000/admin"
    assert status["uptime_seconds"] is not None


def test_stop_server_when_not_running(monkeypatch):
    """Verify stop_server returns early when no server is running."""
    monkeypatch.setattr("artemis.runtime.server_lifecycle.is_port_in_use", lambda port, **k: False)
    monkeypatch.setattr("artemis.runtime.server_lifecycle.find_server_pids", lambda port: [])

    success, msg, stopped = stop_server(8000)
    assert success is True
    assert stopped == []
    assert "No active server" in msg


def test_server_main_parses_non_default_bind_address(monkeypatch):
    run_server = MagicMock()
    monkeypatch.setattr(server_module, "run_ui_server", run_server)

    server_module.main(["--host", "127.0.0.1", "--port", "9123"])

    run_server.assert_called_once_with(host="127.0.0.1", port=9123)


def test_request_graceful_shutdown_uses_metadata_token(monkeypatch):
    response = MagicMock(status=202)
    response.__enter__.return_value = response
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.read_server_info",
        lambda port=None: {"pid": 123, "port": 9123, "lifecycle_token": "local-secret"},
    )
    monkeypatch.setattr("artemis.runtime.server_lifecycle._metadata_identity_is_valid", lambda info, port: True)
    status_response = MagicMock(status=200)
    status_response.read.return_value = b'{"port": 9123, "current_pid": 123}'
    status_response.__enter__.return_value = status_response
    urlopen = MagicMock(side_effect=[status_response, response])
    monkeypatch.setattr("artemis.runtime.server_lifecycle.urllib.request.urlopen", urlopen)

    assert request_graceful_shutdown(9123) is True
    request = urlopen.call_args_list[-1].args[0]
    assert request.full_url == "http://127.0.0.1:9123/api/system/shutdown"
    assert request.get_header("X-artemis-lifecycle-token") == "local-secret"


def test_stop_server_prefers_graceful_shutdown(monkeypatch):
    monkeypatch.setattr("artemis.runtime.server_lifecycle.find_server_pids", lambda port: [12345])
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.request_graceful_shutdown", lambda port, timeout: True
    )
    monkeypatch.setattr("artemis.runtime.server_lifecycle.is_port_in_use", lambda port: False)
    monkeypatch.setattr("artemis.runtime.server_lifecycle._any_pid_alive", lambda pids: False)
    terminate = MagicMock()
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.ProcessSupervisor.terminate_tree", terminate
    )
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.DeviceExecutionLock.cleanup_stale_locks", lambda: 0
    )
    monkeypatch.setattr("artemis.runtime.server_lifecycle.clear_server_info", lambda **kwargs: None)

    success, msg, stopped = stop_server(9123)

    assert success is True
    assert stopped == [12345]
    assert "gracefully" in msg
    terminate.assert_not_called()


def test_stop_server_terminates_tree(monkeypatch):
    """Verify stop_server calls ProcessSupervisor.terminate_tree and returns stopped pids."""
    terminated_pids = []

    monkeypatch.setattr("artemis.runtime.server_lifecycle.find_server_pids", lambda port: [12345])
    port_in_use = [True, False]

    def mock_in_use(port, **kwargs):
        if port_in_use:
            return port_in_use.pop(0)
        return False

    monkeypatch.setattr("artemis.runtime.server_lifecycle.is_port_in_use", mock_in_use)
    monkeypatch.setattr(
        "artemis.runtime.server_lifecycle.request_graceful_shutdown", lambda port, timeout: False
    )
    monkeypatch.setattr(
        "artemis.runtime.supervisor.ProcessSupervisor.terminate_tree",
        lambda pid, timeout_seconds=4.0: terminated_pids.append(pid),
    )
    monkeypatch.setattr(
        "artemis.runtime.device_lock.DeviceExecutionLock.cleanup_stale_locks",
        lambda: 1,
    )
    reconcile = MagicMock(return_value=1)
    monkeypatch.setattr("artemis.runtime.server_lifecycle._reconcile_orphaned_sessions", reconcile)

    success, msg, stopped = stop_server(8000)
    assert success is True
    assert stopped == [12345]
    assert 12345 in terminated_pids
    assert "stopped" in msg.lower()
    assert "Reconciled 1 interrupted session" in msg
    reconcile.assert_called_once_with()


@pytest.mark.asyncio
async def test_api_server_status():
    """Verify GET /api/system/server-status returns server runtime metadata."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/system/server-status")
        assert response.status_code == 200
        data = response.json()
        assert "port" in data
        assert "running" in data
        assert "current_pid" in data


@pytest.mark.asyncio
async def test_api_lifecycle_identity_requires_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        denied = await client.get("/api/system/lifecycle-identity")
        assert denied.status_code == 403
        response = await client.get(
            "/api/system/lifecycle-identity",
            headers={"X-Artemis-Lifecycle-Token": LIFECYCLE_TOKEN},
        )
    assert response.status_code == 200
    assert response.json()["current_pid"] == os.getpid()


@pytest.mark.asyncio
async def test_api_restart_endpoint():
    """Verify POST /api/system/restart accepts request and schedules restart."""
    with patch("threading.Thread") as mock_thread:
        mock_instance = MagicMock()
        mock_thread.return_value = mock_instance

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            response = await client.post("/api/system/restart")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "restarting"
            assert (
                "reconnection" in data["message"].lower() or "restarting" in data["message"].lower()
            )
            mock_thread.assert_called_once()
            mock_instance.start.assert_called_once()


@pytest.mark.asyncio
async def test_api_shutdown_endpoint():
    """Verify shutdown is authenticated and drives Uvicorn's graceful exit flag."""
    fake_server = MagicMock(should_exit=False)
    app.state.uvicorn_server = fake_server

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        denied = await client.post("/api/system/shutdown")
        assert denied.status_code == 403

        response = await client.post(
            "/api/system/shutdown",
            headers={"X-Artemis-Lifecycle-Token": LIFECYCLE_TOKEN},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "shutting_down"
        await asyncio.sleep(0.1)

    assert fake_server.should_exit is True
    app.state.uvicorn_server = None
