from __future__ import annotations
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

try:
    from admin_console.schemas.email_schema import EmailSettingsResponse, EmailSettingsUpdate
    from admin_console.services.secret_store import SecretStore, create_secret_store
except ImportError:
    from apps.admin_console.schemas.email_schema import EmailSettingsResponse, EmailSettingsUpdate
    from apps.admin_console.services.secret_store import SecretStore, create_secret_store


class EmailSettingsError(RuntimeError):
    pass


class EmailSettingsConflict(EmailSettingsError):
    pass


class EmailSettingsNotConfigured(EmailSettingsError):
    pass


class EmailSettingsService:
    SECRET_KEY = "smtp-password"

    def __init__(self, secret_store: SecretStore, settings_path: Path | None = None) -> None:
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        self._path = settings_path or base / "Artemis" / "email_settings.json"
        self._secret_store = secret_store
        self._lock = RLock()

    def _read_metadata(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EmailSettingsError("Unable to read SMTP settings.") from exc
        if not isinstance(value, dict):
            raise EmailSettingsError("Stored SMTP settings are invalid.")
        return value

    def get(self) -> EmailSettingsResponse:
        with self._lock:
            return EmailSettingsResponse(
                **self._read_metadata(),
                password_configured=self._secret_store.get(self.SECRET_KEY) is not None,
            )

    def update(self, request: EmailSettingsUpdate) -> EmailSettingsResponse:
        with self._lock:
            current = self._read_metadata()
            version = int(current.get("version", 0))
            if request.expected_version is not None and request.expected_version != version:
                raise EmailSettingsConflict("SMTP settings were changed by another request.")
            password = request.password.get_secret_value() if request.password is not None else None
            existing = self._secret_store.get(self.SECRET_KEY)
            if request.enabled and not (password or existing):
                raise EmailSettingsError(
                    "An SMTP password is required before email can be enabled."
                )
            metadata = request.model_dump(exclude={"password", "expected_version"})
            metadata["version"] = version + 1
            if password:
                self._secret_store.set(self.SECRET_KEY, password)
            self._write_metadata(metadata)
            return EmailSettingsResponse(**metadata, password_configured=bool(password or existing))

    def _write_metadata(self, metadata: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(temporary, self._path)
        except OSError as exc:
            raise EmailSettingsError("Unable to save SMTP settings.") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def clear_password(self) -> EmailSettingsResponse:
        with self._lock:
            self._secret_store.delete(self.SECRET_KEY)
            metadata = self._read_metadata()
            if metadata.get("enabled"):
                metadata["enabled"] = False
                metadata["version"] = int(metadata.get("version", 0)) + 1
                self._write_metadata(metadata)
            return EmailSettingsResponse(**metadata, password_configured=False)

    def connection_parameters(self) -> tuple[EmailSettingsResponse, str]:
        settings = self.get()
        if not settings.smtp_host or not settings.sender_email:
            raise EmailSettingsNotConfigured("SMTP settings are not configured.")
        password = self._secret_store.get(self.SECRET_KEY)
        if not password:
            raise EmailSettingsNotConfigured("SMTP password is not configured.")
        return settings, password


def create_email_settings_service() -> EmailSettingsService:
    return EmailSettingsService(create_secret_store())


email_settings_service = create_email_settings_service()

