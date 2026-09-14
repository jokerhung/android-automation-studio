from __future__ import annotations
import asyncio
from datetime import datetime
import os
import socket
import uuid

try:
    from admin_console.database.repositories.schedule_repository import schedule_repo
    from admin_console.schemas.schedule_schema import ScheduleRule
    from admin_console.services.schedule_recurrence import next_occurrence, utc_now
    from admin_console.services.schedule_service import schedule_service
except ImportError:
    from apps.admin_console.database.repositories.schedule_repository import schedule_repo
    from apps.admin_console.schemas.schedule_schema import ScheduleRule
    from apps.admin_console.services.schedule_recurrence import next_occurrence, utc_now
    from apps.admin_console.services.schedule_service import schedule_service


class SchedulerService:
    def __init__(self, repo=schedule_repo, service=schedule_service, clock=utc_now):
        self.repo = repo
        self.service = service
        self.clock = clock
        self.owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"
        self.task = None
        self.last_heartbeat = None
        self.generation = None
        self.running = False

    async def start(self):
        if self.task and not self.task.done():
            return
        self.running = True
        self.task = asyncio.create_task(self.loop())

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
        if self.task:
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.repo.release_lease(self.owner)

    async def tick(self):
        now = self.clock()
        gen = self.repo.acquire_lease(self.owner, now)
        if gen is None:
            return 0
        self.generation = gen
        self.last_heartbeat = now
        count = 0
        # Durable outbox recovery retries the same deterministic session ID.
        for pending in self.repo.pending_runs():
            await self.service.dispatch(pending)
            count += 1
        for s in self.repo.due_schedules(now):
            due = datetime.fromisoformat(s["next_run_at"])
            rule = ScheduleRule.model_validate(s)
            anchor = (
                datetime.fromisoformat(s["interval_anchor_at"])
                if s.get("interval_anchor_at")
                else None
            )
            next_run = next_occurrence(rule, after=now, anchor_at=anchor)
            run = self.repo.claim_occurrence(s, due, next_run, now, self.owner, gen)
            if run and run["status"] == "dispatch_pending":
                await self.service.dispatch(run)
                count += 1
        return count

    async def loop(self):
        while self.running:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(1)

    def status(self):
        return {
            "running": self.running,
            "leader": self.generation is not None,
            "owner": self.owner,
            "generation": self.generation,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "timezone_support": True,
        }


scheduler_service = SchedulerService()
