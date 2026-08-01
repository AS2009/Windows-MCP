"""Tests for the setup wizard helpers (generate_toml, config parsing, autostart)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from windows_mcp.setup_wizard import (
    _autostart_command,
    _ensure_auth_key,
    _read_config_safe,
    default_config,
    generate_toml,
)


def _cfg(**overrides):
    cfg = default_config()
    cfg.update(overrides)
    return cfg


def test_generate_toml_has_all_sections():
    cfg = _cfg(
        auth_key="secret",
        ip_allowlist=["192.168.1.0/24"],
        local_enabled=True,
        local_port=8123,
    )
    text = generate_toml(cfg)
    assert "[server]" in text
    assert 'transport = "sse"' in text
    assert 'host = "0.0.0.0"' in text
    assert 'auth_key = "secret"' in text
    assert "[security]" in text
    assert "[tools]" in text
    assert "[local]" in text
    assert "enabled = true" in text
    assert "port = 8123" in text


def test_generate_toml_omits_local_when_disabled():
    text = generate_toml(_cfg(local_enabled=False))
    assert "[local]" not in text


def test_read_config_safe_roundtrip(tmp_path: Path, monkeypatch):
    from windows_mcp import setup_wizard as sw

    monkeypatch.setattr(sw, "CONFIG_FILE", tmp_path / "config.toml")
    cfg = _cfg(auth_key="secret", local_enabled=True, local_port=8001)
    (tmp_path / "config.toml").write_text(generate_toml(cfg), encoding="utf-8")

    parsed = _read_config_safe()
    assert parsed["server"]["port"] == 8000
    assert parsed["server"]["auth_key"] == "secret"
    assert parsed["local"]["enabled"] is True
    assert parsed["local"]["port"] == 8001


def test_read_config_safe_missing_file(tmp_path: Path, monkeypatch):
    from windows_mcp import setup_wizard as sw

    monkeypatch.setattr(sw, "CONFIG_FILE", tmp_path / "nope.toml")
    assert _read_config_safe() == {}


def test_ensure_auth_key_generates_for_lan_host():
    cfg = _cfg(host="0.0.0.0", auth_key="")
    assert _ensure_auth_key(cfg)
    assert len(cfg["auth_key"]) >= 16


def test_ensure_auth_key_keeps_existing():
    cfg = _cfg(host="0.0.0.0", auth_key="my-key")
    assert _ensure_auth_key(cfg) == "my-key"


def test_ensure_auth_key_skips_loopback_and_stdio():
    cfg = _cfg(host="127.0.0.1", auth_key="")
    assert not _ensure_auth_key(cfg)
    cfg = _cfg(transport="stdio", host="0.0.0.0", auth_key="")
    assert not _ensure_auth_key(cfg)


def test_autostart_command_frozen(monkeypatch):
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", r"C:\Program Files\Windows-MCP\windows-mcp.exe")
    assert (
        _autostart_command(use_serve_all=False, transport="sse")
        == r'"C:\Program Files\Windows-MCP\windows-mcp.exe" serve --tray'
    )
    assert (
        _autostart_command(use_serve_all=True, transport="sse")
        == r'"C:\Program Files\Windows-MCP\windows-mcp.exe" serve-all'
    )
    assert (
        _autostart_command(use_serve_all=False, transport="stdio")
        == r'"C:\Program Files\Windows-MCP\windows-mcp.exe" serve'
    )


def test_autostart_command_source_uses_pythonw(monkeypatch, tmp_path: Path):
    from windows_mcp import setup_wizard as sw

    monkeypatch.delattr(sys, "frozen", raising=False)
    pythonw = tmp_path / "pythonw.exe"
    pythonw.touch()
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(sys, "platform", "win32")
    cmd = _autostart_command(use_serve_all=False, transport="sse")
    assert cmd == f'"{pythonw}" -m windows_mcp serve --tray'
