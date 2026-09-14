import asyncio
import json
import sqlite3
import smtplib
import threading

import pytest

from admin_console.database.repositories.email_notification_repository import EmailNotificationRepository
from admin_console.services.email_notification_service import EmailNotificationService, EmailNotificationSettings
from admin_console.services.notification_redaction import REDACTED, redact, redact_text
from admin_console.services.task_log_export_service import ReportExportError, TaskLogExportService, safe_report_filename


def schema(db):
    with sqlite3.connect(db) as conn:
        conn.executescript("""
        CREATE TABLE sessions(session_id TEXT PRIMARY KEY, initial_goal TEXT, start_time REAL, end_time REAL, status TEXT, device_info TEXT, video_filepath TEXT, pid INTEGER);
        CREATE TABLE steps(step_id TEXT PRIMARY KEY, session_id TEXT, step_number INTEGER, timestamp REAL, pre_image_name TEXT, post_image_name TEXT, summary TEXT, action_taken TEXT, operator_raw_thinking TEXT, operator_native_thinking TEXT, last_execution_result TEXT, extra_metadata TEXT);
        CREATE TABLE traces(trace_id TEXT PRIMARY KEY, session_id TEXT, step_id TEXT, parent_trace_id TEXT, type TEXT, name TEXT, timestamp REAL, duration REAL, status TEXT, payload TEXT);
        """)
        conn.executescript(EmailNotificationRepository.SCHEMA_SQL)


def seed(db, run_id="run-1"):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?)", (run_id, "use token=topsecret", 1, 2, "completed", json.dumps({"api_key":"key-secret","device":"pixel"}), "/private/image.mp4", 9))
        conn.execute("INSERT INTO steps VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", ("s1",run_id,1,1.5,"pre.png","post.png","café password=hunter2","tap","I opened café. password=hunter2","NATIVE SECRET","ok",json.dumps({"authorization":"Bearer abcdefghijk","safe":"yes"})))
        conn.execute("INSERT INTO traces VALUES(?,?,?,?,?,?,?,?,?,?)", ("t1",run_id,"s1",None,"tool","result",1.6,.1,"success",json.dumps({"cookie":"session-value","result":"done"})))
        conn.execute("INSERT INTO traces VALUES(?,?,?,?,?,?,?,?,?,?)", ("t2",run_id,"s1",None,"reasoning","brain",1.7,.1,"success","never export this"))


def test_outbox_is_unique_claimed_and_manual_retry(tmp_path):
    db=tmp_path/"n.db"; schema(db)
    now=[100.0]; repo=EmailNotificationRepository(db, clock=lambda: now[0])
    first, inserted=repo.enqueue("run","terminal","a@example.com","done",max_attempts=1)
    second, inserted2=repo.enqueue("run","terminal","b@example.com","duplicate")
    assert (first,True)==(first,inserted) and second==first and inserted2 is False
    claim=repo.claim_next("w1",lease_seconds=10)
    assert claim and claim.attempts==1 and repo.claim_next("w2") is None
    assert repo.mark_failed_attempt(claim,"bad",retry_at=101)
    assert repo.get(first)["status"]=="failed"
    assert repo.manual_retry(first)
    assert repo.get(first)["status"]=="pending" and repo.get(first)["attempts"]==0


def test_expired_lease_is_reclaimed_and_stale_owner_cannot_finish(tmp_path):
    db=tmp_path/"n.db"; schema(db); now=[10.0]
    repo=EmailNotificationRepository(db,clock=lambda:now[0]); ident,_=repo.enqueue("r","t","a@b.test","x")
    old=repo.claim_next("old",lease_seconds=2); now[0]=13
    new=repo.claim_next("new",lease_seconds=2)
    assert new and new.id==ident and new.attempts==2
    assert repo.mark_accepted(old) is False
    assert repo.mark_accepted(new) is True and repo.get(ident)["status"]=="accepted"


def test_redaction_structured_json_and_free_text():
    value={"api_key":"secret", "nested":{"password":"hunter2"}, "text":"Authorization: Bearer abcdefghijk email me@example.com", "json":'{"refresh_token":"xyz","ok":1}'}
    result=redact(value); rendered=json.dumps(result)
    assert "hunter2" not in rendered and "abcdefghijk" not in rendered and "me@example.com" not in rendered and "xyz" not in rendered
    assert result["api_key"]==REDACTED and REDACTED in redact_text("password=hunter2")


def test_export_is_deterministic_utf8_redacted_and_omits_reasoning_images(tmp_path):
    db=tmp_path/"n.db"; schema(db); seed(db)
    export=TaskLogExportService(db)
    one=export.render("run-1"); two=export.render("run-1")
    assert one==two and "café" in one.decode("utf-8")
    text=one.decode("utf-8")
    for secret in ("topsecret","hunter2","key-secret","session-value","RAW SECRET","NATIVE SECRET","never export this","pre.png","post.png"):
        assert secret not in text
    assert "done" in text and REDACTED in text
    assert 'Work\nI opened café.' in text
    assert 'step: {' not in text and 'trace: {' not in text


def test_export_rejects_unsafe_filename_and_size(tmp_path):
    db=tmp_path/"n.db"; schema(db); seed(db)
    with pytest.raises(ReportExportError): safe_report_filename("../escape")
    with pytest.raises(ReportExportError): TaskLogExportService(db,max_bytes=20).render("run-1")


class FakeSMTP:
    def __init__(self, outcome=None): self.outcome=outcome; self.messages=[]
    def send_message(self,message):
        self.messages.append(message)
        if isinstance(self.outcome,Exception): raise self.outcome
        return self.outcome


def service(db,smtp,now,max_attempts=2,enabled=True):
    return EmailNotificationService(EmailNotificationRepository(db,clock=lambda:now[0]),TaskLogExportService(db),lambda:smtp,
        EmailNotificationSettings(enabled=enabled,sender="sender@example.test",recipient="to@example.test",max_attempts=max_attempts,retry_base_seconds=5),clock=lambda:now[0])


def test_worker_sends_via_injected_smtp_and_marks_accepted(tmp_path):
    db=tmp_path/"n.db"; schema(db); seed(db); now=[50.0]; smtp=FakeSMTP(); svc=service(db,smtp,now)
    ident,created=svc.record_terminal_intent("run-1","success")
    assert created and svc.process_one("worker") and len(smtp.messages)==1
    assert svc.repository.get(ident)["status"]=="accepted"
    attachment=list(smtp.messages[0].iter_attachments())[0]
    assert attachment.get_filename()=="task-report-run-1.txt" and "café" in attachment.get_content()


def test_worker_bounds_retry_and_marks_unknown_without_resend(tmp_path):
    db=tmp_path/"n.db"; schema(db); seed(db); now=[50.0]
    smtp=FakeSMTP(smtplib.SMTPDataError(451,b"try later")); svc=service(db,smtp,now,max_attempts=1)
    ident,_=svc.record_terminal_intent("run-1","completed"); svc.process_one("w")
    assert svc.repository.get(ident)["status"]=="failed" and svc.process_one("w") is False
    ident2,_=svc.record_terminal_intent("run-1","failed",context={"password":"hidden"})
    smtp.outcome=TimeoutError("ack lost"); svc.process_one("w")
    assert svc.repository.get(ident2)["status"]=="delivery_unknown" and svc.process_one("w") is False


class BlockingSMTP(FakeSMTP):
    def __init__(self, outcome=None):
        super().__init__(outcome)
        self.entered = threading.Event()
        self.release = threading.Event()

    def send_message(self, message):
        self.messages.append(message)
        self.entered.set()
        assert self.release.wait(2), "test did not release fake SMTP"
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.mark.asyncio
async def test_drain_stops_new_claims_and_stop_waits_for_inflight(tmp_path):
    db = tmp_path / "n.db"
    schema(db)
    seed(db)
    now = [50.0]
    smtp = BlockingSMTP()
    svc = service(db, smtp, now)
    svc.reconcile = lambda: None
    first, _ = svc.record_terminal_intent("run-1", "completed")
    second, _ = svc.record_terminal_intent("run-1", "failed")

    await svc.start()
    assert await asyncio.to_thread(smtp.entered.wait, 1)
    assert svc.status()["inflight_count"] == 1
    svc.begin_drain()
    assert svc.status()["accepting_deliveries"] is False

    smtp.release.set()
    assert await svc.stop(timeout=1) is True
    assert svc.repository.get(first)["status"] == "accepted"
    assert svc.repository.get(second)["status"] == "pending"
    assert svc.status()["inflight_count"] == 0


@pytest.mark.asyncio
async def test_stop_timeout_keeps_smtp_tracked_and_preserves_unknown_result(tmp_path):
    db = tmp_path / "n.db"
    schema(db)
    seed(db)
    now = [50.0]
    smtp = BlockingSMTP(TimeoutError("ack lost"))
    svc = service(db, smtp, now)
    svc.reconcile = lambda: None
    ident, _ = svc.record_terminal_intent("run-1", "completed")

    await svc.start()
    assert await asyncio.to_thread(smtp.entered.wait, 1)
    assert await svc.stop(timeout=0.01) is False
    assert svc.status()["inflight_count"] == 1
    assert svc.status()["draining"] is True
    assert svc.status()["accepting_deliveries"] is False
    # A shutdown timeout does not invent a send result or release the claim.
    assert svc.repository.get(ident)["status"] == "sending"

    smtp.release.set()
    for _ in range(100):
        if not svc.busy:
            break
        await asyncio.sleep(0.01)
    assert svc.repository.get(ident)["status"] == "delivery_unknown"
    assert svc.busy is False


def test_suppression_and_reconcile_hooks_are_idempotent(tmp_path):
    db=tmp_path/"n.db"; schema(db); seed(db); now=[50.0]; smtp=FakeSMTP(); svc=service(db,smtp,now,enabled=False)
    assert svc.reconcile_terminal_intents([{"session_id":"run-1","status":"completed"},{"session_id":"x","status":"running"}])==1
    assert svc.reconcile_terminal_intents([{"session_id":"run-1","status":"completed"}])==0
    row=svc.repository.get(1); assert row["status"]=="suppressed" and svc.process_one("w") is False and smtp.messages==[]
