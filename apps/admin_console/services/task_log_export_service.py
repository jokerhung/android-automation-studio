"""Deterministic, redacted UTF-8 task report exporter."""

from __future__ import annotations
import json
from pathlib import Path
import re
from datetime import UTC, datetime
from typing import Any

try:
    from admin_console.database.connection import db_session
    from admin_console.services.notification_redaction import redact
except ImportError:
    from apps.admin_console.database.connection import db_session
    from apps.admin_console.services.notification_redaction import redact
MAX_REPORT_BYTES = 10 * 1024 * 1024
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class ReportExportError(RuntimeError):
    pass


def safe_report_filename(run_id: str) -> str:
    raw = str(run_id).strip()
    if not raw or raw in {".", ".."} or "/" in raw or "\\" in raw or "\x00" in raw:
        raise ReportExportError("unsafe run id")
    cleaned = _SAFE_FILENAME.sub("_", raw).strip("._")
    if not cleaned or cleaned != raw or len(cleaned.encode("utf-8")) > 180:
        raise ReportExportError("unsafe report filename")
    return f"task-report-{cleaned}.txt"


def _parse(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _text(value: Any) -> str:
    """Only human-readable scalars, never dump an object, XML or media blob."""
    value = _parse(value)
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if re.search(r"data:[^\s]+;base64,|<\?xml|<hierarchy\b", text, re.I):
        return ""
    return str(redact(text))


def _action_lines(value: Any) -> list[str]:
    action = _parse(value)
    if not isinstance(action, dict):
        return [_text(action)] if _text(action) else []
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    name = str(action.get("name") or action.get("action") or "Action")
    labels = {
        "click": "Tapping Element",
        "tap": "Tapping Element",
        "input_text": "Typing Text",
        "type_text": "Typing Text",
        "clear_text": "Clearing Text",
        "swipe": "Swiping Screen",
        "scroll": "Swiping Screen",
        "drag": "Dragging Screen",
        "press_key": "Pressing Hardware Key",
        "press_back": "Pressing Hardware Key",
        "press_home": "Pressing Hardware Key",
        "launch_app": "Launching Application",
        "open_app": "Launching Application",
        "stop_app": "Stopping Application",
        "close_app": "Stopping Application",
        "wait": "Waiting for Delay",
        "wait_for_delay": "Waiting for Delay",
        "delay": "Waiting for Delay",
        "long_press": "Long Pressing Element",
        "click_sequence": "Clicking Sequence",
        "report_task_status": "Task Result",
    }
    verb = args.get("action", "")
    label = labels.get(name, name.replace("_", " ").title())
    if name == "manage_app":
        label = {
            "launch": "Launching Application",
            "stop": "Stopping Application",
            "close": "Stopping Application",
        }.get(verb, "Managing Application")
    lines = [label]
    target = next(
        (
            action.get(k) or args.get(k)
            for k in ("target_text", "target_description", "app_name", "package_name", "element_id")
            if action.get(k) or args.get(k)
        ),
        None,
    )
    if _text(target):
        lines.append(f"Target: {_text(target)}")
    coords = (
        action.get("normalized_coordinates")
        or args.get("normalized_coordinates")
        or action.get("coordinates")
        or args.get("coordinates")
        or args.get("target")
    )
    if (
        isinstance(coords, (list, tuple))
        and len(coords) in (2, 4)
        and all(isinstance(n, (int, float)) for n in coords)
    ):
        lines.append("Coordinates: [" + ", ".join(str(n) for n in coords) + "]")
    for key, label in (
        ("time_in_ms", "Duration (ms)"),
        ("delay_ms", "Duration (ms)"),
        ("delay_seconds", "Duration (seconds)"),
        ("duration", "Duration"),
        ("key", "Key"),
        ("keycode", "Key"),
        ("direction", "Direction"),
    ):
        value = action.get(key) if action.get(key) is not None else args.get(key)
        if _text(value):
            lines.append(f"{label}: {_text(value)}")
    # Entered text can itself be a password without a field label. Never email it.
    if name in {"input_text", "type_text", "paste_text"}:
        lines.append("Input Text: [REDACTED]")
    if name == "report_task_status":
        if _text(args.get("status")):
            lines.append(f"Status: {_text(args['status'])}")
        if _text(args.get("explanation") or args.get("summary")):
            lines.append(f"Summary: {_text(args.get('explanation') or args.get('summary'))}")
    return lines


def _result_lines(value: Any) -> list[str]:
    result = _parse(value)
    if isinstance(result, dict):
        lines = []
        for key in ("message", "result", "error", "summary", "explanation"):
            if isinstance(result.get(key), dict):
                lines.extend(_result_lines(result[key]))
            elif _text(result.get(key)):
                lines.append(f"{'Error' if key == 'error' else 'Result'}: {_text(result[key])}")
        return lines
    return [f"Result: {_text(result)}"] if _text(result) else []


def _time(value: Any) -> str:
    try:
        return datetime.fromtimestamp(float(value), UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError, OverflowError, OSError):
        return "—"


class TaskLogExportService:
    def __init__(self, db_path: Path | str | None = None, *, max_bytes: int = MAX_REPORT_BYTES):
        self.db_path = Path(db_path) if db_path is not None else None
        self.max_bytes = max_bytes

    def render(self, run_id: str) -> bytes:
        """Render Workspace-style text, not database JSON or native thinking."""
        safe_report_filename(run_id)
        with db_session(self.db_path) as conn:
            session = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (str(run_id),)
            ).fetchone()
            if session is None:
                raise ReportExportError("session not found")
            steps = conn.execute(
                "SELECT * FROM steps WHERE session_id = ? ORDER BY step_number, timestamp, step_id",
                (str(run_id),),
            ).fetchall()
            traces = conn.execute(
                "SELECT * FROM traces WHERE session_id = ? ORDER BY timestamp, trace_id",
                (str(run_id),),
            ).fetchall()
        lines = [
            "ARTEMIS — TASK REPORT",
            "",
            f"Status: {_text(session['status'])}",
            f"Started: {_time(session['start_time'])}",
            f"Finished: {_time(session['end_time'])}",
            "",
        ]
        by_step: dict[str, list[dict]] = {}
        entered_texts: set[str] = set()
        for trace in traces:
            by_step.setdefault(str(trace["step_id"] or ""), []).append(dict(trace))
        for value in [step["action_taken"] for step in steps] + [
            {"name": trace["name"], "args": (_parse(trace["payload"]) or {}).get("args", {})}
            for trace in traces
            if trace["type"] == "action" and isinstance(_parse(trace["payload"]), dict)
        ]:
            action = _parse(value)
            if isinstance(action, dict) and (action.get("name") or action.get("action")) in {
                "input_text",
                "type_text",
                "paste_text",
            }:
                args = action.get("args") or {}
                for key in ("text", "input_text"):
                    if isinstance(args.get(key), str) and args[key]:
                        entered_texts.add(args[key])
        startup = []
        for trace in by_step.get("", []):
            payload = _parse(trace["payload"])
            if (
                trace["type"] == "startup_progress"
                and isinstance(payload, dict)
                and _text(payload.get("message"))
            ):
                startup.append(_text(payload["message"]))
        if startup:
            lines.extend(["Task startup", *[f"• {message}" for message in startup], ""])
        final_summary = ""
        for step in steps:
            lines.extend([f"Step {step['step_number']}", "─" * 48])
            # Despite its legacy name, operator_raw_thinking is the public text
            # stream shown as Work. Native/model thinking stays excluded.
            work = _text(step["operator_raw_thinking"])
            if work:
                lines.extend(["Work", work, ""])
            elif _text(step["summary"]):
                lines.extend([_text(step["summary"]), ""])
            action = _parse(step["action_taken"])
            step_traces = by_step.get(str(step["step_id"]), [])
            action_traces = [t for t in step_traces if t["type"] == "action"]
            if action_traces:
                # A burst may contain multiple actions; don't print only the last.
                for index, trace in enumerate(action_traces):
                    payload = _parse(trace["payload"])
                    if not isinstance(payload, dict):
                        continue
                    item = {"name": trace["name"], "args": payload.get("args", {})}
                    if (
                        index == len(action_traces) - 1
                        and isinstance(action, dict)
                        and (action.get("name") or action.get("action")) == trace["name"]
                    ):
                        # Preserve the same grounded target/normalized coordinates
                        # displayed in the Workspace action card.
                        item = {
                            **action,
                            "name": trace["name"],
                            "args": action.get("args") or item["args"],
                        }
                    lines.extend(_action_lines(item))
                    if trace["name"] not in {"input_text", "type_text", "paste_text"}:
                        lines.extend(_result_lines(payload.get("result")))
                    lines.append("")
            else:
                lines.extend(_action_lines(action))
                if not isinstance(action, dict) or action.get("action") not in {
                    "input_text",
                    "type_text",
                    "paste_text",
                }:
                    lines.extend(_result_lines(step["last_execution_result"]))
            for trace in step_traces:
                if trace["type"] not in {"tool", "tool_call", "tool_result"} and trace[
                    "name"
                ] not in {"llm_retry", "llm_fallback"}:
                    continue
                payload = _parse(trace["payload"])
                lines.extend(
                    [
                        str(trace["name"] or "Tool").replace("_", " ").title(),
                        *_result_lines(payload),
                    ]
                )
            if (
                isinstance(action, dict)
                and (action.get("action") or action.get("name")) == "report_task_status"
            ):
                args = action.get("args") or {}
                final_summary = _text(args.get("explanation") or args.get("summary"))
            lines.append("")
        if not steps:
            lines.append("No execution steps were recorded.")
        lines.extend(
            [
                "Final summary:",
                final_summary
                or "No final summary was produced; see the recorded execution steps above.",
            ]
        )
        text = "\n".join(lines) + "\n"
        for entered in sorted(entered_texts, key=len, reverse=True):
            text = text.replace(entered, "[REDACTED]")
        data = text.encode("utf-8", errors="strict")
        if len(data) > self.max_bytes:
            raise ReportExportError("report exceeds 10 MiB limit")
        return data

    def export(self, run_id: str, output_dir: Path | str) -> Path:
        root = Path(output_dir).resolve()
        if not root.exists() or not root.is_dir():
            raise ReportExportError("output directory does not exist")
        target = (root / safe_report_filename(run_id)).resolve()
        if target.parent != root:
            raise ReportExportError("unsafe report path")
        data = self.render(run_id)
        temp = target.with_suffix(target.suffix + ".tmp")
        try:
            temp.write_bytes(data)
            temp.replace(target)
        except OSError as exc:
            temp.unlink(missing_ok=True)
            raise ReportExportError("report write failed") from exc
        return target
