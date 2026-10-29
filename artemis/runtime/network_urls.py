"""Discover interface URLs without requiring an external network connection."""

from __future__ import annotations

import ipaddress
import socket

import psutil


def lan_addresses() -> list[tuple[str, str, bool]]:
    """Return unique usable IPv4 addresses on up interfaces, with VPN hints."""
    stats = psutil.net_if_stats()
    seen: set[str] = set()
    result = []
    for name, addresses in psutil.net_if_addrs().items():
        if name not in stats or not stats[name].isup:
            continue
        virtual = any(
            hint in name.lower()
            for hint in (
                "vpn",
                "tun",
                "tap",
                "tailscale",
                "docker",
                "veth",
                "vmnet",
                "vethernet",
                "utun",
                "virtual",
                "bridge",
            )
        )
        for address in addresses:
            if address.family != socket.AF_INET:
                continue
            ip = ipaddress.IPv4Address(address.address)
            if ip.is_loopback or ip.is_unspecified or ip.is_link_local or ip.is_multicast:
                continue
            if str(ip) not in seen:
                seen.add(str(ip))
                result.append((name, str(ip), virtual))
    return sorted(result, key=lambda item: (item[2], item[0], item[1]))
