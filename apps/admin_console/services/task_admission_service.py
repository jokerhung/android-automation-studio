from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from artemis.core.diagnostics import readiness_engine
from artemis.runtime import device_pool

try:
    from admin_console.core.state import state
    from admin_console.database.repositories.session_repository import session_repo
    from admin_console.services.task_queue_service import task_queue_service
except ImportError:
    from apps.admin_console.core.state import state
    from apps.admin_console.database.repositories.session_repository import session_repo
    from apps.admin_console.services.task_queue_service import task_queue_service


class AdmissionConflict(Exception):
    """A safe, expected readiness conflict suitable for an HTTP 409."""


async def admit_tasks(
    goals: list[str],
    *,
    profile: str = "flash",
    expected_output: str | None = None,
    enable_outputter: bool | None = None,
    verification_level: str | None = None,
    explorer_mode: str | None = None,
    locked_app_package: str | None = None,
    app_path: str | None = None,
    device_serial: str | None = None,
    ingress: str = "frontend",
    session_id: str | None = None,
    conversation_id: str | None = None,
    require_explicit_device: bool = False,
    runtime_state=state,
    sessions=session_repo,
    pool=device_pool,
    readiness=readiness_engine,
    queue=task_queue_service,
) -> dict[str, Any]:
    """Atomically admit work or reject it after drain admission closes."""
    async with runtime_state.admission_lock:
        if getattr(runtime_state, "is_draining", False) or runtime_state.is_shutting_down:
            return {
                "status": "rejected",
                "error": "ARTEMIS is draining for shutdown and is not accepting new tasks.",
                "tasks": [],
                "enqueued_count": 0,
                "total_queued": len(runtime_state.queue_tasks),
            }
        return await _admit_tasks_unlocked(
            goals,
            profile=profile,
            expected_output=expected_output,
            enable_outputter=enable_outputter,
            verification_level=verification_level,
            explorer_mode=explorer_mode,
            locked_app_package=locked_app_package,
            app_path=app_path,
            device_serial=device_serial,
            ingress=ingress,
            session_id=session_id,
            conversation_id=conversation_id,
            require_explicit_device=require_explicit_device,
            runtime_state=runtime_state,
            sessions=sessions,
            pool=pool,
            readiness=readiness,
            queue=queue,
        )


async def _admit_tasks_unlocked(
    goals: list[str],
    *,
    profile: str = "flash",
    expected_output: str | None = None,
    enable_outputter: bool | None = None,
    verification_level: str | None = None,
    explorer_mode: str | None = None,
    locked_app_package: str | None = None,
    app_path: str | None = None,
    device_serial: str | None = None,
    ingress: str = "frontend",
    session_id: str | None = None,
    conversation_id: str | None = None,
    require_explicit_device: bool = False,
    runtime_state=state,
    sessions=session_repo,
    pool=device_pool,
    readiness=readiness_engine,
    queue=task_queue_service,
) -> dict[str, Any]:
    """Apply the common idempotency/readiness policy and enqueue a task.

    Dependencies are injectable so routes retain their existing monkeypatch test
    seams while schedule dispatch uses the exact same admission implementation.
    """
    if not goals:
        raise ValueError("At least one goal is required")
    if require_explicit_device and not device_serial:
        return {
            "status": "rejected",
            "error": "A specific device_serial is required.",
            "tasks": [],
            "enqueued_count": 0,
            "total_queued": len(runtime_state.queue_tasks),
        }

    if session_id and len(goals) == 1:
        requested_sid = str(session_id)
        existing_item = next(
            (
                item
                for item in runtime_state.queue_items
                if isinstance(item, dict) and str(item.get("session_id")) == requested_sid
            ),
            None,
        )
        persisted_session = sessions.get_session_by_id(requested_sid)
        is_active = (
            str(runtime_state.active_session_id) == requested_sid
            or requested_sid in runtime_state.active_connections
        )
        if existing_item or persisted_session or is_active:
            payload = dict(existing_item or persisted_session or {})
            payload.setdefault("session_id", requested_sid)
            payload.setdefault("goal", goals[0])
            payload.setdefault("profile", profile)
            payload.setdefault("device_serial", device_serial)
            payload.setdefault("status", "running" if is_active else "queued")
            return {
                "status": payload["status"],
                "tasks": [payload],
                "enqueued_count": 0,
                "total_queued": len(runtime_state.queue_tasks),
            }

    if device_serial:
        try:
            rejection = await pool.validate_explicit_serial_async(device_serial)
        except Exception:
            rejection = None
        if rejection:
            return {
                "status": "rejected",
                "error": rejection,
                "tasks": [],
                "enqueued_count": 0,
                "total_queued": len(runtime_state.queue_tasks),
            }

    target_serial = device_serial
    probe = await readiness.run_device_submission_probe(target_serial=target_serial)
    if probe and probe.summary in {"Device Locked", "Lock State Unknown"}:
        locked_serial = probe.metadata.get("active_device", {}).get("serial") or target_serial or ""
        if probe.summary == "Device Locked":
            detail = f"Android device {locked_serial} is locked. Unlock it and enter the home screen before running a task.".replace(
                "  ", " "
            ).strip()
        else:
            detail = f"Android device {locked_serial} lock state could not be verified. Keep it unlocked on the home screen and try again.".replace(
                "  ", " "
            ).strip()
        raise AdmissionConflict(detail)
    if probe and probe.metadata.get("active_device") and not device_serial:
        target_serial = probe.metadata["active_device"].get("serial") or target_serial

    return await queue.enqueue_tasks(
        goals,
        profile=profile,
        expected_output=expected_output,
        enable_outputter=enable_outputter,
        verification_level=verification_level,
        explorer_mode=explorer_mode,
        locked_app_package=locked_app_package,
        app_path=app_path,
        device_serial=target_serial,
        ingress=ingress,
        session_id=session_id,
        conversation_id=conversation_id,
    )
