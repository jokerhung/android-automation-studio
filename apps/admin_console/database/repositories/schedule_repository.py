from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from artemis.config import DB_PATH

try:
    from admin_console.database.connection import db_session
except ImportError:
    from apps.admin_console.database.connection import db_session


def iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


class ScheduleRepository:
    _SNAPSHOT_FIELDS = (
        "goal",
        "profile",
        "device_serial",
        "expected_output",
        "enable_outputter",
        "verification_level",
        "explorer_mode",
        "locked_app_package",
        "app_path",
        "name",
        "timezone",
        "email_enabled",
        "recipient_name",
        "recipient_email",
        "email_subject",
    )

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH

    @classmethod
    def _snapshot(cls, schedule):
        return {key: schedule.get(key) for key in cls._SNAPSHOT_FIELDS}

    @staticmethod
    def _row(row):
        if not row:
            return None
        value = dict(row)
        if "weekdays_json" in value:
            value["weekdays"] = json.loads(value.pop("weekdays_json") or "[]")
        if "enabled" in value:
            value["enabled"] = bool(value["enabled"])
        if "email_enabled" in value:
            value["email_enabled"] = bool(value["email_enabled"])
        if "task_snapshot_json" in value:
            value["task_snapshot"] = json.loads(value["task_snapshot_json"])
        return value

    def create(self, data, now, next_run, anchor):
        sid = str(uuid.uuid4())
        with db_session(self.db_path) as conn:
            conn.execute(
                """INSERT INTO task_schedules (id,name,goal,profile,device_serial,expected_output,enable_outputter,verification_level,explorer_mode,locked_app_package,app_path,schedule_type,interval_minutes,time_of_day,weekdays_json,timezone,interval_anchor_at,enabled,email_enabled,recipient_name,recipient_email,email_subject,version,next_run_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
                (
                    sid,
                    data["name"],
                    data["goal"],
                    data["profile"],
                    data["device_serial"],
                    data.get("expected_output"),
                    data.get("enable_outputter"),
                    data.get("verification_level"),
                    data.get("explorer_mode"),
                    data.get("locked_app_package"),
                    data.get("app_path"),
                    data["schedule_type"],
                    data.get("interval_minutes"),
                    data.get("time_of_day"),
                    json.dumps(data.get("weekdays", [])),
                    data["timezone"],
                    iso(anchor),
                    int(data["enabled"]),
                    int(data.get("email_enabled", False)),
                    data.get("recipient_name"),
                    data.get("recipient_email"),
                    data.get("email_subject"),
                    iso(next_run),
                    iso(now),
                    iso(now),
                ),
            )
            conn.commit()
        return self.get(sid)

    def get(self, sid, include_deleted=False):
        with db_session(self.db_path) as conn:
            return self._row(
                conn.execute(
                    "SELECT * FROM task_schedules WHERE id=?"
                    + ("" if include_deleted else " AND deleted_at IS NULL"),
                    (sid,),
                ).fetchone()
            )

    def list(self):
        with db_session(self.db_path) as conn:
            rows = conn.execute(
                """SELECT s.*,r.status AS last_run_status,r.session_id AS last_session_id,r.due_at AS last_due_at FROM task_schedules s LEFT JOIN task_schedule_runs r ON r.id=(SELECT id FROM task_schedule_runs WHERE schedule_id=s.id ORDER BY created_at DESC LIMIT 1) WHERE s.deleted_at IS NULL ORDER BY s.created_at DESC"""
            ).fetchall()
            return [self._row(r) for r in rows]

    def update(self, sid, expected_version, data, now, next_run, anchor):
        current = self.get(sid)
        if not current:
            return None, "not_found"
        merged = {**current, **data}
        fields = [
            "name",
            "goal",
            "profile",
            "device_serial",
            "expected_output",
            "enable_outputter",
            "verification_level",
            "explorer_mode",
            "locked_app_package",
            "app_path",
            "schedule_type",
            "interval_minutes",
            "time_of_day",
            "timezone",
            "email_enabled",
            "recipient_name",
            "recipient_email",
            "email_subject",
        ]
        values = [merged.get(f) for f in fields] + [
            json.dumps(merged.get("weekdays", [])),
            iso(anchor),
            int(merged["enabled"]),
            iso(next_run),
            iso(now),
            sid,
            expected_version,
        ]
        with db_session(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE task_schedules SET "
                + ",".join(f + "=?" for f in fields)
                + ",weekdays_json=?,interval_anchor_at=?,enabled=?,next_run_at=?,updated_at=?,version=version+1 WHERE id=? AND version=? AND deleted_at IS NULL",
                values,
            )
            conn.commit()
        return (self.get(sid), None) if cur.rowcount else (None, "conflict")

    def delete(self, sid, now):
        with db_session(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE task_schedules SET enabled=0,next_run_at=NULL,deleted_at=?,updated_at=?,version=version+1 WHERE id=? AND deleted_at IS NULL",
                (iso(now), iso(now), sid),
            )
            conn.commit()
            return bool(cur.rowcount)

    def find_manual_run(self, sid, key):
        with db_session(self.db_path) as conn:
            return self._row(
                conn.execute(
                    "SELECT * FROM task_schedule_runs WHERE schedule_id=? AND trigger='manual' AND idempotency_key=?",
                    (sid, key),
                ).fetchone()
            )

    def create_manual_run(self, s, key, now):
        run_id = str(uuid.uuid4())
        session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"artemis:schedule:{s['id']}:manual:{key}"))
        snap = self._snapshot(s)
        try:
            with db_session(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO task_schedule_runs(id,schedule_id,schedule_version,due_at,trigger,idempotency_key,task_snapshot_json,status,session_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        s["id"],
                        s["version"],
                        iso(now),
                        "manual",
                        key,
                        json.dumps(snap),
                        "dispatch_pending",
                        session_id,
                        iso(now),
                        iso(now),
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            with db_session(self.db_path) as conn:
                return self._row(
                    conn.execute(
                        "SELECT * FROM task_schedule_runs WHERE schedule_id=? AND trigger='manual' AND idempotency_key=?",
                        (s["id"], key),
                    ).fetchone()
                ), False
        return self.get_run(run_id), True

    def get_run(self, rid):
        with db_session(self.db_path) as conn:
            return self._row(
                conn.execute("SELECT * FROM task_schedule_runs WHERE id=?", (rid,)).fetchone()
            )

    def get_run_by_session(self, session_id):
        with db_session(self.db_path) as conn:
            return self._row(
                conn.execute(
                    "SELECT * FROM task_schedule_runs WHERE session_id=? ORDER BY created_at DESC LIMIT 1",
                    (str(session_id),),
                ).fetchone()
            )

    def terminal_email_runs_without_notification(self):
        with db_session(self.db_path) as conn:
            rows = conn.execute(
                """SELECT r.* FROM task_schedule_runs r LEFT JOIN task_email_notifications n ON n.schedule_run_id=r.id AND n.notification_type='task_result' WHERE r.status IN ('completed','failed','cancelled') AND n.id IS NULL ORDER BY r.finished_at LIMIT 100"""
            ).fetchall()
            return [self._row(row) for row in rows]

    def update_run(self, rid, status, now, error_code=None, error_message=None):
        with db_session(self.db_path) as conn:
            conn.execute(
                "UPDATE task_schedule_runs SET status=?,safe_error_code=?,safe_error_message=?,queued_at=CASE WHEN ?='queued' THEN ? ELSE queued_at END,updated_at=? WHERE id=?",
                (status, error_code, error_message, status, iso(now), iso(now), rid),
            )
            conn.commit()
        return self.get_run(rid)

    def update_run_by_session(self, session_id, status, now):
        terminal = status in {"completed", "success", "failed", "cancelled"}
        normalized = "completed" if status == "success" else status
        with db_session(self.db_path) as conn:
            conn.execute(
                "UPDATE task_schedule_runs SET status=?, started_at=CASE WHEN ?='running' THEN COALESCE(started_at,?) ELSE started_at END, finished_at=CASE WHEN ? THEN ? ELSE finished_at END, updated_at=? WHERE session_id=?",
                (
                    normalized,
                    normalized,
                    iso(now),
                    int(terminal),
                    iso(now),
                    iso(now),
                    str(session_id),
                ),
            )
            conn.commit()

    def runs(self, sid, limit=50, offset=0):
        with db_session(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM task_schedule_runs WHERE schedule_id=?", (sid,)
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM task_schedule_runs WHERE schedule_id=? ORDER BY due_at DESC LIMIT ? OFFSET ?",
                (sid, limit, offset),
            ).fetchall()
            return [self._row(r) for r in rows], total

    def acquire_lease(self, owner, now, ttl=5):
        with db_session(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT owner,expires_at,generation FROM task_scheduler_lease WHERE lease_name='scheduler'"
            ).fetchone()
            if row and row[0] != owner and row[1] > iso(now):
                conn.rollback()
                return None
            gen = (row[2] + 1) if row and row[0] != owner else (row[2] if row else 1)
            conn.execute(
                "INSERT OR REPLACE INTO task_scheduler_lease VALUES('scheduler',?,?,?,?)",
                (owner, gen, iso(now + timedelta(seconds=ttl)), iso(now)),
            )
            conn.commit()
            return gen

    def release_lease(self, owner):
        with db_session(self.db_path) as conn:
            conn.execute(
                "DELETE FROM task_scheduler_lease WHERE lease_name='scheduler' AND owner=?",
                (owner,),
            )
            conn.commit()

    def pending_runs(self):
        with db_session(self.db_path) as conn:
            return [
                self._row(r)
                for r in conn.execute(
                    "SELECT * FROM task_schedule_runs WHERE status='dispatch_pending' ORDER BY created_at LIMIT 50"
                ).fetchall()
            ]

    def due_schedules(self, now):
        with db_session(self.db_path) as conn:
            return [
                self._row(r)
                for r in conn.execute(
                    "SELECT * FROM task_schedules WHERE enabled=1 AND deleted_at IS NULL AND next_run_at<=? ORDER BY next_run_at LIMIT 20",
                    (iso(now),),
                ).fetchall()
            ]

    def claim_occurrence(self, schedule, due, next_run, now, owner, generation):
        """Atomically fence leader, persist an occurrence, and advance the schedule."""
        rid = str(uuid.uuid4())
        session_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"artemis:schedule:{schedule['id']}:{iso(due)}")
        )
        snap = self._snapshot(schedule)
        with db_session(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            lease = conn.execute(
                "SELECT owner,generation,expires_at FROM task_scheduler_lease WHERE lease_name='scheduler'"
            ).fetchone()
            current = conn.execute(
                "SELECT version,enabled,next_run_at,deleted_at FROM task_schedules WHERE id=?",
                (schedule["id"],),
            ).fetchone()
            valid = (
                lease
                and lease[0] == owner
                and lease[1] == generation
                and lease[2] > iso(now)
                and current
                and current[1]
                and current[3] is None
                and current[0] == schedule["version"]
                and current[2] == iso(due)
            )
            if not valid:
                conn.rollback()
                return None
            active = conn.execute(
                "SELECT 1 FROM task_schedule_runs WHERE schedule_id=? AND status IN ('dispatch_pending','claimed','queued','running','paused') LIMIT 1",
                (schedule["id"],),
            ).fetchone()
            status = (
                "skipped_overlap"
                if active
                else ("skipped_misfire" if (now - due).total_seconds() > 60 else "dispatch_pending")
            )
            try:
                conn.execute(
                    "INSERT INTO task_schedule_runs(id,schedule_id,schedule_version,due_at,trigger,task_snapshot_json,status,session_id,claim_owner,claim_generation,created_at,updated_at,lateness_ms) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        schedule["id"],
                        schedule["version"],
                        iso(due),
                        "scheduled",
                        json.dumps(snap),
                        status,
                        session_id,
                        owner,
                        generation,
                        iso(now),
                        iso(now),
                        max(0, int((now - due).total_seconds() * 1000)),
                    ),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                return None
            updated = conn.execute(
                "UPDATE task_schedules SET next_run_at=?,updated_at=?,version=version+1 WHERE id=? AND version=? AND next_run_at=? AND enabled=1 AND deleted_at IS NULL",
                (iso(next_run), iso(now), schedule["id"], schedule["version"], iso(due)),
            )
            if updated.rowcount != 1:
                conn.rollback()
                return None
            conn.commit()
        return self.get_run(rid)

    def create_scheduled_run(
        self, s, due, now, status="dispatch_pending", owner=None, generation=None
    ):
        rid = str(uuid.uuid4())
        session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"artemis:schedule:{s['id']}:{iso(due)}"))
        snap = self._snapshot(s)
        try:
            with db_session(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO task_schedule_runs(id,schedule_id,schedule_version,due_at,trigger,task_snapshot_json,status,session_id,claim_owner,claim_generation,created_at,updated_at,lateness_ms) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        s["id"],
                        s["version"],
                        iso(due),
                        "scheduled",
                        json.dumps(snap),
                        status,
                        session_id,
                        owner,
                        generation,
                        iso(now),
                        iso(now),
                        max(0, int((now - due).total_seconds() * 1000)),
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            return None
        return self.get_run(rid)

    def has_active_run(self, sid):
        with db_session(self.db_path) as conn:
            return bool(
                conn.execute(
                    "SELECT 1 FROM task_schedule_runs WHERE schedule_id=? AND status IN ('dispatch_pending','claimed','queued','running','paused') LIMIT 1",
                    (sid,),
                ).fetchone()
            )


schedule_repo = ScheduleRepository()
