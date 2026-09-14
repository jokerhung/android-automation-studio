from __future__ import annotations
import argparse
import logging
from pathlib import Path
import sys


def launcher_log_path(port: int) -> Path:
    from artemis.config.paths import get_app_dir

    return get_app_dir() / "logs" / f"tray-{port}.log"


def _configure_launcher_logging(port: int) -> logging.Logger:
    path = launcher_log_path(port)
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return logging.getLogger(__name__)


import threading


def main(argv=None):
    parser = argparse.ArgumentParser(description="ARTEMIS Windows system tray")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--workspace", default="")
    args = parser.parse_args(argv)
    logger = _configure_launcher_logging(args.port)
    logger.info("Tray launcher starting for workspace=%s port=%s", args.workspace or ".", args.port)
    if sys.platform != "win32":
        logger.error("Tray launcher is unavailable on platform %s", sys.platform)
        return 2
    from artemis.runtime.background_runtime import BackgroundOperationRunner
    from artemis.runtime.tray_app import TrayApp, TrayCallbacks, TrayView
    from artemis.runtime.tray_controller import ArtemisLifecycleAdapter, TrayController
    from artemis.runtime.tray_http_adapter import (
        DefaultBrowser,
        DefaultConfirmation,
        DefaultOpenConfirmation,
        HttpDrainAdapter,
    )
    from artemis.runtime.tray_instance import TrayInstance, TrayTarget, attach_existing

    target = TrayTarget.create(args.workspace or ".", args.port)
    instance = TrayInstance(target)
    if not instance.acquire():
        attached = attach_existing(target, "show")
        logger.info("Existing tray target found; attach result=%s", attached)
        return 0 if attached else 1
    runner = BackgroundOperationRunner()
    shell_ref = {}

    def changed(snapshot):
        shell = shell_ref.get("shell")
        if not shell:
            return
        mapped = {"draining": "stopping", "port_conflict": "error", "exited": "stopped"}.get(
            snapshot.state.value, snapshot.state.value
        )
        shell.update(TrayView(mapped, args.port))
        if snapshot.exit_requested:
            shell.stop()

    lifecycle = ArtemisLifecycleAdapter(host=args.host, port=args.port)
    controller = TrayController(
        port=args.port,
        lifecycle=lifecycle,
        drain=HttpDrainAdapter(args.host, args.port),
        confirmation=DefaultConfirmation(),
        browser=DefaultBrowser(),
        open_confirmation=DefaultOpenConfirmation(),
        on_change=changed,
    )

    def submit(fn):
        runner.submit(fn)

    shell = TrayApp(
        TrayCallbacks(
            lambda: submit(controller.start),
            lambda: submit(controller.stop),
            lambda: submit(controller.open_homepage),
            lambda: submit(controller.exit),
        ),
        TrayView("stopped", args.port),
    )
    shell_ref["shell"] = shell
    stop_poll = threading.Event()

    def attach_action(action):
        if action == "start":
            submit(controller.start)
        elif action == "open_homepage":
            submit(controller.open_homepage)
        else:
            submit(controller.refresh)

    def poll():
        while not stop_poll.wait(2.0):
            try:
                submit(controller.refresh)
            except RuntimeError:
                return

    instance.start_attach_listener(attach_action)
    poller = threading.Thread(target=poll, name="artemis-tray-poll", daemon=True)
    poller.start()
    try:
        controller.refresh()
        logger.info("Tray event loop starting")
        shell.run()
    except Exception:
        logger.exception("Tray launcher failed")
        return 1
    finally:
        stop_poll.set()
        runner.close(wait=False, cancel_pending=True)
        instance.close()
        logger.info("Tray launcher stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
