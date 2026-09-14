from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from apps.admin_console.server import app
from apps.admin_console.core.state import state


@pytest.mark.asyncio
async def test_startup_mutation_uses_server_port(monkeypatch):
    monkeypatch.setattr(state, "port", 8009)
    with patch(
        "artemis.runtime.windows_startup.set_startup_enabled",
        return_value={"supported": True, "enabled": True, "port": 8009},
    ) as update:
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("127.0.0.1", 1234)),
            base_url="http://localhost",
        ) as client:
            result = await client.put(
                "/api/system/windows-startup",
                json={"enabled": True},
                headers={"Origin": "http://localhost"},
            )
    assert result.status_code == 200
    update.assert_called_once_with(True, 8009)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "peer,origin", [("192.168.1.2", "http://localhost"), ("127.0.0.1", "http://localhost:1234")]
)
async def test_startup_rejects_remote_and_cross_origin(peer, origin):
    with patch("artemis.runtime.windows_startup.set_startup_enabled") as update:
        async with AsyncClient(
            transport=ASGITransport(app=app, client=(peer, 1234)), base_url="http://localhost"
        ) as client:
            result = await client.put(
                "/api/system/windows-startup", json={"enabled": True}, headers={"Origin": origin}
            )
    assert result.status_code == 403
    update.assert_not_called()


@pytest.mark.asyncio
async def test_permission_failure_is_an_actionable_error():
    with patch("artemis.runtime.windows_startup.set_startup_enabled", side_effect=PermissionError):
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("127.0.0.1", 1234)),
            base_url="http://localhost",
        ) as client:
            result = await client.put("/api/system/windows-startup", json={"enabled": False})
    assert result.status_code == 500
    assert "permissions" in result.json()["detail"]
