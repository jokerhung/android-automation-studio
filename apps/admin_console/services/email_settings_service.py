from __future__ import annotations
import json
import base64
import os
import sys
from pathlib import Path
from typing import Any
from artemis.config.sqlite_store import SettingsStore, get_settings_store

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

    def __init__(
        self, secret_store: SecretStore | None, settings_path: Path | None = None, *, store=None
    ) -> None:
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        self._path = settings_path or base / "Artemis" / "email_settings.json"
        self._secret_store = secret_store
        self.store = store or (
            SettingsStore(self._path.with_suffix(".sqlite3"))
            if settings_path is not None
            else get_settings_store()
        )

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

    def _protect(self, value):
        return base64.b64encode(self._secret_store.protect(value)).decode("ascii")

    def _password(self, document):
        protected = document.get("password")
        return self._secret_store.unprotect(base64.b64decode(protected)) if protected else None

    def _read(self):
        def migrate():
            metadata = self._read_metadata()
            secret_store = self._secret_store
            if secret_store is None and sys.platform == "win32":
                secret_store = self._secret_store = create_secret_store()
            password = secret_store.get(self.SECRET_KEY) if secret_store else None
            # Validate before committing the imported document.
            metadata = EmailSettingsResponse(
                **metadata, password_configured=bool(password)
            ).model_dump(exclude={"password_configured"})
            return {"settings": metadata, "password": self._protect(password) if password else None}

        return self.store.get_or_import("email", migrate)

    def initialize(self) -> None:
        """Seed defaults or import legacy settings without requiring SMTP setup."""
        self._read()

    def _response(self, document):
        return EmailSettingsResponse(
            **document["settings"], password_configured=bool(self._password(document))
        )

    def get(self) -> EmailSettingsResponse:
        document, _ = self._read()
        return self._response(document)

    def update(self, request: EmailSettingsUpdate) -> EmailSettingsResponse:
        self._read()

        def change(document):
            version = int(document["settings"].get("version", 0))
            if request.expected_version is not None and request.expected_version != version:
                raise EmailSettingsConflict("SMTP settings were changed by another request.")
            password = request.password.get_secret_value() if request.password is not None else None
            if request.enabled and not (password or self._password(document)):
                raise EmailSettingsError(
                    "An SMTP password is required before email can be enabled."
                )
            metadata = {
                **document["settings"],
                **{
                    key: value
                    for key, value in request.model_dump(
                        exclude={"password", "expected_version"}
                    ).items()
                    if not isinstance(value, str) or value.strip()
                },
            }
            metadata["version"] = version + 1
            document["settings"] = metadata
            if password:
                document["password"] = self._protect(password)
            return document

        document, _ = self.store.update("email", change)
        return self._response(document)

    def clear_password(self) -> EmailSettingsResponse:
        self._read()

        def change(document):
            metadata = document["settings"]
            if metadata.get("enabled"):
                metadata["enabled"] = False
                metadata["version"] = int(metadata.get("version", 0)) + 1
            document["password"] = None
            return document

        document, _ = self.store.update("email", change)
        return self._response(document)

    def connection_parameters(self) -> tuple[EmailSettingsResponse, str]:
        document, _ = self._read()
        settings = self._response(document)
        if not settings.smtp_host or not settings.sender_email:
            raise EmailSettingsNotConfigured("SMTP settings are not configured.")
        password = self._password(document)
        if not password:
            raise EmailSettingsNotConfigured("SMTP password is not configured.")
        return settings, password


def create_email_settings_service() -> EmailSettingsService:
    return EmailSettingsService(create_secret_store())
