from __future__ import annotations
from datetime import UTC, datetime
from pydantic import ValidationError

try:
    from admin_console.database.repositories.schedule_repository import schedule_repo
    from admin_console.schemas.schedule_schema import ScheduleCreate, ScheduleRule
    from admin_console.services.schedule_recurrence import (
        next_occurrence,
        preview_occurrences,
        utc_now,
    )
    from admin_console.services.task_admission_service import AdmissionConflict, admit_tasks
except ImportError:
    from apps.admin_console.database.repositories.schedule_repository import schedule_repo
    from apps.admin_console.schemas.schedule_schema import ScheduleCreate, ScheduleRule
    from apps.admin_console.services.schedule_recurrence import (
        next_occurrence,
        preview_occurrences,
        utc_now,
    )
    from apps.admin_console.services.task_admission_service import AdmissionConflict, admit_tasks


class ScheduleService:
    def __init__(self, repo=schedule_repo, clock=utc_now):
        self.repo = repo
        self.clock = clock

    def preview(self, rule, count=5, anchor=None):
        return preview_occurrences(rule, after=self.clock(), count=count, anchor_at=anchor)

    def create(self, request):
        now = self.clock()
        data = request.model_dump()
        anchor = now if request.schedule_type == "interval" and request.enabled else None
        next_run = (
            next_occurrence(request, after=now, anchor_at=anchor) if request.enabled else None
        )
        return self.repo.create(data, now, next_run, anchor)

    def update(self, sid, request):
        current = self.repo.get(sid)
        if not current:
            return None, "not_found"
        changes = request.model_dump(exclude_unset=True)
        expected = changes.pop("expected_version")
        merged = {**current, **changes}
        rule = ScheduleRule.model_validate(merged)
        now = self.clock()
        enabled = bool(merged["enabled"])
        reset = (not current["enabled"] and enabled) or (
            current["schedule_type"] == "interval"
            and any(k in changes for k in ("interval_minutes", "enabled"))
        )
        anchor = (
            now
            if enabled and rule.schedule_type == "interval" and reset
            else (
                datetime.fromisoformat(current["interval_anchor_at"])
                if current.get("interval_anchor_at")
                else None
            )
        )
        next_run = next_occurrence(rule, after=now, anchor_at=anchor) if enabled else None
        return self.repo.update(sid, expected, changes, now, next_run, anchor)

    async def dispatch(self, run):
        snap = run["task_snapshot"]
        try:
            result = await admit_tasks(
                [snap["goal"]],
                profile=snap.get("profile") or "flash",
                expected_output=snap.get("expected_output"),
                enable_outputter=snap.get("enable_outputter"),
                verification_level=snap.get("verification_level"),
                explorer_mode=snap.get("explorer_mode"),
                locked_app_package=snap.get("locked_app_package"),
                app_path=snap.get("app_path"),
                device_serial=snap.get("device_serial"),
                ingress="schedule",
                session_id=run["session_id"],
                require_explicit_device=True,
            )
        except (AdmissionConflict, Exception) as exc:
            return self.repo.update_run(
                run["id"], "blocked", self.clock(), "enqueue_error", str(exc)[:500]
            )
        status = "queued" if result.get("enqueued_count") or result.get("tasks") else "blocked"
        error = result.get("error") if status == "blocked" else None
        return self.repo.update_run(
            run["id"],
            status,
            self.clock(),
            "device_unavailable" if error else None,
            str(error)[:500] if error else None,
        )


schedule_service = ScheduleService()
