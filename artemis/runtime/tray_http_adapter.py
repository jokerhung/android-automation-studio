from __future__ import annotations
import json
import time
import urllib.error
import urllib.request
import webbrowser


def _message_box(text, title, flags):
    try:
        import win32api

        return win32api.MessageBox(0, text, title, flags)
    except ImportError:
        return 2


from artemis.runtime.server_lifecycle import read_server_info
from artemis.runtime.tray_controller import WorkloadStatus


class HttpDrainAdapter:
    def __init__(self, host="127.0.0.1", port=8000, timeout=1.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def _request(self, path, method="GET"):
        info = read_server_info()
        headers = {}
        if info and getattr(info, "lifecycle_token", None):
            headers["X-Artemis-Lifecycle-Token"] = info.lifecycle_token
        request = urllib.request.Request(
            f"http://{self.host}:{self.port}/api/system{path}", headers=headers, method=method
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def workload(self):
        try:
            data = self._request("/tray-status")
        except (OSError, urllib.error.URLError, ValueError):
            return WorkloadStatus()
        return WorkloadStatus(
            active_tasks=int(data.get("active_tasks", 0)),
            queued_tasks=int(data.get("pending_tasks", 0)),
            sending_email=bool(data.get("email_sending", False)),
            paused_tasks=int(data.get("paused_tasks", 0)),
        )

    def begin_drain(self):
        try:
            self._request("/drain", "POST")
            return True
        except (OSError, urllib.error.URLError, ValueError):
            return False

    def wait_drained(self, *, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.workload().busy:
                return True
            time.sleep(0.5)
        return not self.workload().busy

    def cancel_unfinished(self):
        try:
            request = urllib.request.Request(
                f"http://{self.host}:{self.port}/api/stop?all=true", method="POST"
            )
            with urllib.request.urlopen(request, timeout=self.timeout):
                return True
        except (OSError, urllib.error.URLError, ValueError):
            return False


class DefaultBrowser:
    def open(self, url):
        return bool(webbrowser.open(url))


class DefaultConfirmation:
    def choose(self, workload, *, for_exit):
        from artemis.runtime.tray_controller import DrainChoice
        import win32con

        action = "exit" if for_exit else "stop"
        text = (
            f"ARTEMIS has {workload.active_tasks} active, {workload.queued_tasks} queued, "
            f"{workload.paused_tasks} paused task(s). Wait for completion before {action}?\n\n"
            "Yes: wait and drain\nNo: stop unfinished work now\nCancel: keep ARTEMIS running"
        )
        answer = _message_box(text, "ARTEMIS", win32con.MB_YESNOCANCEL | win32con.MB_ICONWARNING)
        return {win32con.IDYES: DrainChoice.WAIT, win32con.IDNO: DrainChoice.STOP_NOW}.get(
            answer, DrainChoice.CANCEL
        )

    def choose_after_timeout(self, workload, *, for_exit):
        from artemis.runtime.tray_controller import DrainChoice
        import win32con

        answer = _message_box(
            "Waiting for ARTEMIS work timed out. Stop unfinished work now?",
            "ARTEMIS",
            win32con.MB_YESNO | win32con.MB_ICONWARNING,
        )
        return DrainChoice.STOP_NOW if answer == win32con.IDYES else DrainChoice.CANCEL


class DefaultOpenConfirmation:
    def confirm_start_and_open(self):
        try:
            import win32con

            return (
                _message_box(
                    "ARTEMIS is stopped. Start it and open the homepage?",
                    "ARTEMIS",
                    win32con.MB_YESNO | win32con.MB_ICONQUESTION,
                )
                == win32con.IDYES
            )
        except ImportError:
            return False
