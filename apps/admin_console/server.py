# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Artemis Admin & Trace Console Server

Modular entrypoint for full trace inspection, step replay, and task execution management.
"""

import argparse
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import secrets
import signal
import sys
from types import FrameType

# Bootstrap sys.path to allow running from any CWD
_current_p = Path(__file__).resolve().parent
while _current_p != _current_p.parent:
    if (_current_p / "pyproject.toml").exists() or (_current_p / "artemis").is_dir():
        _workspace_root = _current_p
        break
    _current_p = _current_p.parent
else:
    _workspace_root = Path(__file__).resolve().parent.parent.parent

_apps_dir = _workspace_root / "apps"
_admin_console_dir = _apps_dir / "admin_console"
_cloud_service_dir = _apps_dir / "cloud_service"

for _p in (str(_workspace_root), str(_apps_dir), str(_admin_console_dir), str(_cloud_service_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
import uvicorn

from artemis.runtime import (
    DeviceExecutionLock,
    clear_server_info,
    device_pool,
    shutdown_awake_service,
    start_awake_service,
    write_server_info,
)

from artemis.config import (
    DB_PATH,
    IMAGES_DIR,
    REPLAY_BASE_DIR,
    TEST_DATA_DIR,
    TEST_OUTPUTS_DIR,
    TRACES_PATH,
    WORKSPACE_ROOT,
    init_ls_address,
)
from artemis.resources import get_bundled_showcase_dist

try:
    from admin_console.core.security import SameOriginBoundaryMiddleware
    from admin_console.core.state import ServerState, state
    from admin_console.database.connection import db_session, get_db
    from admin_console.database.repositories.session_repository import session_repo
    from admin_console.database.repositories.step_repository import step_repo
    from admin_console.database.repositories.trace_repository import trace_repo
    from admin_console.routers import (
        email_settings,
        media,
        replay,
        schedules,
        sessions,
        steps,
        stream,
        system,
        tasks,
    )
    from admin_console.routers.replay import replay_manager
    from admin_console.services.email_notification_service import email_notification_service
    from admin_console.services.ipc_service import ipc_service
    from admin_console.services.media_service import media_service
    from admin_console.services.model_service import model_service
    from admin_console.services.task_queue_service import task_queue_service
    from admin_console.services.scheduler_service import scheduler_service
except ImportError:
    from apps.admin_console.core.security import SameOriginBoundaryMiddleware
    from apps.admin_console.core.state import state
    from apps.admin_console.database.repositories.session_repository import session_repo
    from apps.admin_console.routers import (
        email_settings,
        media,
        replay,
        schedules,
        sessions,
        steps,
        stream,
        system,
        tasks,
    )
    from apps.admin_console.routers.replay import replay_manager
    from apps.admin_console.services.email_notification_service import email_notification_service
    from apps.admin_console.services.ipc_service import ipc_service
    from apps.admin_console.services.model_service import model_service
    from apps.admin_console.services.task_queue_service import task_queue_service
    from apps.admin_console.services.scheduler_service import scheduler_service

# Initialize language server synchronization address
init_ls_address()


@asynccontextmanager
async def _lifespan(_app: "FastAPI"):
    """Start server resources and release them on shutdown."""
    await on_startup()
    try:
        yield
    finally:
        await on_shutdown()


# Initialize FastAPI application
app = FastAPI(title="Artemis Admin & Trace Console", lifespan=_lifespan)
LIFECYCLE_TOKEN = os.environ.get("ARTEMIS_LIFECYCLE_TOKEN") or secrets.token_urlsafe(32)
app.state.lifecycle_token = LIFECYCLE_TOKEN

# The console UI is served same-origin from this process, so no CORS grants
# exist at all; the boundary middleware rejects cross-origin browser traffic
# and unrecognized Host headers (DNS rebinding) instead.
app.add_middleware(SameOriginBoundaryMiddleware)


async def on_startup():
    """Startup lifecycle hooks."""
    state.is_shutting_down = False
    state.is_draining = False
    state.shutdown_event.clear()
    write_server_info(
        port=getattr(state, "port", 8000),
        host=getattr(state, "host", "127.0.0.1"),
        lifecycle_token=LIFECYCLE_TOKEN,
    )
    await asyncio.to_thread(start_awake_service)
    cleaned_device_locks = DeviceExecutionLock.cleanup_stale_locks()
    if cleaned_device_locks:
        print(f"[ServerStartup] Removed {cleaned_device_locks} stale device lock(s).")

    # Warm the adb server and complete one enumeration before requests are
    # served, so submissions in the first seconds never race an adb cold start
    # and get a false "no devices attached" rejection.
    try:
        adb_warmed = await device_pool.warm_up_async()
    except Exception as exc:
        adb_warmed = False
        print(f"[ServerStartup] ADB warm-up failed: {exc}")
    if not adb_warmed:
        print(
            "[ServerStartup] ADB warm-up did not confirm a responding adb server; "
            "device enumeration will retry on demand."
        )
    asyncio.create_task(asyncio.to_thread(task_queue_service.archive_older_replays_on_launch))
    asyncio.create_task(
        asyncio.to_thread(task_queue_service.verify_chunks_exist_on_launch, replay_manager)
    )

    cleaned = session_repo.cleanup_orphans_on_startup()
    if cleaned > 0:
        print(f"[ServerStartup] Marked {cleaned} orphaned running session(s) as failed.")
    # Workers killed together with a previous daemon never remuxed their
    # recordings; publish whatever raw files they left behind.
    asyncio.create_task(asyncio.to_thread(task_queue_service.recover_orphaned_recordings_on_launch))

    await ipc_service.start_server()
    state.worker_task = asyncio.create_task(task_queue_service.queue_worker())
    await scheduler_service.start()
    await email_notification_service.start()


async def on_shutdown():
    """Stop services, preserving work that completed during an explicit drain."""
    await scheduler_service.stop()
    if state.is_draining:
        await task_queue_service.wait_drained()
    state.is_shutting_down = True
    state.shutdown_event.set()
    await email_notification_service.stop()
    task_queue_service._broadcast_event("server_shutdown", {"status": "stopping"})
    owned_session_ids = {
        str(item["session_id"])
        for item in state.queue_items
        if isinstance(item, dict) and item.get("status") == "running" and item.get("session_id")
    }

    worker = state.worker_task
    if worker is not None and not worker.done():
        worker.cancel()
        try:
            await asyncio.wait_for(worker, timeout=5.0)
        except (asyncio.CancelledError, TimeoutError):
            pass
    state.worker_task = None

    # Cancel in-flight run coroutines and wait for their finalizers (DB status,
    # session_ended broadcast, trace sync, recording recovery) to run.
    run_tasks = [t for t in list(task_queue_service._run_tasks) if not t.done()]
    if not state.is_draining:
        for run_task in run_tasks:
            run_task.cancel()
    if run_tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*run_tasks, return_exceptions=True), timeout=5.0)
        except (TimeoutError, asyncio.CancelledError):
            pass
    for run in list(state.active_runs.values()):
        run_proc = run.get("process")
        if run_proc is not None and run_proc.returncode is None:
            await task_queue_service._terminate_worker_process(run_proc)
    state.active_runs.clear()
    if state.current_process is not None and state.current_process.returncode is None:
        await task_queue_service._terminate_worker_process(state.current_process)
    for item in state.queue_items:
        if isinstance(item, dict):
            DeviceExecutionLock.cancel_reservation(item.get("queue_ticket"))
    DeviceExecutionLock.cleanup_stale_locks()
    state.current_process = None
    state.queue_items.clear()
    for session_id in owned_session_ids:
        session_repo.update_session_status(session_id, "cancelled")

    await ipc_service.stop_server()
    state.ipc_subscribers.clear()
    await asyncio.to_thread(shutdown_awake_service)
    clear_server_info(
        port=getattr(state, "port", 8000),
        lifecycle_token=LIFECYCLE_TOKEN,
    )


# Mount modular routers
app.include_router(stream.router)
app.include_router(media.router)
app.include_router(sessions.router)
app.include_router(steps.router)
app.include_router(tasks.router)
app.include_router(schedules.router)
app.include_router(email_settings.router)
app.include_router(replay.router)
app.include_router(system.router)
try:
    from admin_console.routers import model_settings
except ImportError:
    from apps.admin_console.routers import model_settings
app.include_router(model_settings.router)

# Mount cloud gateway router for Frappe / Cloud integration if present
try:
    from cloud_service.gateway import cloud_router

    app.include_router(cloud_router)
except ImportError:
    try:
        from apps.cloud_service.gateway import cloud_router

        app.include_router(cloud_router)
    except ImportError:
        pass


# ------------------------------------------------------------------------------
# Showcase UI unified single-port static hosting (Next.js export)
# ------------------------------------------------------------------------------
_NEXT_ROUTES = {
    "": "index.html",
    "workspace": "workspace/index.html",
    "task-schedule": "task-schedule/index.html",
    "settings": "settings/index.html",
    "check": "check/index.html",
}
_PROTECTED_UI_PREFIXES = (
    "api/", "images/", "videos/", "local_file", "docs", "openapi.json", "redoc",
)


def _get_frontend_framework() -> str:
    """Return the explicitly selected frontend, Next.js only."""
    framework = os.environ.get("ARTEMIS_FRONTEND", "next").strip().lower()
    if framework not in {"next"}:
        raise RuntimeError("ARTEMIS_FRONTEND must be 'next' (Angular has been removed)")
    return framework


def _get_showcase_dist(framework: str | None = None) -> Path:
    """Return the selected source build, or its immutable wheel resource."""
    framework = framework or _get_frontend_framework()
    source_dist = _workspace_root / "apps" / "showcase_next" / "out"
    candidates = [source_dist]

    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    bundled_dist = get_bundled_showcase_dist(framework)
    return bundled_dist if bundled_dist is not None else source_dist


def _resolve_static_file(root: Path, relative_path: str) -> Path | None:
    """Return the requested file only when it truly lives under ``root``."""
    try:
        root = root.resolve()
        target = (root / relative_path).resolve()
    except (OSError, ValueError):
        return None
    if target.is_file() and target.is_relative_to(root):
        return target
    return None


def _static_headers(relative_path: str, *, html: bool = False) -> dict[str, str]:
    if html or relative_path.endswith((".html", ".json", ".webmanifest")):
        return {"Cache-Control": "no-cache"}
    if relative_path.startswith("_next/static/"):
        return {"Cache-Control": "public, max-age=31536000, immutable"}
    return {"Cache-Control": "public, max-age=3600"}


def _file_response(path: Path, relative_path: str, *, status_code: int = 200) -> FileResponse:
    return FileResponse(
        path,
        status_code=status_code,
        headers=_static_headers(relative_path, html=path.suffix.lower() == ".html"),
    )


@app.get("/", include_in_schema=False)
async def serve_showcase_root():
    """Explicitly serve the selected Showcase UI at the root path."""
    return await serve_showcase_spa("")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_showcase_spa(full_path: str):
    clean_path = full_path.strip("/")

    if any(clean_path == prefix.rstrip("/") or clean_path.startswith(prefix) for prefix in _PROTECTED_UI_PREFIXES):
        raise HTTPException(status_code=404, detail="Endpoint not found")

    if clean_path in ("admin", "debug") or clean_path.startswith(("admin/", "debug/")):
        admin_index = _admin_console_dir / "index.html"
        if admin_index.is_file():
            return _file_response(admin_index, "index.html")
        raise HTTPException(status_code=404, detail="Admin console not found")

    framework = _get_frontend_framework()
    showcase_dist = _get_showcase_dist(framework)

    # Serve every emitted file exactly, including the complete _next tree and
    # any version-specific static navigation payloads.
    if clean_path:
        target_file = _resolve_static_file(showcase_dist, clean_path)
        if target_file is not None:
            return _file_response(target_file, clean_path)

    route_file = _NEXT_ROUTES.get(clean_path)
    if route_file is not None:
        target_file = _resolve_static_file(showcase_dist, route_file)
        if target_file is not None:
            return _file_response(target_file, route_file)
    elif clean_path.startswith("_next/") or Path(clean_path).suffix:
        raise HTTPException(status_code=404, detail="Static asset not found")

    not_found = _resolve_static_file(showcase_dist, "404.html")
    if not_found is not None:
        return _file_response(not_found, "404.html", status_code=404)
    if (showcase_dist / "index.html").is_file():
        raise HTTPException(status_code=404, detail="UI route not found")
    app_dir = "showcase_next"
    output = "out"
    fallback_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Artemis Showcase UI - Not Built</title></head><body>
<h1>Artemis Showcase UI</h1>
<p>The selected {framework} frontend has not been built yet.</p>
<p>Run <code>cd apps/{app_dir} &amp;&amp; npm install &amp;&amp; npm run build</code>.</p>
<p>Expected build output: <code>apps/{app_dir}/{output}</code>.</p>
<p><a href="/admin">Go to Admin Debug Console</a></p>
</body></html>"""
    return HTMLResponse(fallback_html, headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------------------------
# Backward compatibility exports
# ------------------------------------------------------------------------------
get_active_model_info = model_service.get_active_model_info
start_ipc_server = ipc_service.start_server
queue_worker = task_queue_service.queue_worker
active_connections = state.active_connections
ipc_subscribers = state.ipc_subscribers
task_queue = state.task_queue
queue_goals = state.queue_goals


class ArtemisUvicornServer(uvicorn.Server):
    """Notify application streams before Uvicorn waits for them to close."""

    @staticmethod
    def _task_is_active() -> bool:
        """Check task state without doing process I/O from a signal handler."""
        proc = state.current_process
        if proc is not None and proc.returncode is None:
            return True
        return any(
            isinstance(item, dict) and item.get("status") == "running" for item in state.queue_items
        )

    @staticmethod
    def _schedule_signal_report(message: str) -> None:
        """Defer console output so a signal cannot re-enter Colorama writes."""
        try:
            asyncio.get_running_loop().call_soon(print, message)
        except RuntimeError:
            try:
                os.write(2, f"{message}\n".encode(errors="replace"))
            except OSError:
                pass

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        try:
            signal_name = signal.Signals(sig).name
        except ValueError:
            signal_name = "UNKNOWN"
        frame_location = "unknown"
        if frame is not None:
            frame_location = f"{frame.f_code.co_filename}:{frame.f_lineno}"
        signal_report = (
            f"[ServerSignal] Received {signal_name} ({sig}); "
            f"server PID={os.getpid()}, parent PID={os.getppid()}, frame={frame_location}"
        )
        self._schedule_signal_report(signal_report)

        if sys.platform == "win32" and sig == signal.SIGINT and self._task_is_active():
            self._schedule_signal_report(
                "[ServerSignal] Ignored Windows SIGINT while a mobile task is active. "
                "Stop the task first, or press Ctrl+Break to force server shutdown."
            )
            return

        state.is_shutting_down = True
        state.shutdown_event.set()
        super().handle_exit(sig, frame)


def run_ui_server(host: str, port: int, reload: bool = False) -> None:
    """Run the UI server with bounded, signal-aware graceful shutdown."""
    state.host = host
    state.port = port
    write_server_info(port=port, host=host, lifecycle_token=LIFECYCLE_TOKEN)

    try:
        if reload:
            uvicorn.run(
                "apps.admin_console.server:app",
                host=host,
                port=port,
                reload=True,
                timeout_graceful_shutdown=5,
            )
            return

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            timeout_graceful_shutdown=5,
        )
        server = ArtemisUvicornServer(config)
        app.state.uvicorn_server = server
        server.run()
    finally:
        app.state.uvicorn_server = None
        clear_server_info(port=port, lifecycle_token=LIFECYCLE_TOKEN)


def main(argv: list[str] | None = None) -> None:
    """Parse the daemon/standalone server bind address and run Uvicorn."""
    parser = argparse.ArgumentParser(description="Run the Artemis Admin Console server")
    parser.add_argument(
        "--host",
        default=os.environ.get("ARTEMIS_SERVER_HOST", "127.0.0.1"),
        help=(
            "Address to bind the HTTP server to. Defaults to loopback; expose "
            "remotely via a Tailscale/SSH tunnel rather than a wide bind."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ANTIGRAVITY_SIDECAR_WEB_PORT", "8000")),
        help="TCP port for the HTTP server.",
    )
    args = parser.parse_args(argv)
    run_ui_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
