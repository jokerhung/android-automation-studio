from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from artemis.config import DB_PATH

try:
    from admin_console.database.connection import db_session
except ImportError:
    from apps.admin_console.database.connection import db_session

_DEFAULT = {
    "enabled": False,
    "smtp_host": "",
    "smtp_port": 587,
    "security": "starttls",
    "sender_email": "",
    "sender_name": "ARTEMIS",
    "smtp_username": "",
    "config_version": 0,
    "last_test_at": None,
    "last_test_status": None,
    "last_test_error_code": None,
}


class EmailSettingsRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH

    def get(self):
        with db_session(self.db_path) as conn:
            row = conn.execute("SELECT * FROM email_settings WHERE id=1").fetchone()
        if not row:
            return dict(_DEFAULT)
        value = dict(row)
        value["enabled"] = bool(value["enabled"])
        return value

    def save(self, data, expected_version=None):
        current = self.get()
        if expected_version is not None and current["config_version"] != expected_version:
            return None
        now = datetime.now(UTC).isoformat()
        version = current["config_version"] + 1
        with db_session(self.db_path) as conn:
            conn.execute(
                """INSERT INTO email_settings(id,enabled,smtp_host,smtp_port,security,sender_email,sender_name,smtp_username,config_version,created_at,updated_at) VALUES(1,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled,smtp_host=excluded.smtp_host,smtp_port=excluded.smtp_port,security=excluded.security,sender_email=excluded.sender_email,sender_name=excluded.sender_name,smtp_username=excluded.smtp_username,config_version=excluded.config_version,updated_at=excluded.updated_at""",
                (
                    int(data["enabled"]),
                    data["smtp_host"],
                    data["smtp_port"],
                    data["security"],
                    data["sender_email"],
                    data.get("sender_name"),
                    data["smtp_username"],
                    version,
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get()

    def record_test(self, success: bool, error_code: str | None = None):
        now = datetime.now(UTC).isoformat()
        with db_session(self.db_path) as conn:
            conn.execute(
                "UPDATE email_settings SET last_test_at=?,last_test_status=?,last_test_error_code=?,updated_at=? WHERE id=1",
                (now, "success" if success else "failed", error_code, now),
            )
            conn.commit()


email_settings_repo = EmailSettingsRepository()
