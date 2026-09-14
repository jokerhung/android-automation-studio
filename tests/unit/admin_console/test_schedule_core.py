from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from artemis.data_engine.storage import StorageManager
from apps.admin_console.database.repositories.schedule_repository import ScheduleRepository
from apps.admin_console.schemas.schedule_schema import ScheduleRule
from apps.admin_console.services.schedule_recurrence import next_occurrence, preview_occurrences


def test_interval_uses_stable_anchor_and_seconds():
    rule = ScheduleRule(schedule_type="interval", interval_minutes=15, timezone="UTC")
    anchor = datetime(2026, 9, 14, 10, 0, 20, tzinfo=UTC)
    assert next_occurrence(rule, after=anchor, anchor_at=anchor) == datetime(
        2026, 9, 14, 10, 15, 20, tzinfo=UTC
    )
    assert next_occurrence(
        rule, after=datetime(2026, 9, 14, 10, 16, tzinfo=UTC), anchor_at=anchor
    ) == datetime(2026, 9, 14, 10, 30, 20, tzinfo=UTC)


def test_daily_is_strictly_after_and_keeps_seconds():
    rule = ScheduleRule(schedule_type="daily", time_of_day="08:30:05", timezone="Asia/Bangkok")
    after = datetime(2026, 9, 14, 1, 30, 5, tzinfo=UTC)
    assert next_occurrence(rule, after=after) == datetime(2026, 9, 15, 1, 30, 5, tzinfo=UTC)


def test_weekly_supports_multiple_iso_days():
    rule = ScheduleRule(
        schedule_type="weekly", time_of_day="09:00:00", weekdays=[1, 3, 5], timezone="UTC"
    )
    values = preview_occurrences(rule, after=datetime(2026, 9, 14, 9, 0, tzinfo=UTC), count=3)
    assert values == [
        datetime(2026, 9, 16, 9, 0, tzinfo=UTC),
        datetime(2026, 9, 18, 9, 0, tzinfo=UTC),
        datetime(2026, 9, 21, 9, 0, tzinfo=UTC),
    ]


def test_repository_schema_and_manual_idempotency(tmp_path: Path):
    db = tmp_path / "schedule.db"
    StorageManager(db_path=db, base_trace_dir=tmp_path / "traces")
    repo = ScheduleRepository(db)
    now = datetime(2026, 9, 14, 0, 0, tzinfo=UTC)
    data = dict(
        name="Test",
        goal="Open settings",
        profile="flash",
        device_serial="serial",
        expected_output=None,
        enable_outputter=None,
        verification_level=None,
        explorer_mode=None,
        locked_app_package=None,
        app_path=None,
        schedule_type="interval",
        interval_minutes=15,
        time_of_day=None,
        weekdays=[],
        timezone="UTC",
        enabled=True,
    )
    schedule = repo.create(data, now, datetime(2026, 9, 14, 0, 15, tzinfo=UTC), now)
    first, created = repo.create_manual_run(schedule, "request-1", now)
    second, created_again = repo.create_manual_run(schedule, "request-1", now)
    assert created is True and created_again is False and first["id"] == second["id"]
