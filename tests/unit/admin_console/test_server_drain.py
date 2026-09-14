import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.admin_console.core.state import ServerState, state
from apps.admin_console.routers import system
from apps.admin_console.server import on_shutdown
from apps.admin_console.services.scheduler_service import SchedulerService
from apps.admin_console.services.task_admission_service import admit_tasks
from apps.admin_console.services.task_queue_service import TaskQueueService, task_queue_service


@pytest.fixture(autouse=True)
def restore_global_state():
    old = (state.is_draining, state.is_shutting_down, list(state.queue_items), state.worker_task)
    state.is_draining = False
    state.is_shutting_down = False
    state.queue_items = []
    state.worker_task = None
    yield
    state.is_draining, state.is_shutting_down, items, state.worker_task = old
    state.queue_items = items


@pytest.mark.asyncio
async def test_drain_waits_for_inflight_admission_commit_before_closing():
    runtime = ServerState()
    entered = asyncio.Event()
    release = asyncio.Event()

    class Queue:
        async def enqueue_tasks(self, goals, **kwargs):
            entered.set()
            await release.wait()
            runtime.queue_items.append({"session_id": "accepted", "status": "pending"})
            return {"status": "queued", "tasks": runtime.queue_items, "enqueued_count": 1}

    readiness = SimpleNamespace(run_device_submission_probe=AsyncMock(return_value=None))
    pool = SimpleNamespace(validate_explicit_serial_async=AsyncMock(return_value=None))
    sessions = SimpleNamespace(get_session_by_id=MagicMock(return_value=None))
    admission = asyncio.create_task(
        admit_tasks(
            ["accepted before drain"],
            device_serial="fake",
            runtime_state=runtime,
            queue=Queue(),
            readiness=readiness,
            pool=pool,
            sessions=sessions,
        )
    )
    await entered.wait()

    async def close_admission():
        async with runtime.admission_lock:
            runtime.is_draining = True

    drain = asyncio.create_task(close_admission())
    await asyncio.sleep(0)
    assert not drain.done()
    release.set()
    assert (await admission)["enqueued_count"] == 1
    await drain

    rejected = await admit_tasks(
        ["too late"],
        runtime_state=runtime,
        queue=Queue(),
        readiness=readiness,
        pool=pool,
        sessions=sessions,
    )
    assert rejected["status"] == "rejected"
    assert len(runtime.queue_items) == 1


def test_queue_dispatches_accepted_pending_item_during_drain(monkeypatch):
    state.is_draining = True
    item = {"session_id": "queued", "status": "pending", "device_serial": "fake"}
    state.queue_items = [item]
    spawned = []

    class FakeLoop:
        def create_task(self, coro):
            spawned.append(coro)
            coro.close()
            return MagicMock(add_done_callback=MagicMock())

    monkeypatch.setattr(TaskQueueService, "_concurrency_limit", classmethod(lambda cls: 2))
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: FakeLoop())
    monkeypatch.setattr(state, "prune_finished_runs", lambda: None)
    monkeypatch.setattr(type(state), "busy_device_ids", property(lambda self: set()))
    TaskQueueService._dispatch_pending_tasks()
    assert item["status"] == "running"
    assert len(spawned) == 1


@pytest.mark.asyncio
async def test_wait_drained_waits_for_queued_and_active_items():
    state.is_draining = True
    item = {"session_id": "accepted", "status": "pending"}
    state.queue_items = [item]
    waiter = asyncio.create_task(task_queue_service.wait_drained())
    await asyncio.sleep(0)
    assert not waiter.done()

    item["status"] = "running"
    state.wake_event.set()
    await asyncio.sleep(0)
    assert not waiter.done()

    state.queue_items.clear()
    state.wake_event.set()
    await asyncio.wait_for(waiter, timeout=1)


@pytest.mark.asyncio
async def test_begin_drain_waits_for_scheduler_claim_and_closes_admission(monkeypatch):
    claim_entered = asyncio.Event()
    release_claim = asyncio.Event()

    async def claim_in_progress():
        async with system.scheduler_service.claim_lock:
            claim_entered.set()
            await release_claim.wait()

    claim = asyncio.create_task(claim_in_progress())
    await claim_entered.wait()
    monkeypatch.setattr(
        "apps.admin_console.services.email_notification_service.email_notification_service.begin_drain",
        lambda: None,
    )
    monkeypatch.setattr(
        "apps.admin_console.services.email_notification_service.email_notification_service.status",
        lambda: {"inflight_count": 0, "accepting_deliveries": False},
    )
    drain = asyncio.create_task(system.begin_drain())
    await asyncio.sleep(0)
    assert not drain.done()
    assert state.is_draining is False

    release_claim.set()
    await claim
    result = await drain
    assert state.is_draining is True
    assert result["scheduler"]["claiming"] is False


@pytest.mark.asyncio
async def test_scheduler_stops_claiming_after_drain():
    repo = MagicMock()
    scheduler = SchedulerService(repo=repo, service=MagicMock())
    scheduler.running = True
    state.is_draining = True
    assert await scheduler.tick() == 0
    repo.acquire_lease.assert_not_called()
    status = scheduler.status()
    assert status["running"] is True
    assert status["claiming"] is False
    assert status["draining"] is True


@pytest.mark.asyncio
async def test_status_exposes_active_queued_paused_and_scheduler(monkeypatch):
    state.is_draining = True
    state.queue_items = [
        {"session_id": "active", "status": "running"},
        {"session_id": "queued", "status": "pending"},
    ]
    monkeypatch.setattr(type(state), "is_paused", property(lambda self: True))
    monkeypatch.setattr(system.scheduler_service, "status", lambda: {"running": True, "claiming": False})
    with patch(
        "apps.admin_console.services.email_notification_service.email_notification_service.status",
        return_value={"inflight_count": 0, "accepting_deliveries": False},
    ):
        result = await system.tray_status()
    assert result["active"] == 1
    assert result["queued"] == 1
    assert result["paused"] is True
    assert result["scheduler"]["claiming"] is False
    assert result["drained"] is False


@pytest.mark.asyncio
async def test_shutdown_after_drain_does_not_cancel_completed_work(monkeypatch):
    state.is_draining = True
    state.queue_items = []
    state.worker_task = None
    wait_drained = AsyncMock()
    update_status = MagicMock()
    monkeypatch.setattr(task_queue_service, "wait_drained", wait_drained)
    with (
        patch("apps.admin_console.server.scheduler_service.stop", new=AsyncMock()),
        patch("apps.admin_console.server.email_notification_service.stop", new=AsyncMock()),
        patch("apps.admin_console.server.ipc_service.stop_server", new=AsyncMock()),
        patch("apps.admin_console.server.shutdown_awake_service"),
        patch("apps.admin_console.server.clear_server_info"),
        patch("apps.admin_console.server.DeviceExecutionLock.cleanup_stale_locks"),
        patch("apps.admin_console.server.session_repo.update_session_status", update_status),
    ):
        await on_shutdown()
    wait_drained.assert_awaited_once()
    update_status.assert_not_called()
