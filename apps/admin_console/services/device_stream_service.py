"""Per-device screen capture registry used by the Remote Phone UI."""
from __future__ import annotations
import asyncio, io, logging, subprocess, time
from dataclasses import dataclass, field
from collections.abc import AsyncGenerator
from artemis.toolchain import find_adb
from artemis.utils.subprocess_utils import hidden_process_kwargs

logger = logging.getLogger("artemis.stream_service")

@dataclass
class DeviceProducer:
    serial: str
    subscriber_count: int = 0
    latest_frame: bytes | None = None
    frame_sequence: int = 0
    captured_at: float = 0.0
    last_error: str | None = None
    screen_width: int | None = None
    screen_height: int | None = None
    rotation: int = 0
    task: asyncio.Task | None = field(default=None, repr=False)

class DeviceStreamService:
    """One capture task and latest-frame buffer per ADB serial."""
    def __init__(self) -> None:
        self._producers: dict[str, DeviceProducer] = {}
        self._lock = asyncio.Lock()
        self._active_listeners = 0  # legacy compatibility
        self._latest_frame: bytes | None = None
        self._last_frame_time = 0.0
        self._capture_task: asyncio.Task | None = None

    async def get_device_serial(self) -> str | None:
        try:
            proc = await asyncio.create_subprocess_exec(find_adb(), "devices", stdout=subprocess.PIPE, stderr=subprocess.PIPE, **hidden_process_kwargs())
            stdout, _ = await proc.communicate()
            for line in stdout.decode(errors="replace").splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device": return parts[0]
        except Exception as exc: logger.warning("ADB discovery failed: %s", exc)
        return None

    @staticmethod
    def _jpeg(raw: bytes) -> tuple[bytes, int | None, int | None]:
        try:
            from PIL import Image
            image = Image.open(io.BytesIO(raw)).convert("RGB")
            width, height = image.size
            scale = min(1.0, 960 / max(width, height))
            if scale < 1: image = image.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
            out = io.BytesIO(); image.save(out, format="JPEG", quality=70, optimize=True)
            return out.getvalue(), width, height
        except Exception: return raw, None, None

    async def _capture_loop(self, producer: DeviceProducer | None = None) -> None:
        # The optional form preserves the legacy workspace test/helper contract.
        legacy = producer is None
        if producer is None:
            serial = await self.get_device_serial()
            if not serial: return
            producer = DeviceProducer(serial, subscriber_count=self._active_listeners)
            self._producers[serial] = producer
        try:
            while (self._active_listeners > 0 if legacy else producer.subscriber_count > 0):
                started = time.monotonic()
                proc = await asyncio.create_subprocess_exec(find_adb(), "-s", producer.serial, "exec-out", "screencap", "-p", stdout=subprocess.PIPE, stderr=subprocess.PIPE, **hidden_process_kwargs())
                raw, stderr = await proc.communicate()
                if proc.returncode == 0 and len(raw) > 100:
                    frame, width, height = await asyncio.to_thread(self._jpeg, raw)
                    producer.latest_frame, producer.frame_sequence = frame, producer.frame_sequence + 1
                    producer.captured_at, producer.last_error = time.monotonic(), None
                    producer.screen_width, producer.screen_height = width, height
                    self._latest_frame, self._last_frame_time = frame, time.time()
                else: producer.last_error = stderr.decode(errors="replace")[-300:] or "screencap failed"
                await asyncio.sleep(max(0.03, 0.2 - (time.monotonic() - started)))
        except asyncio.CancelledError: raise
        except Exception as exc: producer.last_error = str(exc)

    async def _acquire(self, serial: str) -> DeviceProducer:
        async with self._lock:
            producer = self._producers.get(serial) or DeviceProducer(serial)
            self._producers[serial] = producer; producer.subscriber_count += 1
            if producer.task is None or producer.task.done(): producer.task = asyncio.create_task(self._capture_loop(producer))
            return producer

    async def _release(self, producer: DeviceProducer) -> None:
        async with self._lock:
            producer.subscriber_count = max(0, producer.subscriber_count - 1)
            if producer.subscriber_count: return
            task, producer.task = producer.task, None; producer.latest_frame = None
            if task and not task.done():
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
            self._producers.pop(producer.serial, None)

    async def mjpeg_frame_generator(self, serial: str | None = None) -> AsyncGenerator[bytes, None]:
        serial = serial or await self.get_device_serial()
        if not serial: return
        producer = await self._acquire(serial); last_sequence = 0
        try:
            while True:
                if producer.latest_frame is not None and producer.frame_sequence > last_sequence:
                    last_sequence = producer.frame_sequence; frame = producer.latest_frame
                    yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
                await asyncio.sleep(0.04)
        finally: await self._release(producer)

    async def get_state(self, serial: str) -> dict:
        p = self._producers.get(serial)
        age = None if not p or not p.captured_at else max(0, round((time.monotonic() - p.captured_at) * 1000))
        return {"serial": serial, "state": "device" if p else "unknown", "frame_sequence": p.frame_sequence if p else 0, "frame_age_ms": age, "screen_width": p.screen_width if p else None, "screen_height": p.screen_height if p else None, "rotation": p.rotation if p else 0, "stream_url": f"/api/remote/stream?device_serial={serial}", "last_error": p.last_error if p else None}

device_stream_service = DeviceStreamService()
