import json
from unittest.mock import MagicMock
from artemis.runtime.tray_controller import DrainChoice, WorkloadStatus
from artemis.runtime.tray_http_adapter import (
    DefaultConfirmation,
    DefaultOpenConfirmation,
    HttpDrainAdapter,
)


def test_cancel_unfinished_posts_stop_all(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    opened = MagicMock(return_value=response)
    monkeypatch.setattr("urllib.request.urlopen", opened)
    assert HttpDrainAdapter(port=8009).cancel_unfinished() is True
    request = opened.call_args.args[0]
    assert request.full_url.endswith("/api/stop?all=true") and request.method == "POST"


def test_confirmation_maps_windows_choices(monkeypatch):
    import win32con

    monkeypatch.setattr("artemis.runtime.tray_http_adapter._message_box", lambda *a: win32con.IDNO)
    assert (
        DefaultConfirmation().choose(WorkloadStatus(active_tasks=1), for_exit=False)
        is DrainChoice.STOP_NOW
    )
    monkeypatch.setattr("artemis.runtime.tray_http_adapter._message_box", lambda *a: win32con.IDYES)
    assert (
        DefaultConfirmation().choose_after_timeout(WorkloadStatus(), for_exit=True)
        is DrainChoice.STOP_NOW
    )
    assert DefaultOpenConfirmation().confirm_start_and_open() is True
