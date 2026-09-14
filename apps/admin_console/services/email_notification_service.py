from __future__ import annotations

import asyncio
from dataclasses import dataclass
from email.message import EmailMessage
import smtplib
import time
import hashlib
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from artemis.config import DB_PATH

try:
    from admin_console.database.repositories.email_notification_repository import (
        EmailNotificationRepository,
    )
    from admin_console.database.repositories.schedule_repository import schedule_repo
    from admin_console.services.email_settings_service import create_email_settings_service
    from admin_console.services.notification_redaction import redact_text
    from admin_console.services.smtp_service import SMTPService
    from admin_console.services.task_log_export_service import (
        TaskLogExportService,
        safe_report_filename,
    )
except ImportError:
    from apps.admin_console.database.repositories.email_notification_repository import (
        EmailNotificationRepository,
    )
    from apps.admin_console.database.repositories.schedule_repository import schedule_repo
    from apps.admin_console.services.email_settings_service import create_email_settings_service
    from apps.admin_console.services.notification_redaction import redact_text
    from apps.admin_console.services.smtp_service import SMTPService
    from apps.admin_console.services.task_log_export_service import (
        TaskLogExportService,
        safe_report_filename,
    )


@dataclass(frozen=True)
class EmailNotificationSettings:
    enabled: bool
    sender: str
    recipient: str
    notification_type: str = "task_terminal"
    max_attempts: int = 5
    lease_seconds: float = 60
    retry_base_seconds: float = 30
    attach_report: bool = True


class EmailNotificationService:
    def __init__(
        self,
        repository=None,
        exporter=None,
        smtp_factory=None,
        settings=None,
        *,
        clock=time.time,
        smtp=None,
    ):
        self.repository = repository or EmailNotificationRepository()
        self.exporter = exporter
        self.smtp_factory = smtp_factory
        self.settings = settings
        self.clock = clock
        self.smtp = smtp or SMTPService()
        self.owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"
        self.task = None
        self.running = False
        self.accepting_deliveries = False
        self._inflight: set[asyncio.Task] = set()

    @staticmethod
    def now():
        return datetime.now(UTC)

    def record_terminal_intent(self, run_id, status, *, recipient=None, context=None):
        status = str(status).lower().strip()
        if status not in {"completed", "failed", "cancelled", "success"}:
            raise ValueError("notification intent requires terminal status")
        if status == "success":
            status = "completed"
        target = str(recipient or self.settings.recipient).strip()
        reason = (
            "email notifications disabled"
            if not self.settings.enabled
            else ("recipient not configured" if not target else None)
        )
        subject = (
            redact_text(f"Artemis task {status}: {run_id}")
            .replace("\r", " ")
            .replace("\n", " ")[:200]
        )
        return self.repository.enqueue_core(
            str(run_id),
            f"{self.settings.notification_type}:{status}",
            target,
            subject,
            {"status": status, "context": context or {}},
            max_attempts=self.settings.max_attempts,
            suppressed_reason=reason,
        )

    def reconcile_terminal_intents(self, rows):
        count = 0
        for row in rows:
            run_id = row.get("session_id") or row.get("run_id")
            status = str(row.get("status") or "").lower()
            if run_id and status in {"completed", "failed", "cancelled", "success"}:
                count += int(self.record_terminal_intent(run_id, status)[1])
        return count

    def process_one(self, worker_id=None):
        if self.settings is not None:
            claim = self.repository.claim_next(
                worker_id or "email-worker", lease_seconds=self.settings.lease_seconds
            )
            if not claim:
                return False
            try:
                message = EmailMessage()
                message["From"] = self.settings.sender
                message["To"] = claim.recipient
                message["Subject"] = claim.subject
                message.set_content(
                    f"Artemis task {claim.run_id} finished with status: {claim.payload.get('status', 'finished')}.\n"
                )
                if self.settings.attach_report:
                    message.add_attachment(
                        self.exporter.render(claim.run_id).decode("utf-8"),
                        subtype="plain",
                        charset="utf-8",
                        filename=f"task-report-{claim.run_id}.txt",
                    )
                result = self.smtp_factory().send_message(message)
                if isinstance(result, dict) and result:
                    raise RuntimeError("SMTP refused recipient")
            except smtplib.SMTPDataError as exc:
                self.repository.mark_failed_attempt(
                    claim,
                    redact_text(str(exc)),
                    retry_at=self.clock()
                    + self.settings.retry_base_seconds * (2 ** max(0, claim.attempts - 1)),
                )
            except (smtplib.SMTPServerDisconnected, TimeoutError, ConnectionError, OSError) as exc:
                self.repository.mark_delivery_unknown(claim, redact_text(str(exc)))
            except Exception as exc:
                self.repository.mark_failed_attempt(
                    claim,
                    redact_text(str(exc)),
                    retry_at=self.clock()
                    + self.settings.retry_base_seconds * (2 ** max(0, claim.attempts - 1)),
                )
            else:
                self.repository.mark_accepted(claim, message.get("Message-ID"))
            return True
        return self._process_runtime_one()

    def create_for_session(self, session_id, status):
        if status not in {"completed", "failed", "cancelled", "success"}:
            return None
        run = schedule_repo.get_run_by_session(session_id)
        if not run or not (run.get("task_snapshot") or {}).get("email_enabled"):
            return None
        config = create_email_settings_service().get()
        return self.repository.enqueue(run, config.version, self.now())[0]

    def attach_statuses(self, runs):
        found = self.repository.list_for_runs([run["id"] for run in runs])
        keys = (
            "id",
            "status",
            "attempt_count",
            "accepted_at",
            "safe_error_code",
            "safe_error_message",
            "updated_at",
        )
        for run in runs:
            item = found.get(run["id"])
            run["email_notification"] = {key: item.get(key) for key in keys} if item else None
        return runs

    def manual_retry(self, run_id):
        if not self.repository.manual_retry(run_id, self.now()):
            raise ValueError("Email is not in a retryable state")
        return {"status": "pending"}

    def report_for_run(self, run_id):
        item = self.repository.get_for_run(run_id)
        if not item or not item.get("report_path"):
            return None
        path = Path(item["report_path"]).resolve()
        root = (DB_PATH.parent / "email_reports").resolve()
        if path.is_file() and path.is_relative_to(root):
            return {"path": str(path), "filename": path.name}
        return None

    @property
    def inflight_count(self):
        return sum(not task.done() for task in self._inflight)

    @property
    def busy(self):
        return self.inflight_count > 0

    def status(self):
        return {
            "running": self.running,
            "accepting_deliveries": self.accepting_deliveries,
            "draining": not self.accepting_deliveries and (self.running or self.busy),
            "inflight_count": self.inflight_count,
            "busy": self.busy,
        }

    def begin_drain(self):
        """Prevent new SMTP claims while allowing the current delivery to finish."""
        self.accepting_deliveries = False
        return self.status()

    async def start(self):
        if self.task and not self.task.done():
            return
        self.running = True
        self.accepting_deliveries = True
        self.task = asyncio.create_task(self.loop())

    async def stop(self, timeout=5.0):
        """Stop claiming mail and wait a bounded time for SMTP threads to settle."""
        self.begin_drain()
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None

        pending = [task for task in self._inflight if not task.done()]
        if not pending:
            return True
        try:
            await asyncio.wait_for(
                asyncio.shield(asyncio.gather(*pending, return_exceptions=True)),
                timeout=max(0.0, timeout),
            )
        except TimeoutError:
            # asyncio.to_thread cannot safely cancel an SMTP call. Keep the task
            # tracked until the thread returns so delivery outcome is never
            # guessed merely because shutdown reached its bound.
            return False
        return True

    def _track_delivery(self):
        task = asyncio.create_task(asyncio.to_thread(self.process_one))
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)
        return task

    async def loop(self):
        while self.running:
            try:
                await asyncio.to_thread(self.reconcile)
                if not self.accepting_deliveries:
                    break
                # Shield the executor future from worker cancellation. SMTP is a
                # blocking operation and cancelling its asyncio waiter does not
                # stop the underlying thread.
                processed = await asyncio.shield(self._track_delivery())
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[EmailWorker] {redact_text(str(exc))}")
                processed = False
            await asyncio.sleep(0.5 if processed else 2.0)

    def reconcile(self):
        for run in schedule_repo.terminal_email_runs_without_notification():
            self.create_for_session(run["session_id"], run["status"])

    def _process_runtime_one(self):
        now = self.now()
        item = self.repository.claim(self.owner, now)
        if not item:
            return False
        run = schedule_repo.get_run(item["schedule_run_id"])
        settings_service = create_email_settings_service()
        settings = settings_service.get()
        if not settings.enabled:
            self.repository.finish(
                item["id"],
                self.owner,
                "suppressed",
                now,
                safe_error_code="global_disabled",
                safe_error_message="Email notifications are globally disabled",
            )
            return True
        if settings.version != item["smtp_config_version"]:
            self.repository.finish(
                item["id"],
                self.owner,
                "failed",
                now,
                safe_error_code="smtp_config_changed",
                safe_error_message="SMTP account changed after this task was queued; review before retrying.",
            )
            return True
        try:
            settings, password = settings_service.connection_parameters()
            snapshot = run["task_snapshot"]
            report = TaskLogExportService().render(run["session_id"])
            root = DB_PATH.parent / "email_reports"
            root.mkdir(parents=True, exist_ok=True)
            path = (root / safe_report_filename(run["session_id"])).resolve()
            if not path.is_relative_to(root.resolve()):
                raise RuntimeError("Unsafe report path")
            path.write_bytes(report)
            status = run["status"]
            finished = run.get("finished_at") or now.isoformat()
            subject = snapshot.get("email_subject") or "ARTEMIS — {schedule_name} — {status}"
            subject = subject.replace(
                "{schedule_name}", snapshot.get("schedule_name") or run["schedule_id"]
            )
            subject = subject.replace("{status}", status).replace("{finished_at}", finished)
            subject = redact_text(subject).replace("\r", " ").replace("\n", " ")[:500]
            summary = self._summary(report)
            greeting = (
                f"Hello {snapshot.get('recipient_name')},"
                if snapshot.get("recipient_name")
                else "Hello,"
            )
            body = (
                f"{greeting}\n\nSchedule: {snapshot.get('schedule_name') or run['schedule_id']}"
                f"\nResult: {status}\nFinished: {finished}\nSession ID: {run['session_id']}"
                f"\n\nSummary:\n{summary}\n\nThe attached text file contains the recorded execution steps.\n"
            )
            self.smtp.send(
                settings,
                password,
                item["recipient_email"],
                subject,
                body,
                report.decode("utf-8"),
                path.name,
                item["message_id"],
            )
            self.repository.finish(
                item["id"],
                self.owner,
                "accepted_by_smtp",
                now,
                rendered_subject=subject,
                rendered_body=body,
                report_path=str(path),
                report_sha256=hashlib.sha256(report).hexdigest(),
                report_size_bytes=len(report),
                report_complete=1,
                accepted_at=now.isoformat(),
            )
        except Exception as exc:
            attempts = item["attempt_count"]
            terminal = attempts >= 3
            retry_at = now + timedelta(seconds=30 if attempts == 1 else 120)
            self.repository.finish(
                item["id"],
                self.owner,
                "failed" if terminal else "retry",
                now,
                safe_error_code="smtp_or_report_error",
                safe_error_message=redact_text(str(exc))[:500],
                next_attempt_at=retry_at.isoformat(),
            )
        return True

    @staticmethod
    def _summary(report):
        text = report.decode("utf-8", "replace")
        if "\nFinal summary:\n" in text:
            return text.rsplit("\nFinal summary:\n", 1)[1].strip()[:4000]
        lines = [
            line
            for line in report.decode("utf-8", "replace").splitlines()
            if line.startswith("step: ")
        ]
        return (
            lines[-1][:4000]
            if lines
            else "No final summary was produced; see the attached recorded execution log."
        )


email_notification_service = EmailNotificationService()
