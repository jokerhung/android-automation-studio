import json
import sqlite3

from admin_console.services.task_log_export_service import TaskLogExportService
from admin_console.services.email_notification_service import EmailNotificationService
from admin_console.services.notification_redaction import redact_text
from tests.unit.admin_console.test_email_notification_core import schema


def test_workspace_text_actions_and_final_summary(tmp_path):
    db = tmp_path / "report.db"
    schema(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO sessions(session_id,status,start_time,end_time) VALUES(?,?,?,?)",
            ("readable", "completed", 1, 20),
        )
        for number, name, args, work in [
            (
                1,
                "manage_app",
                {"action": "launch", "app_name": "com.example"},
                "Tôi sẽ mở ứng dụng.",
            ),
            (
                2,
                "click",
                {"target_description": "Chấm công", "coordinates": [126, 380]},
                "Ứng dụng đã vào trang chủ.",
            ),
            (
                3,
                "report_task_status",
                {"status": "completed", "explanation": "Đã hoàn thành tác vụ."},
                "Tôi đã kiểm tra kết quả.",
            ),
        ]:
            conn.execute(
                "INSERT INTO steps(step_id,session_id,step_number,timestamp,action_taken,operator_raw_thinking,operator_native_thinking,extra_metadata) VALUES(?,?,?,?,?,?,?,?)",
                (
                    str(number),
                    "readable",
                    number,
                    number,
                    json.dumps({"action": name, "args": args}),
                    work,
                    "PRIVATE THINKING",
                    json.dumps({"pre_image_dhash": "technical-hash"}),
                ),
            )
    report = TaskLogExportService(db).render("readable").decode()
    assert "Work\nTôi sẽ mở ứng dụng." in report
    assert "Launching Application\nTarget: com.example" in report
    assert "Tapping Element\nTarget: Chấm công\nCoordinates: [126, 380]" in report
    assert report.index("Step 1") < report.index("Step 2") < report.index("Step 3")
    assert "PRIVATE THINKING" not in report and "technical-hash" not in report
    assert '"args"' not in report and "operator_raw_thinking" not in report
    assert EmailNotificationService._summary(report.encode()) == "Đã hoàn thành tác vụ."


def test_action_burst_keeps_all_actions_and_masks_entered_text(tmp_path):
    db = tmp_path / "burst.db"
    schema(db)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO sessions(session_id,status) VALUES('burst','failed')")
        conn.execute(
            "INSERT INTO steps(step_id,session_id,step_number,operator_raw_thinking,action_taken) VALUES(?,?,?,?,?)",
            (
                "s",
                "burst",
                1,
                "Entered private-value",
                json.dumps({"action": "input_text", "args": {"text": "private-value"}}),
            ),
        )
        for i, name, args in [
            (1, "click", {"target_description": "Login"}),
            (2, "input_text", {"text": "private-value"}),
        ]:
            conn.execute(
                "INSERT INTO traces(trace_id,session_id,step_id,type,name,timestamp,payload) VALUES(?,?,?,?,?,?,?)",
                (
                    str(i),
                    "burst",
                    "s",
                    "action",
                    name,
                    i,
                    json.dumps({"args": args, "result": "echo private-value"}),
                ),
            )
    report = TaskLogExportService(db).render("burst").decode()
    assert report.count("Tapping Element") == 1
    assert report.count("Typing Text") == 1
    assert "private-value" not in report
    assert "[REDACTED]" in report


def test_quoted_passwords_are_masked():
    assert "p@ss word" not in redact_text('password "p@ss word"')
    assert "p@ss word" not in redact_text('mật khẩu: "p@ss word"')
