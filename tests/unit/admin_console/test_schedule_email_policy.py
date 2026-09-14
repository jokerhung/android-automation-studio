from datetime import UTC, datetime
from pathlib import Path
import sqlite3

import pytest
from pydantic import ValidationError

from artemis.data_engine.storage import StorageManager
from apps.admin_console.database.repositories.schedule_repository import ScheduleRepository
from apps.admin_console.schemas.schedule_schema import ScheduleCreate, SchedulePatch
from apps.admin_console.services.schedule_service import ScheduleService


def _payload(**overrides):
    value = dict(
        name="Notify",
        goal="Perform a harmless task",
        profile="flash",
        device_serial="fake",
        schedule_type="interval",
        interval_minutes=15,
        timezone="UTC",
        enabled=True,
    )
    value.update(overrides)
    return value


def test_email_policy_defaults_off_and_rejects_unsafe_headers():
    assert ScheduleCreate(**_payload()).email_enabled is False
    with pytest.raises(ValidationError):
        ScheduleCreate(**_payload(email_enabled=True, recipient_email="user@example.com", email_subject="Hi\r\nBcc: bad@example.com"))
    with pytest.raises(ValidationError):
        ScheduleCreate(**_payload(email_enabled=True, recipient_email="user@example.com", email_subject="{danger}"))
    with pytest.raises(ValidationError):
        ScheduleCreate(**_payload(email_enabled=True, recipient_email="user@example.com"))


def test_policy_is_persisted_and_frozen_in_manual_run_snapshot(tmp_path: Path):
    db = tmp_path / "schedule.db"
    StorageManager(db, tmp_path / "traces")
    repo = ScheduleRepository(db)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    schedule = repo.create(
        ScheduleCreate(**_payload(
            email_enabled=True,
            recipient_name="Nguyễn Văn A",
            recipient_email="recipient@example.com",
            email_subject="ARTEMIS — {schedule_name} — {status}",
        )).model_dump(),
        now,
        datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        now,
    )
    run, created = repo.create_manual_run(schedule, "once", now)
    assert created is True
    assert run["task_snapshot"]["recipient_email"] == "recipient@example.com"
    service = ScheduleService(repo=repo, clock=lambda: now)
    updated, error = service.update(schedule["id"], SchedulePatch(
        expected_version=schedule["version"],
        recipient_email="other@example.com",
    ))
    assert error is None and updated["recipient_email"] == "other@example.com"
    assert repo.get_run(run["id"])["task_snapshot"]["recipient_email"] == "recipient@example.com"


def test_migration_adds_email_tables_without_backfilling_enabled(tmp_path: Path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE task_schedules (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, goal TEXT NOT NULL, profile TEXT NOT NULL,
            device_serial TEXT NOT NULL, expected_output TEXT, enable_outputter INTEGER,
            verification_level TEXT, explorer_mode TEXT, locked_app_package TEXT, app_path TEXT,
            schedule_type TEXT NOT NULL, interval_minutes INTEGER, time_of_day TEXT,
            weekdays_json TEXT NOT NULL DEFAULT '[]', timezone TEXT NOT NULL,
            interval_anchor_at TEXT, enabled INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1,
            next_run_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT
        );
        INSERT INTO task_schedules VALUES (
            'old','Old','safe','flash','fake',NULL,NULL,NULL,NULL,NULL,NULL,'daily',NULL,'12:00:00',
            '[]','UTC',NULL,1,1,NULL,'2026-01-01','2026-01-01',NULL
        );
    """)
    conn.commit()
    conn.close()
    StorageManager(db, tmp_path / "traces")
    conn = sqlite3.connect(db)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(task_schedules)")}
    assert {"email_enabled", "recipient_name", "recipient_email", "email_subject"} <= columns
    assert conn.execute("SELECT email_enabled FROM task_schedules WHERE id='old'").fetchone()[0] == 0
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"email_settings", "task_email_notifications"} <= tables
    conn.close()
