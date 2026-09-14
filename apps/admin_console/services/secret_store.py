from __future__ import annotations

from abc import ABC, abstractmethod
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys


class SecretStoreError(RuntimeError):
    """A secret could not be securely stored or retrieved."""


class SecretStoreUnsupported(SecretStoreError):
    """No supported OS-backed secret storage is available."""


class SecretStore(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> bool: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[_DataBlob, object]:
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


class WindowsDPAPISecretStore(SecretStore):
    """Current-user Windows DPAPI store backed only by encrypted bytes on disk."""

    _DESCRIPTION = "Artemis SMTP credential"
    _ENTROPY = b"Artemis.AdminConsole.SMTP.v1"

    def __init__(self, directory: Path | None = None) -> None:
        if sys.platform != "win32":
            raise SecretStoreUnsupported("SMTP password storage requires Windows DPAPI.")
        base = directory or Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        self._directory = base / "Artemis" / "secrets"

    def _path(self, key: str) -> Path:
        if not key or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for c in key
        ):
            raise SecretStoreError("Invalid secret key.")
        return self._directory / f"{key}.dpapi"

    @staticmethod
    def _crypt32():
        try:
            return ctypes.windll.crypt32, ctypes.windll.kernel32
        except AttributeError as exc:
            raise SecretStoreUnsupported("Windows DPAPI is unavailable.") from exc

    def set(self, key: str, value: str) -> None:
        if not value:
            raise SecretStoreError("Refusing to store an empty secret.")
        crypt32, kernel32 = self._crypt32()
        plain, plain_buffer = _blob(value.encode("utf-8"))
        entropy, entropy_buffer = _blob(self._ENTROPY)
        output = _DataBlob()
        if not crypt32.CryptProtectData(
            ctypes.byref(plain),
            self._DESCRIPTION,
            ctypes.byref(entropy),
            None,
            None,
            0,
            ctypes.byref(output),
        ):
            raise SecretStoreError("Windows DPAPI could not protect the SMTP password.")
        try:
            encrypted = ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
            del plain_buffer, entropy_buffer
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        try:
            temporary.write_bytes(encrypted)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, key: str) -> str | None:
        path = self._path(key)
        if not path.exists():
            return None
        encrypted = path.read_bytes()
        crypt32, kernel32 = self._crypt32()
        protected, protected_buffer = _blob(encrypted)
        entropy, entropy_buffer = _blob(self._ENTROPY)
        output = _DataBlob()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(protected),
            None,
            ctypes.byref(entropy),
            None,
            None,
            0,
            ctypes.byref(output),
        ):
            raise SecretStoreError("Windows DPAPI could not decrypt the SMTP password.")
        try:
            return ctypes.string_at(output.pbData, output.cbData).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SecretStoreError("The stored SMTP password is invalid.") from exc
        finally:
            kernel32.LocalFree(output.pbData)
            del protected_buffer, entropy_buffer

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if not path.exists():
            return False
        path.unlink()
        return True


def create_secret_store() -> SecretStore:
    if sys.platform == "win32":
        return WindowsDPAPISecretStore()
    raise SecretStoreUnsupported("SMTP password storage is unsupported on this operating system.")
