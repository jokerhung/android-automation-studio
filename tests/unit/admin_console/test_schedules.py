from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from artemis.data_engine.storage import StorageManager
from apps.admin_console.database.repositories.schedule_repository import ScheduleRepository
from apps.admin_console.schemas.schedule_schema import ScheduleCreate, ScheduleRule
from apps.admin_console.services.schedule_recurrence import next_occurrence, preview_occurrences
from apps.admin_console.services.schedule_service import ScheduleService


def test_daily_dst_skips_nonexistent_and_uses_first_fold():
    spring = ScheduleRule(
        schedule_type="daily", time_of_day="02:30:00", timezone="America/New_York"
    )
    result = next_occurrence(spring, after=datetime(2026, 3, 8, 5, 0, tzinfo=UTC))
    assert result == datetime(2026, 3, 9, 6, 30, tzinfo=UTC)
    fall = ScheduleRule(schedule_type="daily", time_of_day="01:30:00", timezone="America/New_York")
    assert next_occurrence(fall, after=datetime(2026, 11, 1, 4, 0, tzinfo=UTC)) == datetime(
        2026, 11, 1, 5, 30, tzinfo=UTC
    )


def test_interval_anchor_does_not_drift():
    rule = ScheduleRule(schedule_type="interval", interval_minutes=15, timezone="UTC")
    anchor = datetime(2026, 1, 1, 10, 0, 20, tzinfo=UTC)
    assert next_occurrence(
        rule, after=datetime(2026, 1, 1, 10, 31, tzinfo=UTC), anchor_at=anchor
    ) == datetime(2026, 1, 1, 10, 45, 20, tzinfo=UTC)


def test_repository_crud_idempotency_and_lease(tmp_path):
    db = tmp_path / "test.db"
    StorageManager(db, tmp_path)
    repo = ScheduleRepository(db)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    data = ScheduleCreate(
        name="Daily",
        goal="Do safe thing",
        profile="flash",
        device_serial="fake",
        schedule_type="daily",
        time_of_day="12:00:00",
        timezone="UTC",
    ).model_dump()
    item = repo.create(data, now, datetime(2026, 1, 1, 12, tzinfo=UTC), None)
    assert repo.get(item["id"])["version"] == 1
    run, created = repo.create_manual_run(item, "same", now)
    again, created2 = repo.create_manual_run(item, "same", now)
    assert created and not created2 and run["session_id"] == again["session_id"]
    assert repo.acquire_lease("one", now) == 1
    assert repo.acquire_lease("two", now) is None


def test_schedule_api_crud_preview_and_run_now(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    StorageManager(db, tmp_path)
    repo = ScheduleRepository(db)
    import apps.admin_console.routers.schedules as routes

    service = ScheduleService(repo=repo, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    service.dispatch = AsyncMock(
        side_effect=lambda run: repo.update_run(
            run["id"], "queued", datetime(2026, 1, 1, tzinfo=UTC)
        )
    )
    monkeypatch.setattr(routes, "schedule_repo", repo)
    monkeypatch.setattr(routes, "schedule_service", service)
    monkeypatch.setattr(
        routes.scheduler_service, "status", lambda: {"running": True, "timezone_support": True}
    )
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)
    preview = client.post(
        "/api/schedules/preview",
        json={
            "schedule_type": "weekly",
            "time_of_day": "09:00:00",
            "weekdays": [1, 3],
            "timezone": "UTC",
        },
    )
    assert preview.status_code == 200 and len(preview.json()["occurrences"]) == 5
    payload = {
        "name": "Test",
        "goal": "No device action in test",
        "profile": "flash",
        "device_serial": "fake",
        "schedule_type": "interval",
        "interval_minutes": 15,
        "timezone": "UTC",
        "enabled": True,
    }
    created = client.post("/api/schedules", json=payload)
    assert created.status_code == 201
    sid = created.json()["id"]
    assert client.get("/api/schedules").json()["schedules"][0]["goal"] == "No device action in test"
    first = client.post(f"/api/schedules/{sid}/run-now", json={"idempotency_key": "click"})
    second = client.post(f"/api/schedules/{sid}/run-now", json={"idempotency_key": "click"})
    assert first.status_code == 200
    assert second.status_code == 200 and second.json()["created"] is False
    assert client.get(f"/api/schedules/{sid}/runs").json()["total"] == 1

def test_atomic_claim_advances_once_and_fences_other_owner(tmp_path):
    db = tmp_path / "claim.db"
    StorageManager(db, tmp_path)
    repo = ScheduleRepository(db)
    now = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
    data = ScheduleCreate(name="Claim", goal="Safe", profile="flash", device_serial="fake", schedule_type="interval", interval_minutes=15, timezone="UTC").model_dump()
    schedule = repo.create(data, datetime(2026, 1, 1, tzinfo=UTC), now, datetime(2026, 1, 1, tzinfo=UTC))
    generation = repo.acquire_lease("leader", now)
    next_run = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)
    run = repo.claim_occurrence(schedule, now, next_run, now, "leader", generation)
    assert run is not None and run["status"] == "dispatch_pending"
    assert repo.get(schedule["id"])["next_run_at"] == next_run.isoformat()
    assert repo.claim_occurrence(schedule, now, next_run, now, "other", generation) is None
    assert repo.runs(schedule["id"])[1] == 1


@pytest.mark.asyncio
async def test_schedule_dispatch_uses_shared_admission(monkeypatch, tmp_path):
    db = tmp_path / "admission.db"
    StorageManager(db, tmp_path)
    repo = ScheduleRepository(db)
    service = ScheduleService(repo=repo, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    import apps.admin_console.services.schedule_service as module
    admitted = AsyncMock(return_value={"status": "queued", "tasks": [{"session_id": "sid"}], "enqueued_count": 1})
    monkeypatch.setattr(module, "admit_tasks", admitted)
    run = {"id": "missing", "session_id": "sid", "task_snapshot": {"goal": "Safe", "profile": "flash", "device_serial": "fake"}}
    repo.update_run = lambda *args, **kwargs: {"status": args[1]}
    result = await service.dispatch(run)
    assert result["status"] == "queued"
    admitted.assert_awaited_once()
    assert admitted.await_args.kwargs["ingress"] == "schedule"
    assert admitted.await_args.kwargs["require_explicit_device"] is True

