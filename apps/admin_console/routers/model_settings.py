import asyncio
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import psutil
from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from artemis.config.paths import ROOT_DIR
from artemis.runtime import settings_restart
from artemis.runtime.daemon_client import daemon_log_path
from artemis.utils.subprocess_utils import hidden_process_kwargs

try:
    from admin_console.services.model_settings_service import (
        ModelSettingsService,
        ModelSettingsUpdate,
    )
    from admin_console.routers.system import (
        _require_server_bound_request,
        state,
        scheduler_service,
    )
    from admin_console.services.email_notification_service import email_notification_service
except ImportError:
    from apps.admin_console.services.model_settings_service import (
        ModelSettingsService,
        ModelSettingsUpdate,
    )
    from apps.admin_console.routers.system import (
        _require_server_bound_request,
        state,
        scheduler_service,
    )
    from apps.admin_console.services.email_notification_service import email_notification_service

router = APIRouter(prefix="/api/settings/model", tags=["settings"])


def authorize(request):
    _require_server_bound_request(request, "Model settings are local-only.")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc.lower() != request.headers.get("host", "").lower():
        raise HTTPException(403, "Use the same-origin Artemis console.")


@router.get("")
def get_model_settings(request: Request):
    authorize(request)
    try:
        return ModelSettingsService().get()
    except (ValueError, OSError):
        raise HTTPException(500, "Unable to read model configuration files.") from None


def launch_restart(port, host, drop_env):
    env = os.environ.copy()
    for key in drop_env:
        env.pop(key, None)
    process = psutil.Process()
    cmd = [
        sys.executable,
        str(Path(settings_restart.__file__).resolve()),
        "--pid",
        str(process.pid),
        "--created",
        str(process.create_time()),
        "--port",
        str(port),
        "--host",
        host,
        "--cwd",
        str(ROOT_DIR),
    ]
    options = hidden_process_kwargs()
    if sys.platform == "win32":
        options["creationflags"] |= (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        options["start_new_session"] = True
    log = daemon_log_path(port)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as stream:
        subprocess.Popen(
            cmd,
            cwd=ROOT_DIR,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            **options,
        )


@router.put("")
async def save_model_settings(request: Request):
    authorize(request)
    # Never let FastAPI echo a submitted API key in a validation error response.
    try:
        payload = ModelSettingsUpdate.model_validate(await request.json())
    except (ValidationError, ValueError):
        raise HTTPException(
            422, "Check provider, model names, URLs and restart confirmation."
        ) from None
    server = getattr(request.app.state, "uvicorn_server", None)
    if server is None:
        raise HTTPException(503, "Restart controller unavailable; no files were changed.")
    async with scheduler_service.claim_lock:
        async with state.admission_lock:
            state.prune_finished_runs()
            if (
                state.is_draining
                or state.is_shutting_down
                or state.active_task_count
                or state.queue_tasks
                or state.is_paused
                or email_notification_service.busy
            ):
                raise HTTPException(
                    409,
                    "Tasks, queued work, email delivery or shutdown is active. Wait until idle and save again.",
                )
            state.is_draining = True
            accepting = email_notification_service.accepting_deliveries
            email_notification_service.begin_drain()
            try:
                dropped = ModelSettingsService().save(payload)
            except (OSError, ValueError) as exc:
                state.is_draining = False
                email_notification_service.accepting_deliveries = accepting
                raise HTTPException(
                    409 if isinstance(exc, FileExistsError) else 500,
                    "Configuration changed or could not be saved. Reload and retry.",
                ) from None
            try:
                launch_restart(state.port, state.host, dropped)
            except OSError:
                state.is_draining = False
                email_notification_service.accepting_deliveries = accepting
                return {
                    "status": "saved_restart_failed",
                    "message": "Files saved, but restart failed. Restart ARTEMIS manually to apply.",
                }

    schedule_shutdown(server)
    return {
        "status": "restarting",
        "previous_pid": os.getpid(),
        "message": "Saved. ARTEMIS will restart in 2 seconds.",
    }


def schedule_shutdown(server):
    async def shutdown():
        await asyncio.sleep(2)
        state.is_shutting_down = True
        state.shutdown_event.set()
        server.should_exit = True

    asyncio.create_task(shutdown())
