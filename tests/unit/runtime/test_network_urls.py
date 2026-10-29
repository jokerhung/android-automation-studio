from collections import namedtuple
import socket

from artemis.runtime.network_urls import lan_addresses


def test_filters_down_loopback_linklocal_duplicates_and_marks_virtual(monkeypatch):
    import psutil

    Address = namedtuple("Address", "family address")
    Stats = namedtuple("Stats", "isup")
    monkeypatch.setattr(
        psutil,
        "net_if_stats",
        lambda: {name: Stats(name != "down") for name in ("wifi", "ethernet", "utun0", "down")},
    )
    monkeypatch.setattr(
        psutil,
        "net_if_addrs",
        lambda: {
            "wifi": [
                Address(socket.AF_INET, ip)
                for ip in ("127.0.0.1", "0.0.0.0", "169.254.1.2", "192.168.1.5")
            ],
            "ethernet": [Address(socket.AF_INET, "192.168.1.5")],
            "utun0": [Address(socket.AF_INET, "10.0.0.2")],
            "down": [Address(socket.AF_INET, "10.1.0.2")],
        },
    )
    assert lan_addresses() == [("wifi", "192.168.1.5", False), ("utun0", "10.0.0.2", True)]
