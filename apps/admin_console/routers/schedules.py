from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

try:
    from admin_console.database.repositories.schedule_repository import schedule_repo
    from admin_console.schemas.schedule_schema import (
        ScheduleCreate,
        SchedulePatch,
        SchedulePreview,
        RunNowRequest,
        ScheduleRule,
    )
    from admin_console.services.schedule_recurrence import preview_occurrences, utc_now
    from admin_console.services.schedule_service import schedule_service
    from admin_console.services.scheduler_service import scheduler_service
    from admin_console.services.email_notification_service import email_notification_service
except ImportError:
    from apps.admin_console.database.repositories.schedule_repository import schedule_repo
    from apps.admin_console.schemas.schedule_schema import (
        ScheduleCreate,
        SchedulePatch,
        SchedulePreview,
        RunNowRequest,
        ScheduleRule,
    )
    from apps.admin_console.services.schedule_recurrence import preview_occurrences, utc_now
    from apps.admin_console.services.schedule_service import schedule_service
    from apps.admin_console.services.scheduler_service import scheduler_service
    from apps.admin_console.services.email_notification_service import email_notification_service
router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("/status")
def status():
    return scheduler_service.status()


@router.post("/preview")
def preview(req: SchedulePreview):
    after = utc_now()
    values = preview_occurrences(req, after=after, count=req.count, anchor_at=req.anchor_at)
    return {"occurrences": [v.isoformat() for v in values]}


@router.get("")
def list_schedules():
    return {"schedules": schedule_repo.list()}


@router.post("", status_code=201)
def create_schedule(req: ScheduleCreate):
    return schedule_service.create(req)


@router.get("/{schedule_id}")
def get_schedule(schedule_id: str):
    value = schedule_repo.get(schedule_id)
    if not value:
        raise HTTPException(404, "Schedule not found")
    return value


@router.patch("/{schedule_id}")
def patch_schedule(schedule_id: str, req: SchedulePatch):
    try:
        value, error = schedule_service.update(schedule_id, req)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    if error == "not_found":
        raise HTTPException(404, "Schedule not found")
    if error:
        raise HTTPException(409, "Schedule version conflict")
    return value


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str):
    if not schedule_repo.delete(schedule_id, utc_now()):
        raise HTTPException(404, "Schedule not found")


@router.post("/{schedule_id}/run-now")
async def run_now(schedule_id: str, req: RunNowRequest):
    schedule = schedule_repo.get(schedule_id)
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    existing = schedule_repo.find_manual_run(schedule_id, req.idempotency_key)
    if existing:
        return {"created": False, "run": existing}
    if schedule_repo.has_active_run(schedule_id):
        raise HTTPException(409, "Schedule already has an unfinished occurrence")
    run, created = schedule_repo.create_manual_run(schedule, req.idempotency_key, utc_now())
    if created:
        run = await schedule_service.dispatch(run)
    return {"created": created, "run": run}


@router.get("/{schedule_id}/runs")
def runs(schedule_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    if not schedule_repo.get(schedule_id):
        raise HTTPException(404, "Schedule not found")
    values, total = schedule_repo.runs(schedule_id, limit, offset)
    values = email_notification_service.attach_statuses(values)
    return {"runs": values, "total": total, "limit": limit, "offset": offset}


@router.post("/{schedule_id}/runs/{run_id}/email/retry")
def retry_email(schedule_id: str, run_id: str):
    run = schedule_repo.get_run(run_id)
    if not run or run["schedule_id"] != schedule_id:
        raise HTTPException(404, "Schedule run not found")
    try:
        return email_notification_service.manual_retry(run_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{schedule_id}/runs/{run_id}/email/report")
def email_report(schedule_id: str, run_id: str):
    run = schedule_repo.get_run(run_id)
    if not run or run["schedule_id"] != schedule_id:
        raise HTTPException(404, "Schedule run not found")
    report = email_notification_service.report_for_run(run_id)
    if not report:
        raise HTTPException(404, "Notification report not available")
    return FileResponse(report["path"], media_type="text/plain; charset=utf-8", filename=report["filename"])
