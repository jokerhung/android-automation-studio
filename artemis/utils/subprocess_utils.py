"""Cross-platform options for non-interactive background subprocesses."""

import subprocess
import sys


def hidden_process_kwargs() -> dict[str, int]:
    """Suppress Windows console creation, including when launched by pythonw.

    Redirecting stdout/stderr alone does not prevent a console window. Keep
    POSIX kwargs unchanged and do not change process groups or signal handling.
    """
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}
