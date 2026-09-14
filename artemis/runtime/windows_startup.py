"""Opt-in, current-user Windows logon startup for the local Artemis daemon.

The registry invokes this file through pythonw so neither a console nor a
browser opens. No keys, credentials, or shell commands are stored in the entry.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Artemis"


def startup_command(port: int) -> str:
    from artemis.config.paths import ROOT_DIR

    if not 1 <= port <= 65535:
        raise ValueError("Invalid server port")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        raise OSError("pythonw.exe is missing from this Python installation.")
    return subprocess.list2cmdline(
        [
            str(pythonw),
            "-m",
            "artemis.runtime.windows_startup",
            "--working-directory",
            str(ROOT_DIR),
            "--port",
            str(port),
        ]
    )


def get_startup_status() -> dict:
    if sys.platform != "win32":
        return {"supported": False, "enabled": False, "port": None}
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        command = ""
    match = re.search(r"--port (\d+)(?:\s|$)", str(command))
    return {
        "supported": True,
        "enabled": bool(command),
        "port": int(match.group(1)) if match else None,
    }


def set_startup_enabled(enabled: bool, port: int) -> dict:
    if sys.platform != "win32":
        raise NotImplementedError("Start with Windows is available only on Windows.")
    import winreg

    if enabled:
        command = startup_command(port)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
    return get_startup_status()


def main() -> None:
    """Ensure the identity-aware tray/daemon target at Windows sign-in."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--working-directory", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Invalid port")
    os.chdir(args.working_directory)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from artemis.runtime.background_runtime import (
        WindowsTrayRuntimeAdapter,
        ensure_background_runtime,
    )
    from artemis.runtime.tray_controller import ArtemisLifecycleAdapter
    from artemis.runtime.tray_launcher import _configure_launcher_logging

    logger = _configure_launcher_logging(args.port)
    logger.info("Windows startup orchestration beginning")
    result = ensure_background_runtime(
        host="127.0.0.1",
        port=args.port,
        lifecycle=ArtemisLifecycleAdapter(host="127.0.0.1", port=args.port),
        tray=WindowsTrayRuntimeAdapter(workspace=args.working_directory),
        wait_timeout=60.0,
    )
    if result.ok:
        logger.info(
            "Windows startup orchestration ready; daemon_started=%s tray_running=%s",
            result.daemon_started,
            result.tray_running,
        )
    else:
        logger.error("Windows startup orchestration failed: %s", result.detail)


if __name__ == "__main__":
    main()
