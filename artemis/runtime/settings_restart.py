"""Detached restart helper: wait for old server to exit before binding again."""

import argparse
import os
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--created", type=float, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--cwd", required=True)
    args = parser.parse_args()
    os.chdir(args.cwd)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from artemis.runtime.process_probe import pid_is_alive
    from artemis.runtime.daemon_client import spawn_daemon

    deadline = time.monotonic() + 90
    while pid_is_alive(args.pid, args.created):
        if time.monotonic() >= deadline:
            return
        time.sleep(0.25)
    spawn_daemon(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
