"""Validated, serial-bound Android input commands for Remote Phone."""
from __future__ import annotations
import asyncio, base64, os, re, subprocess
from dataclasses import dataclass
from artemis.runtime import DeviceExecutionLock, device_pool
from artemis.toolchain import find_adb
from artemis.utils.subprocess_utils import hidden_process_kwargs
from artemis.drivers.android.input_ime import _escape_for_adb_text

REMOTE_KEYCODES = {"back":4,"home":3,"enter":66,"delete":67,"tab":61,"escape":111,
    "move_home":122,"move_end":123,"dpad_up":19,"dpad_down":20,"dpad_left":21,
    "dpad_right":22,"volume_up":24,"volume_down":25,"power":26,"app_switch":187,
    "copy":278,"cut":277,"paste":279}

class InputError(Exception):
    def __init__(self, status: int, code: str, detail: str): self.status, self.code, self.detail = status, code, detail

async def _devices():
    return await device_pool.try_list_devices_async()

async def require_device(serial: str):
    if not isinstance(serial, str) or not serial: raise InputError(404, "device_not_found", "Device serial is required")
    devices = await _devices()
    device = next((d for d in (devices or []) if d.serial == serial), None)
    if device is None: raise InputError(404, "device_not_found", "Device serial was not found")
    if device.state != "device": raise InputError(409, "device_unauthorized", f"Device is {device.state}")
    owners = DeviceExecutionLock.get_active_owners()
    if any(getattr(owner, "device_id", None) == serial or key == DeviceExecutionLock._normalize_device_id(serial) for key, owner in owners.items()):
        raise InputError(409, "device_busy", "Device is busy with an ARTEMIS task")
    return device

async def screen_size(serial: str) -> tuple[int, int]:
    proc = await asyncio.create_subprocess_exec(find_adb(), "-s", serial, "shell", "wm", "size", stdout=subprocess.PIPE, stderr=subprocess.PIPE, **hidden_process_kwargs())
    out, _ = await proc.communicate()
    match = re.search(rb"(\d+)x(\d+)", out)
    if not match: raise InputError(503, "capture_unavailable", "Unable to determine device screen size")
    return int(match.group(1)), int(match.group(2))

def _int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int): raise InputError(422, "invalid_coordinate", f"{name} must be an integer")
    return value

def _duration(value, default: int) -> int:
    if value is None: return default
    value = _int(value, "duration_ms")
    if not 0 <= value <= 5000: raise InputError(422, "invalid_coordinate", "duration_ms must be between 0 and 5000")
    return value

async def _run(serial: str, *args: str):
    proc = await asyncio.create_subprocess_exec(find_adb(), "-s", serial, "shell", "input", *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **hidden_process_kwargs())
    out, err = await proc.communicate()
    if proc.returncode: raise InputError(503, "capture_unavailable", err.decode(errors="replace")[-200:] or "ADB input failed")

async def tap(payload: dict) -> dict:
    serial = payload.get("device_serial"); await require_device(serial); width, height = await screen_size(serial)
    x, y = _int(payload.get("x"), "x"), _int(payload.get("y"), "y")
    if not 0 <= x < width or not 0 <= y < height: raise InputError(422, "invalid_coordinate", "Tap is outside the screen")
    duration = _duration(payload.get("duration_ms"), 100)
    await _run(serial, "tap", str(x), str(y)) if duration == 0 else await _run(serial, "swipe", str(x), str(y), str(x), str(y), str(duration))
    return {"ok": True, "sequence": 0}

async def swipe(payload: dict) -> dict:
    serial = payload.get("device_serial"); await require_device(serial); width, height = await screen_size(serial)
    vals = [_int(payload.get(k), k) for k in ("x1","y1","x2","y2")]
    if not (0 <= vals[0] < width and 0 <= vals[2] < width and 0 <= vals[1] < height and 0 <= vals[3] < height): raise InputError(422, "invalid_coordinate", "Swipe is outside the screen")
    await _run(serial, "swipe", *(str(v) for v in vals), str(_duration(payload.get("duration_ms"), 400)))
    return {"ok": True, "sequence": 0}

async def text(payload: dict) -> dict:
    serial = payload.get("device_serial"); await require_device(serial); value = payload.get("text")
    if not isinstance(value, str) or len(value) > 2000: raise InputError(422, "invalid_text", "text must be at most 2000 characters")
    if value.isascii():
        await _run(serial, "text", _escape_for_adb_text(value)); return {"ok": True, "mode": "ascii"}
    # ADB's text command cannot reliably carry Unicode; use ADBKeyboard's
    # documented base64 broadcast and fail clearly when that IME is absent.
    probe = await asyncio.create_subprocess_exec(find_adb(), "-s", serial, "shell", "settings", "get", "secure", "default_input_method", stdout=subprocess.PIPE, stderr=subprocess.PIPE, **hidden_process_kwargs())
    ime, _ = await probe.communicate()
    if b"adbkeyboard" not in ime.lower(): raise InputError(503, "capture_unavailable", "ADBKeyboard IME is not installed or enabled")
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    proc = await asyncio.create_subprocess_exec(find_adb(), "-s", serial, "shell", "am", "broadcast", "-a", "ADB_INPUT_B64", "--es", "msg", encoded, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **hidden_process_kwargs())
    _, err = await proc.communicate()
    if proc.returncode: raise InputError(503, "capture_unavailable", err.decode(errors="replace")[-200:] or "ADBKeyboard is unavailable")
    return {"ok": True, "mode": "ime"}

async def key(payload: dict) -> dict:
    serial = payload.get("device_serial"); await require_device(serial); name = payload.get("key")
    if name not in REMOTE_KEYCODES: raise InputError(422, "invalid_key", "Unsupported key")
    await _run(serial, "keyevent", str(REMOTE_KEYCODES[name])); return {"ok": True}

def control_allowed(client_host: str | None) -> bool:
    if os.getenv("ARTEMIS_REMOTE_CONTROL_ALLOW_LAN", "").lower() in {"1","true","yes","on"}: return True
    return client_host in {None, "127.0.0.1", "::1", "localhost"}
