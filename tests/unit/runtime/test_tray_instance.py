from pathlib import Path
from unittest.mock import MagicMock

import pytest

from artemis.runtime.tray_instance import (
    InvalidAttachRequest,
    TrayInstance,
    TrayTarget,
    attach_existing,
    decode_attach_request,
    encode_attach_request,
)


class FakeMutexApi:
    def __init__(self, already_exists: bool = False) -> None:
        self.already_exists = already_exists
        self.created = []
        self.closed = []

    def create(self, name):
        self.created.append(name)
        return object(), self.already_exists

    def close(self, handle):
        self.closed.append(handle)


def test_target_identity_binds_user_canonical_workspace_and_port(tmp_path):
    relative = tmp_path / "folder" / ".." / "workspace"
    a = TrayTarget.create(relative, 8009, user="DOMAIN\alice")
    b = TrayTarget.create(relative.resolve(), 8009, user="DOMAIN\alice")
    assert a.key == b.key
    assert a.mutex_name.startswith(r"Local\ARTEMIS.Tray.")
    assert a.pipe_address.endswith(a.key)
    assert TrayTarget.create(relative, 8010, user="DOMAIN\alice").key != a.key
    assert TrayTarget.create(relative, 8009, user="DOMAIN\bob").key != a.key


@pytest.mark.parametrize("port", [0, 65536])
def test_target_rejects_invalid_port(port):
    with pytest.raises(ValueError):
        TrayTarget.create(Path.cwd(), port, user="alice")


def test_attach_protocol_accepts_only_fixed_actions():
    assert decode_attach_request(encode_attach_request("open_homepage")) == "open_homepage"
    for payload in [
        b'{"action":"exit"}',
        b'{"action":"show","command":"calc.exe"}',
        b'{"action":"open_homepage","url":"https://example.com"}',
        b"not-json",
    ]:
        with pytest.raises(InvalidAttachRequest):
            decode_attach_request(payload)
    with pytest.raises(InvalidAttachRequest):
        encode_attach_request("exit")


def test_mutex_second_instance_closes_non_owned_handle(tmp_path):
    api = FakeMutexApi(already_exists=True)
    instance = TrayInstance(TrayTarget.create(tmp_path, 8009, user="alice"), mutex_api=api)
    assert instance.acquire() is False
    assert len(api.closed) == 1


def test_owned_mutex_is_released(tmp_path):
    api = FakeMutexApi()
    instance = TrayInstance(TrayTarget.create(tmp_path, 8009, user="alice"), mutex_api=api)
    assert instance.acquire() is True
    assert instance.acquire() is True
    assert len(api.created) == 1
    instance.close()
    assert len(api.closed) == 1


def test_attach_existing_sends_whitelisted_bytes_and_authenticates(tmp_path):
    connection = MagicMock()
    connection.recv_bytes.return_value = b'{"ok":true}'
    factory = MagicMock(return_value=connection)
    target = TrayTarget.create(tmp_path, 8009, user="alice")

    assert attach_existing(target, "start", client_factory=factory) is True
    factory.assert_called_once_with(target.pipe_address, family="AF_PIPE", authkey=target.authkey)
    connection.send_bytes.assert_called_once_with(b'{"action":"start"}')
    connection.close.assert_called_once()


def test_attach_existing_failure_is_closed(tmp_path):
    target = TrayTarget.create(tmp_path, 8009, user="alice")
    assert attach_existing(target, client_factory=MagicMock(side_effect=OSError)) is False
