"""Manual host smoke: build frontend first, then run with the project Python.

Creates isolated runtime data under .test-tmp; never runs Android tasks or
changes the developer installation's configuration/metadata.
"""

import argparse
import os
from pathlib import Path
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    temporary_parent = ROOT / ".test-tmp"
    temporary_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="installer-runtime-", dir=temporary_parent, ignore_cleanup_errors=True
    ) as temporary:
        os.environ["ARTEMIS_APP_DIR"] = temporary
        os.environ["ARTEMIS_FRONTEND"] = "next"
        from scripts import install_runtime as installer

        installer.STATE = Path(temporary) / "install-state.json"
        installer.LOG = Path(temporary) / "install.log"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        state = {
            "schema": 1,
            "source": "jokerhung/android-automation-studio",
            "host": "0.0.0.0",
            "port": port,
        }
        args = argparse.Namespace(
            action="start", port=port, local_only=False, non_interactive=True, open=False
        )
        try:
            assert installer.manage(args, state) == 0
            args.action = "status"
            assert installer.manage(args, state) == 0
            args.action = "restart"
            assert installer.manage(args, state) == 0
        finally:
            from artemis.runtime.server_lifecycle import read_server_info
            import psutil

            info = read_server_info(port)
            args.action = "stop"
            assert installer.manage(args, state) == 0
            if info:
                try:
                    psutil.Process(info["pid"]).wait(timeout=15)
                except psutil.NoSuchProcess:
                    pass
        assert installer.port_available(port, "0.0.0.0")
        print("PASS: real detached start/status/restart/stop, identity and frontend HTTP checks")


if __name__ == "__main__":
    main()
