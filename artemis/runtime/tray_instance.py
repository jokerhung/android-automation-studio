"""Windows current-user tray single-instance and attach channel.

The target identity is bound to the canonical workspace and port. The attach
protocol accepts only a small action whitelist and uses byte messages rather
than multiprocessing's pickle helpers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
from typing import Any, Protocol

ATTACH_ACTIONS = frozenset({"show", "open_homepage", "start"})
_MAX_MESSAGE_BYTES = 1024
_ERROR_ALREADY_EXISTS = 183


class TrayInstanceError(RuntimeError):
    """Base error for tray instance coordination."""


class TrayInstanceUnavailable(TrayInstanceError):
    """Raised when Windows native instance APIs are unavailable."""


class InvalidAttachRequest(TrayInstanceError):
    """Raised when an attach request violates the fixed protocol."""


@dataclass(frozen=True, slots=True)
class TrayTarget:
    workspace: Path
    port: int
    user: str

    @classmethod
    def create(
        cls,
        workspace: str | os.PathLike[str],
        port: int,
        *,
        user: str | None = None,
    ) -> TrayTarget:
        if not 1 <= port <= 65535:
            raise ValueError("Invalid server port")
        canonical = Path(workspace).expanduser().resolve(strict=False)
        identity = user or _current_user_identity()
        if not identity:
            raise TrayInstanceError("Cannot determine the current Windows user")
        return cls(canonical, port, identity)

    @property
    def key(self) -> str:
        material = f"{self.user.casefold()}\0{os.path.normcase(str(self.workspace))}\0{self.port}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]

    @property
    def mutex_name(self) -> str:
        return rf"Local\ARTEMIS.Tray.{self.key}"

    @property
    def pipe_address(self) -> str:
        return rf"\\.\pipe\artemis-tray-{self.key}"

    @property
    def authkey(self) -> bytes:
        return hashlib.sha256(f"artemis-tray-attach\0{self.key}".encode()).digest()


def _current_user_identity() -> str:
    domain = os.environ.get("USERDOMAIN", "").strip()
    username = getpass.getuser().strip()
    return f"{domain}\\{username}" if domain else username


def encode_attach_request(action: str) -> bytes:
    if action not in ATTACH_ACTIONS:
        raise InvalidAttachRequest(f"Attach action is not allowed: {action!r}")
    return json.dumps({"action": action}, separators=(",", ":")).encode("utf-8")


def decode_attach_request(payload: bytes) -> str:
    if len(payload) > _MAX_MESSAGE_BYTES:
        raise InvalidAttachRequest("Attach request is too large")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidAttachRequest("Attach request is not valid JSON") from exc
    if not isinstance(value, dict) or set(value) != {"action"}:
        raise InvalidAttachRequest("Attach request must contain only an action")
    action = value["action"]
    if not isinstance(action, str) or action not in ATTACH_ACTIONS:
        raise InvalidAttachRequest("Attach action is not allowed")
    return action


class MutexApi(Protocol):
    def create(self, name: str) -> tuple[Any, bool]: ...
    def close(self, handle: Any) -> None: ...


class Win32MutexApi:
    """Small ctypes adapter kept replaceable for hermetic tests."""

    def create(self, name: str) -> tuple[Any, bool]:
        if sys.platform != "win32":
            raise TrayInstanceUnavailable("The tray mutex is available only on Windows")
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            raise ctypes.WinError()
        return handle, kernel32.GetLastError() == _ERROR_ALREADY_EXISTS

    def close(self, handle: Any) -> None:
        if handle:
            import ctypes

            ctypes.windll.kernel32.CloseHandle(handle)


class TrayInstance:
    """Own a per-user/workspace/port mutex and optional attach listener."""

    def __init__(self, target: TrayTarget, *, mutex_api: MutexApi | None = None) -> None:
        self.target = target
        self._mutex_api = mutex_api or Win32MutexApi()
        self._mutex: Any = None
        self._listener: Any = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def acquire(self) -> bool:
        if self._mutex is not None:
            return True
        handle, already_exists = self._mutex_api.create(self.target.mutex_name)
        if already_exists:
            self._mutex_api.close(handle)
            return False
        self._mutex = handle
        return True

    def start_attach_listener(
        self,
        callback: Callable[[str], None],
        *,
        listener_factory: Callable[..., Any] | None = None,
    ) -> None:
        if self._mutex is None:
            raise TrayInstanceError("Acquire the tray instance before listening")
        if self._thread is not None:
            raise TrayInstanceError("Attach listener is already running")
        if listener_factory is None:
            if sys.platform != "win32":
                raise TrayInstanceUnavailable("Windows named pipes are unavailable")
            from multiprocessing.connection import Listener

            listener_factory = Listener
        self._listener = listener_factory(
            self.target.pipe_address,
            family="AF_PIPE",
            authkey=self.target.authkey,
        )
        self._thread = threading.Thread(
            target=self._serve,
            args=(callback,),
            name="artemis-tray-attach",
            daemon=True,
        )
        self._thread.start()

    def _serve(self, callback: Callable[[str], None]) -> None:
        while not self._stop.is_set():
            try:
                connection = self._listener.accept()
            except (OSError, EOFError):
                break
            try:
                action = decode_attach_request(connection.recv_bytes(_MAX_MESSAGE_BYTES))
                callback(action)
                connection.send_bytes(b'{"ok":true}')
            except (InvalidAttachRequest, OSError, EOFError):
                try:
                    connection.send_bytes(b'{"ok":false}')
                except (OSError, EOFError):
                    pass
            finally:
                connection.close()

    def close(self) -> None:
        self._stop.set()
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self._thread = None
        if self._mutex is not None:
            self._mutex_api.close(self._mutex)
            self._mutex = None

    def __enter__(self) -> TrayInstance:
        if not self.acquire():
            raise TrayInstanceError("Tray target is already owned")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def attach_existing(
    target: TrayTarget,
    action: str = "show",
    *,
    client_factory: Callable[..., Any] | None = None,
) -> bool:
    """Send one whitelisted action to the tray already bound to target."""
    payload = encode_attach_request(action)
    if client_factory is None:
        if sys.platform != "win32":
            raise TrayInstanceUnavailable("Windows named pipes are unavailable")
        from multiprocessing.connection import Client

        client_factory = Client
    try:
        connection = client_factory(
            target.pipe_address,
            family="AF_PIPE",
            authkey=target.authkey,
        )
        try:
            connection.send_bytes(payload)
            reply = connection.recv_bytes(_MAX_MESSAGE_BYTES)
            return reply == b'{"ok":true}'
        finally:
            connection.close()
    except (OSError, EOFError):
        return False
