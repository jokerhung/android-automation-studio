import pytest
from apps.admin_console.services.device_input_service import REMOTE_KEYCODES, InputError, control_allowed

def test_remote_key_allowlist_does_not_accept_raw_codes():
    assert REMOTE_KEYCODES["escape"] == 111
    assert "29" not in REMOTE_KEYCODES

@pytest.mark.parametrize("host,allowed", [("127.0.0.1", True), ("::1", True), ("192.168.1.20", False)])
def test_remote_control_is_loopback_only_by_default(monkeypatch, host, allowed):
    from admin_console.core.state import state
    monkeypatch.setattr(state, "host", "127.0.0.1")
    assert control_allowed(host) is allowed

def test_remote_control_can_be_enabled_for_lan(monkeypatch):
    from admin_console.core.state import state
    monkeypatch.setattr(state, "host", "0.0.0.0")
    assert control_allowed("192.168.1.20")
