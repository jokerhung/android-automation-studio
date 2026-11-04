import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from admin_console.core.security import SameOriginBoundaryMiddleware, server_access_allowed
from admin_console.routers import remote, system
from artemis.core.diagnostics.schema import SystemReadinessReport


@pytest.mark.parametrize("bound", ["0.0.0.0", "10.201.21.211", "::"])
@pytest.mark.parametrize("peer", ["127.0.0.1", "192.168.1.20", "::1"])
def test_network_bind_accepts_local_and_lan_clients(bound, peer):
    assert server_access_allowed(peer, bound)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "peer,base",
    [
        ("127.0.0.1", "http://localhost:8009"),
        ("192.168.1.20", "http://10.201.21.211:8009"),
    ],
)
async def test_adb_remote_and_lifecycle_apis_accept_localhost_and_lan(monkeypatch, peer, base):
    monkeypatch.setattr(system.state, "host", "0.0.0.0")
    monkeypatch.setattr(system.state, "is_draining", False)
    monkeypatch.setattr(system.state, "is_shutting_down", False)
    monkeypatch.setattr(system.state, "_shutdown_event", asyncio.Event())
    app = FastAPI()
    app.add_middleware(SameOriginBoundaryMiddleware)
    app.include_router(system.router)
    app.include_router(remote.router)
    app.state.lifecycle_token = "test-lifecycle-token"
    app.state.uvicorn_server = Mock(should_exit=False)
    report = SystemReadinessReport(
        overall_ready=True,
        blocker_count=0,
        passed_blocker_count=0,
        probes=[],
        timestamp=1,
    )
    monkeypatch.setattr(system.readiness_engine, "run_all", AsyncMock(return_value=report))
    for method in ("probe", "connect", "use_local_server"):
        monkeypatch.setattr(
            system.adb_server_connection, method, AsyncMock(return_value={"success": True})
        )
    operations = {}
    for method in ("tap", "swipe", "text", "key"):
        operations[method] = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(remote.inputs, method, operations[method])
    async with AsyncClient(
        transport=ASGITransport(app=app, client=(peer, 5000)),
        base_url=base,
        headers={"Origin": base},
    ) as client:
        for path in ("probe", "connect"):
            result = await client.post(
                "/api/system/adb/server/" + path,
                json={"host": "127.0.0.1", "port": 5037, "persist": False},
            )
            assert result.status_code == 200
        assert (await client.post("/api/system/adb/server/local?persist=false")).status_code == 200
        for method in operations:
            result = await client.post(
                "/api/remote/input/" + method, json={"device_serial": "test-device"}
            )
            assert result.status_code == 200
            operations[method].assert_awaited_once()
        with patch("threading.Thread") as thread:
            assert (await client.post("/api/system/restart")).status_code == 200
            thread.return_value.start.assert_called_once()
        for path, method in [("lifecycle-identity", "GET"), ("shutdown", "POST")]:
            assert (await client.request(method, "/api/system/" + path)).status_code == 403
            result = await client.request(
                method,
                "/api/system/" + path,
                headers={"X-Artemis-Lifecycle-Token": "test-lifecycle-token"},
            )
            assert result.status_code == (202 if method == "POST" else 200)
        await asyncio.sleep(0.1)
        assert app.state.uvicorn_server.should_exit is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/system/adb/server/probe", {"host": "127.0.0.1", "port": 5037}),
        ("/api/remote/input/tap", {"device_serial": "test-device"}),
        ("/api/system/restart", {}),
        ("/api/system/shutdown", {}),
    ],
)
async def test_cross_origin_lan_requests_do_not_execute_operations(monkeypatch, path, payload):
    monkeypatch.setattr(system.state, "host", "0.0.0.0")
    app = FastAPI()
    app.add_middleware(SameOriginBoundaryMiddleware)
    app.include_router(system.router)
    app.include_router(remote.router)
    probe, tap = AsyncMock(), AsyncMock()
    monkeypatch.setattr(system.adb_server_connection, "probe", probe)
    monkeypatch.setattr(remote.inputs, "tap", tap)
    with patch("threading.Thread") as thread:
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("192.168.1.20", 5000)),
            base_url="http://10.201.21.211:8009",
        ) as client:
            result = await client.post(
                path, json=payload, headers={"Origin": "https://other.example"}
            )
        assert result.status_code == 403
        thread.assert_not_called()
    probe.assert_not_awaited()
    tap.assert_not_awaited()
