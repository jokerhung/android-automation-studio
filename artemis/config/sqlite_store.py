"""Transactional settings shared by the console and task subprocesses.

Legacy files are import sources only. Once a document exists, edits to those
files (or inherited credentials) cannot replace its database values.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3

from dotenv import dotenv_values
from artemis.config.paths import get_config_path, get_data_engine_db_path, get_env_file
from artemis.utils.file import load_jsonc

PROVIDER_KEYS = {
    "openai_acp": [],
    "openai": ["OPENAI_API_KEY"],
    "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GCP_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openrouter": ["OPEN_ROUTER_API_KEY"],
    "xai": ["XAI_API_KEY"],
    "custom": ["OPENAI_API_KEY"],
    "ollama": ["OPENAI_API_KEY"],
    "vllm": ["OPENAI_API_KEY"],
}
MODEL_ENV_KEYS = tuple(dict.fromkeys(key for keys in PROVIDER_KEYS.values() for key in keys)) + (
    "OPENAI_BASE_URL",
    "ARTEMIS_CODEX_PATH",
    "OCR_API_KEY",
    "VISION_API_KEY",
    "API_KEY",
)


class SettingsStore:
    def __init__(self, db_path: Path | None = None):
        self.path = (
            Path(db_path)
            if db_path is not None
            else Path(os.environ.get("DATA_ENGINE_DB_PATH") or get_data_engine_db_path())
        )

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS application_settings (
                name TEXT PRIMARY KEY, payload TEXT NOT NULL, version INTEGER NOT NULL
            )""")
            yield conn
        finally:
            conn.close()

    def get_or_import(self, name, importer):
        with self.connection() as conn, conn:
            row = conn.execute(
                "SELECT payload,version FROM application_settings WHERE name=?", (name,)
            ).fetchone()
            if row is not None:
                return json.loads(row[0]), row[1]
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT payload,version FROM application_settings WHERE name=?", (name,)
            ).fetchone()
            if row is None:
                value = importer()
                conn.execute(
                    "INSERT INTO application_settings VALUES(?,?,?)", (name, json.dumps(value), 1)
                )
                return value, 1
            return json.loads(row[0]), row[1]

    def update(self, name, change, expected_version=None):
        with self.connection() as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT payload,version FROM application_settings WHERE name=?", (name,)
            ).fetchone()
            if row is None:
                raise ValueError("Settings have not been initialized")
            value, version = json.loads(row[0]), row[1]
            if expected_version is not None and str(version) != str(expected_version):
                raise FileExistsError("Configuration changed. Reload before saving.")
            updated = change(value)
            conn.execute(
                "UPDATE application_settings SET payload=?,version=? WHERE name=?",
                (json.dumps(updated), version + 1, name),
            )
            return updated, version + 1

    def model(self, config_path=None, env_path=None):
        def migrate():
            config = {}
            if config_path is not None:
                path = Path(config_path)
            else:
                path = None
                for candidate in ("artemis.jsonc", "artemis.json", "llm-config.json"):
                    try:
                        path = get_config_path(candidate)
                        break
                    except FileNotFoundError:
                        continue
            if path is not None:
                with path.open(encoding="utf-8") as stream:
                    config = load_jsonc(stream)
            source = Path(env_path) if env_path is not None else get_env_file()
            values = dotenv_values(source) if source.exists() else {}
            # Preserve older configurations that used full per-node model maps.
            model = {k: v for k, v in config.items() if k not in {"agent", "device", "output"}}
            model.setdefault(
                "default",
                {
                    "provider": "google",
                    "model": "gemini-3.8-flash",
                    "fallback": {"provider": "google", "model": "gemini-3.7-flash"},
                },
            )
            credentials = {
                key: str(values.get(key) or os.environ.get(key) or "") for key in MODEL_ENV_KEYS
            }
            return {"config": model, "credentials": credentials}

        return self.get_or_import("model", migrate)

    def android(self, *, host=None, port=None):
        def migrate():
            from urllib.parse import urlsplit
            from artemis.config.constants import DEFAULT_ADB_HOST, DEFAULT_ADB_PORT

            source = get_env_file()
            legacy = dotenv_values(source) if source.exists() else {}
            selected_host = host or os.environ.get("ADB_HOST") or legacy.get("ADB_HOST")
            selected_port = port or os.environ.get("ADB_PORT") or legacy.get("ADB_PORT")
            socket = os.environ.get("ADB_SERVER_SOCKET") or legacy.get("ADB_SERVER_SOCKET")
            if socket and not (
                os.environ.get("ADB_HOST")
                or os.environ.get("ADB_PORT")
                or legacy.get("ADB_HOST")
                or legacy.get("ADB_PORT")
            ):
                parsed = urlsplit("//" + socket.removeprefix("tcp:"))
                selected_host, selected_port = parsed.hostname, parsed.port
            return {
                "host": selected_host or DEFAULT_ADB_HOST,
                "port": int(selected_port or DEFAULT_ADB_PORT),
            }

        return self.get_or_import("android", migrate)

    def history(self):
        """Retention policy for old task history. ``0`` disables a rule."""
        return self.get_or_import(
            "history",
            lambda: {"media_retention_days": 0, "history_retention_days": 0, "last_run": None},
        )


def get_settings_store():
    return SettingsStore()
