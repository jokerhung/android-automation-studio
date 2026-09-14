from __future__ import annotations
from datetime import UTC, datetime, timedelta
import json
import uuid
from pathlib import Path
from artemis.config import DB_PATH

try:
    from admin_console.database.connection import db_session
except ImportError:
    from apps.admin_console.database.connection import db_session


def iso(v):
    return v.astimezone(UTC).isoformat() if v else None


class EmailNotificationRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH

    def enqueue(self, run, config_version: int, now: datetime):
        snap = run.get("task_snapshot") or {}
        if not snap.get("email_enabled"):
            return None, False
        nid = str(uuid.uuid4())
        message_id = f"<artemis-{run['id']}@local>"
        with db_session(self.db_path) as c:
            c.execute(
                "INSERT OR IGNORE INTO task_email_notifications(id,schedule_run_id,session_id,notification_type,recipient_name,recipient_email,smtp_config_version,status,attempt_count,next_attempt_at,message_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    nid,
                    run["id"],
                    run["session_id"],
                    "task_result",
                    snap.get("recipient_name"),
                    snap["recipient_email"],
                    config_version,
                    "pending",
                    0,
                    iso(now),
                    message_id,
                    iso(now),
                    iso(now),
                ),
            )
            row = c.execute(
                "SELECT * FROM task_email_notifications WHERE schedule_run_id=? AND notification_type='task_result'",
                (run["id"],),
            ).fetchone()
            c.commit()
            return dict(row), row["id"] == nid

    def get_for_run(self, run_id):
        with db_session(self.db_path) as c:
            row = c.execute(
                "SELECT * FROM task_email_notifications WHERE schedule_run_id=?", (run_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_for_runs(self, run_ids):
        ids = list(run_ids)
        if not ids:
            return {}
        with db_session(self.db_path) as c:
            return {
                r["schedule_run_id"]: dict(r)
                for r in c.execute(
                    f"SELECT * FROM task_email_notifications WHERE schedule_run_id IN ({','.join('?' * len(ids))})",
                    ids,
                ).fetchall()
            }

    def claim(self, owner, now, lease=60):
        with db_session(self.db_path) as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT * FROM task_email_notifications WHERE status IN ('pending','retry') AND next_attempt_at<=? AND (claim_expires_at IS NULL OR claim_expires_at<=?) ORDER BY created_at LIMIT 1",
                (iso(now), iso(now)),
            ).fetchone()
            if not row:
                c.commit()
                return None
            changed = c.execute(
                "UPDATE task_email_notifications SET status='sending',claim_owner=?,claim_expires_at=?,attempt_count=attempt_count+1,updated_at=? WHERE id=? AND status IN ('pending','retry')",
                (owner, iso(now + timedelta(seconds=lease)), iso(now), row["id"]),
            ).rowcount
            c.commit()
            return self.get(row["id"]) if changed else None

    def get(self, nid):
        with db_session(self.db_path) as c:
            row = c.execute("SELECT * FROM task_email_notifications WHERE id=?", (nid,)).fetchone()
            return dict(row) if row else None

    def finish(self, nid, owner, status, now, **fields):
        allowed = {
            "rendered_subject",
            "rendered_body",
            "report_path",
            "report_sha256",
            "report_size_bytes",
            "report_complete",
            "accepted_at",
            "safe_error_code",
            "safe_error_message",
            "next_attempt_at",
        }
        values = {k: v for k, v in fields.items() if k in allowed}
        sets = ["status=?", "claim_owner=NULL", "claim_expires_at=NULL", "updated_at=?"] + [
            f"{k}=?" for k in values
        ]
        with db_session(self.db_path) as c:
            changed = c.execute(
                f"UPDATE task_email_notifications SET {','.join(sets)} WHERE id=? AND claim_owner=?",
                (status, iso(now), *values.values(), nid, owner),
            ).rowcount
            c.commit()
            return bool(changed)

    def manual_retry(self, run_id, now=None):
        if now is None:
            return self.manual_retry_id(run_id)
        with db_session(self.db_path) as c:
            changed = c.execute(
                "UPDATE task_email_notifications SET status='pending',next_attempt_at=?,claim_owner=NULL,claim_expires_at=NULL,safe_error_code=NULL,safe_error_message=NULL,updated_at=? WHERE schedule_run_id=? AND status IN ('failed','delivery_unknown','report_incomplete','attachment_too_large')",
                (iso(now), iso(now), run_id),
            ).rowcount
            c.commit()
            return bool(changed)


notification_repo = EmailNotificationRepository()

# Generic core API for terminal session notifications. Kept alongside the
# schedule-specific adapter above until integration converges on one table.
from dataclasses import dataclass
import time
from typing import Any, Callable


@dataclass(frozen=True)
class NotificationClaim:
    id: int
    run_id: str
    notification_type: str
    recipient: str
    subject: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    lease_owner: str


EmailNotificationRepository.SCHEMA_SQL = """
CREATE TABLE email_notification_outbox (
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, notification_type TEXT NOT NULL,
 recipient TEXT NOT NULL, subject TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}',
 status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 5, next_attempt_at REAL NOT NULL, lease_owner TEXT,
 lease_expires_at REAL, smtp_message_id TEXT, last_error TEXT, report_path TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL, accepted_at REAL, suppressed_at REAL,
 failed_at REAL, UNIQUE(run_id, notification_type));
CREATE INDEX IF NOT EXISTS email_notification_claim_idx
 ON email_notification_outbox(status,next_attempt_at,lease_expires_at,id);
"""


def _generic_init(self, db_path=None, clock=time.time):
    self.db_path = Path(db_path) if db_path is not None else DB_PATH
    self.clock = clock


EmailNotificationRepository.__init__ = _generic_init


def _enqueue_core(
    self,
    run_id,
    notification_type,
    recipient,
    subject,
    payload=None,
    *,
    max_attempts=5,
    suppressed_reason=None,
):
    now = self.clock()
    status = "suppressed" if suppressed_reason else "pending"
    with db_session(self.db_path) as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO email_notification_outbox(run_id,notification_type,recipient,subject,payload_json,status,attempts,max_attempts,next_attempt_at,last_error,created_at,updated_at,suppressed_at) VALUES(?,?,?,?,?,?,0,?,?,?,?,?,?)",
            (
                str(run_id),
                str(notification_type),
                str(recipient),
                str(subject),
                json.dumps(
                    payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
                status,
                max_attempts,
                now,
                suppressed_reason,
                now,
                now,
                now if suppressed_reason else None,
            ),
        )
        row = c.execute(
            "SELECT id FROM email_notification_outbox WHERE run_id=? AND notification_type=?",
            (str(run_id), str(notification_type)),
        ).fetchone()
        c.commit()
        return int(row[0]), cur.rowcount == 1


EmailNotificationRepository.enqueue_core = _enqueue_core
_schedule_enqueue = EmailNotificationRepository.enqueue


def _enqueue_dispatch(self, *args, **kwargs):
    if args and isinstance(args[0], dict):
        return _schedule_enqueue(self, *args, **kwargs)
    return self.enqueue_core(*args, **kwargs)


EmailNotificationRepository.enqueue = _enqueue_dispatch


def _claim_next(self, worker_id, *, lease_seconds=60.0):
    now = self.clock()
    with db_session(self.db_path) as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute(
            "SELECT * FROM email_notification_outbox WHERE attempts<max_attempts AND next_attempt_at<=? AND (status IN ('pending','retry') OR (status='sending' AND lease_expires_at<=?)) ORDER BY next_attempt_at,id LIMIT 1",
            (now, now),
        ).fetchone()
        if not row:
            c.commit()
            return None
        token = f"{worker_id}:{uuid.uuid4().hex}"
        changed = c.execute(
            "UPDATE email_notification_outbox SET status='sending',attempts=attempts+1,lease_owner=?,lease_expires_at=?,updated_at=? WHERE id=? AND (status IN ('pending','retry') OR (status='sending' AND lease_expires_at<=?))",
            (token, now + lease_seconds, now, row["id"], now),
        ).rowcount
        if not changed:
            c.rollback()
            return None
        row = c.execute(
            "SELECT * FROM email_notification_outbox WHERE id=?", (row["id"],)
        ).fetchone()
        c.commit()
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except (ValueError, TypeError):
        payload = {}
    return NotificationClaim(
        int(row["id"]),
        str(row["run_id"]),
        str(row["notification_type"]),
        str(row["recipient"]),
        str(row["subject"]),
        payload if isinstance(payload, dict) else {},
        int(row["attempts"]),
        int(row["max_attempts"]),
        token,
    )


EmailNotificationRepository.claim_next = _claim_next


def _finish_core(self, claim, status, **fields):
    allowed = {
        "smtp_message_id",
        "last_error",
        "next_attempt_at",
        "accepted_at",
        "failed_at",
        "report_path",
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    sets = ["status=?", "lease_owner=NULL", "lease_expires_at=NULL", "updated_at=?"] + [
        f"{k}=?" for k in fields
    ]
    params = [status, self.clock(), *fields.values(), claim.id, claim.lease_owner]
    with db_session(self.db_path) as c:
        changed = c.execute(
            f"UPDATE email_notification_outbox SET {','.join(sets)} WHERE id=? AND status='sending' AND lease_owner=?",
            params,
        ).rowcount
        c.commit()
        return bool(changed)


EmailNotificationRepository.finish_core = _finish_core
EmailNotificationRepository.mark_accepted = lambda self, claim, smtp_message_id=None: (
    self.finish_core(
        claim,
        "accepted",
        smtp_message_id=smtp_message_id,
        accepted_at=self.clock(),
        last_error=None,
    )
)
EmailNotificationRepository.mark_delivery_unknown = lambda self, claim, error: self.finish_core(
    claim, "delivery_unknown", last_error=str(error)[:2000]
)


def _mark_failed(self, claim, error, *, retry_at):
    terminal = claim.attempts >= claim.max_attempts
    return self.finish_core(
        claim,
        "failed" if terminal else "retry",
        last_error=str(error)[:2000],
        next_attempt_at=retry_at,
        failed_at=self.clock() if terminal else None,
    )


EmailNotificationRepository.mark_failed_attempt = _mark_failed


def _manual_retry_id(self, notification_id):
    now = self.clock()
    with db_session(self.db_path) as c:
        changed = c.execute(
            "UPDATE email_notification_outbox SET status='pending', attempts=0, "
            "next_attempt_at=?, lease_owner=NULL, lease_expires_at=NULL, failed_at=NULL, "
            "last_error=NULL, updated_at=? WHERE id=? AND status IN ('failed','delivery_unknown')",
            (now, now, int(notification_id)),
        ).rowcount
        c.commit()
        return bool(changed)


EmailNotificationRepository.manual_retry_id = _manual_retry_id
_schedule_get = EmailNotificationRepository.get


def _get_dispatch(self, identity):
    if isinstance(identity, int):
        with db_session(self.db_path) as c:
            row = c.execute(
                "SELECT * FROM email_notification_outbox WHERE id=?", (identity,)
            ).fetchone()
            return dict(row) if row else None
    return _schedule_get(self, identity)


EmailNotificationRepository.get = _get_dispatch
