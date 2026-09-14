"""Opt-in, current-user Windows logon startup for the local Artemis daemon.

The registry invokes this file through pythonw so neither a console nor a
browser opens. No keys, credentials, or shell commands are stored in the entry.
"""

import argparse
import os
from pathlib import Path
import re
import socket
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
            str(Path(__file__).resolve()),
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--working-directory", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Invalid port")
    os.chdir(args.working_directory)
    # Absolute script invocation is independent of the Windows logon CWD.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from artemis.runtime.daemon_client import spawn_daemon

    # Never restart/kill an existing daemon or another app occupying the port.
    try:
        with socket.create_connection(("127.0.0.1", args.port), timeout=2):
            return
    except OSError:
        pass
    spawn_daemon(host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
