"""Tests for tray network-interface discovery (runs on any OS)."""

from __future__ import annotations

import subprocess

import pytest

from windows_mcp.tray.icon import _ipconfig_get_interfaces, get_network_interfaces


IPCONFIG_SAMPLE = """\r
Windows IP Configuration\r
\r
\r
Ethernet adapter Ethernet:\r
\r
   Connection-specific DNS Suffix  . : lan.local\r
   Link-local IPv6 Address . . . . . : fe80::1%12\r
   IPv4 Address. . . . . . . . . . . : 192.168.1.10\r
   Subnet Mask . . . . . . . . . . . : 255.255.255.0\r
   Default Gateway . . . . . . . . . : 192.168.1.1\r
\r
Ethernet adapter Wi-Fi:\r
\r
   IPv4 Address. . . . . . . . . . . : 10.0.0.5\r
   Subnet Mask . . . . . . . . . . . : 255.255.255.0\r
\r
Ethernet adapter Loopback:\r
\r
   IPv4 Address. . . . . . . . . . . : 127.0.0.1\r
\r
"""


def test_ipconfig_parse_dual_nic(monkeypatch):
    monkeypatch.setattr(
        "windows_mcp.tray.icon.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, IPCONFIG_SAMPLE, ""),
    )
    interfaces = _ipconfig_get_interfaces()
    assert {"name": "Ethernet", "ip": "192.168.1.10"} in interfaces
    assert {"name": "Wi-Fi", "ip": "10.0.0.5"} in interfaces
    # Loopback is filtered out
    assert all(iface["ip"] != "127.0.0.1" for iface in interfaces)


def test_get_network_interfaces_prepends_all_interfaces(monkeypatch):
    # Force the socket fallback (no powershell/ipconfig on this host)
    monkeypatch.setattr(
        "windows_mcp.tray.icon._ps_get_interfaces", lambda: []
    )
    monkeypatch.setattr(
        "windows_mcp.tray.icon._ipconfig_get_interfaces", lambda: []
    )
    interfaces = get_network_interfaces()
    assert interfaces[0]["ip"] == "0.0.0.0"
    assert len(interfaces) >= 1


def test_get_network_interfaces_dedupes(monkeypatch):
    monkeypatch.setattr(
        "windows_mcp.tray.icon._ps_get_interfaces",
        lambda: [{"name": "A", "ip": "192.168.1.5"}, {"name": "B", "ip": "192.168.1.5"}],
    )
    interfaces = get_network_interfaces()
    ips = [iface["ip"] for iface in interfaces]
    assert ips.count("192.168.1.5") == 1
    assert ips[0] == "0.0.0.0"
