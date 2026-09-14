"""Host subprocess launch tests; no device actions or real process mutations."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from artemis.utils import subprocess_utils
from artemis.core.diagnostics.probes.adb_probe import AdbDeviceProbe
from apps.admin_console.services.device_stream_service import DeviceStreamService


@pytest.mark.parametrize(
    "platform,expected", [("win32", {"creationflags": 0x08000000}), ("linux", {}), ("darwin", {})]
)
def test_hidden_process_kwargs(platform, expected):
    with patch.object(subprocess_utils.sys, "platform", platform):
        assert subprocess_utils.hidden_process_kwargs() == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["win32", "linux"])
async def test_readiness_shell_and_discovery_launch_hidden(platform):
    proc = Mock(returncode=0)
    proc.communicate = AsyncMock(
        return_value=(b"List of devices attached\nserial-1\tdevice\n", b"")
    )
    with (
        patch.object(subprocess_utils.sys, "platform", platform),
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as spawn,
    ):
        probe = AdbDeviceProbe()
        await probe._get_adb_version("adb")
        assert await probe._get_device_states("adb") == [("serial-1", "device")]
        await probe._run_adb_shell("adb", "serial-1", "dumpsys", "window", "policy")
    assert spawn.await_count == 3
    for call in spawn.await_args_list:
        assert call.kwargs.get("creationflags", 0) == (0x08000000 if platform == "win32" else 0)
        assert "stdout" in call.kwargs and "stderr" in call.kwargs


@pytest.mark.asyncio
async def test_stream_discovery_and_capture_are_hidden():
    service = DeviceStreamService()
    discovery = Mock(returncode=0)
    discovery.communicate = AsyncMock(
        return_value=(b"List of devices attached\nserial-1\tdevice\n", b"")
    )
    capture = Mock(returncode=0)

    async def communicate():
        service._active_listeners = 0
        return b"frame" * 300, b""

    capture.communicate = communicate
    with (
        patch.object(subprocess_utils.sys, "platform", "win32"),
        patch("apps.admin_console.services.device_stream_service.find_adb", return_value="adb"),
        patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            side_effect=[discovery, capture],
        ) as spawn,
    ):
        service._active_listeners = 1
        await service._capture_loop()
    assert spawn.await_count == 2
    assert spawn.await_args_list[1].args == ("adb", "-s", "serial-1", "exec-out", "screencap", "-p")
    assert all(call.kwargs["creationflags"] == 0x08000000 for call in spawn.await_args_list)
    assert service._latest_frame == b"frame" * 300


def test_adb_session_preserves_other_creation_flags():
    from artemis.runtime.adb_endpoint import AdbEndpoint, AdbSession

    session = AdbSession(AdbEndpoint(host="127.0.0.1", port=5037), adb_path="adb")
    with patch.object(subprocess_utils.sys, "platform", "win32"), patch("subprocess.run") as run:
        session.run(["devices"], creationflags=0x200)
    assert run.call_args.kwargs["creationflags"] == 0x08000200
