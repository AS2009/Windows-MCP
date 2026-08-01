"""Tests for automatic Windows Firewall rule management (runs on any OS)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from windows_mcp.infrastructure import firewall as fw
from windows_mcp.infrastructure.config import ServerConfig, load_config, write_config


def test_rule_name_format():
    assert fw.rule_name(8000) == "Windows-MCP (TCP 8000)"


def test_add_rule_cmd_contents():
    cmd = fw._add_rule_cmd(8000)
    assert cmd[0] == "advfirewall"
    assert "add" in cmd
    assert "name=Windows-MCP (TCP 8000)" in cmd
    assert "dir=in" in cmd
    assert "action=allow" in cmd
    assert "protocol=TCP" in cmd
    assert "localport=8000" in cmd
    assert "profile=any" in cmd


def test_manual_hint_contains_netsh():
    hint = fw.manual_netsh_hint(8000)
    assert "netsh.exe" in hint
    assert "localport=8000" in hint


def test_cmd_line_quotes_rule_name():
    line = fw._add_rule_cmd_line(8999)
    assert 'name="Windows-MCP (TCP 8999)"' in line
    assert "localport=8999" in line


def test_manual_hint_has_quoted_name():
    hint = fw.manual_netsh_hint(8999)
    assert 'name="Windows-MCP (TCP 8999)"' in hint


def test_delete_cmd_line_quotes_rule_name():
    assert 'name="Windows-MCP (TCP 8999)"' in fw._delete_rule_cmd_line(8999)


def test_non_windows_is_safe(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    ok, message = fw.add_rule(8000)
    assert not ok
    assert "仅支持 Windows" in message
    ok, message = fw.delete_rule(8000)
    assert not ok
    assert "仅支持 Windows" in message
    assert fw.rule_exists(8000) is False


def test_run_elevated_netsh_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    ok, message = fw._run_elevated_netsh("advfirewall firewall add rule x")
    assert not ok
    assert "仅支持 Windows" in message


def test_elevated_add_passes_quoted_command_line(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    captured: dict[str, str] = {}

    def fake_run(command_line: str):
        captured["line"] = command_line
        return True, "ok"

    monkeypatch.setattr(fw, "_run_elevated_netsh", fake_run)
    monkeypatch.setattr(fw, "rule_exists", lambda port: True)

    ok, message = fw._add_rule_elevated(8999)
    assert ok is True
    assert 'name="Windows-MCP (TCP 8999)"' in captured["line"]


def test_rule_exists_true(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        fw,
        "_run_netsh",
        lambda *a, **k: subprocess.CompletedProcess([], 0, "Ok.", ""),
    )
    assert fw.rule_exists(8000) is True


def test_add_rule_success_without_elevation(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        fw,
        "_run_netsh",
        lambda *a, **k: subprocess.CompletedProcess([], 0, "Ok.", ""),
    )
    ok, message = fw.add_rule(8000)
    assert ok is True
    assert message == "ok"


def test_add_rule_elevates_when_denied(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    def fake_netsh(args, **kwargs):
        if "show" in args:
            return subprocess.CompletedProcess(args, 1, "", "No rules match")
        return subprocess.CompletedProcess(args, 1, "", "requires elevation")

    monkeypatch.setattr(fw, "_run_netsh", fake_netsh)

    # Without elevation: reported as failure
    ok, message = fw.add_rule(8000, elevate=False)
    assert not ok
    assert "requires elevation" in message

    # With elevation: delegated to the UAC path
    monkeypatch.setattr(
        fw, "_add_rule_elevated", lambda port: (True, "ok")
    )
    ok, message = fw.add_rule(8000, elevate=True)
    assert ok is True
    assert message == "ok"


def test_add_rule_elevation_cancelled(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        fw,
        "_run_netsh",
        lambda *a, **k: subprocess.CompletedProcess([], 1, "", "requires elevation"),
    )
    monkeypatch.setattr(
        fw, "_add_rule_elevated", lambda port: (False, "用户取消了管理员授权")
    )
    ok, message = fw.add_rule(8000, elevate=True)
    assert not ok
    assert "取消" in message


def test_ensure_firewall_open_is_idempotent(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        fw,
        "_run_netsh",
        lambda *a, **k: subprocess.CompletedProcess([], 0, "Ok.", ""),
    )
    ok, message = fw.ensure_firewall_open(8000)
    assert ok is True


def test_delete_rule_success(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        fw,
        "_run_netsh",
        lambda *a, **k: subprocess.CompletedProcess([], 0, "Ok.", ""),
    )
    ok, message = fw.delete_rule(8000)
    assert ok is True


def test_invalid_port_rejected(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    ok, message = fw.add_rule(99999)
    assert not ok
    assert "无效" in message


def test_open_firewall_config_default_true():
    assert ServerConfig().open_firewall is True


def test_open_firewall_config_parse(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[server]\nopen_firewall = false\n", encoding="utf-8")
    assert load_config(p).server.open_firewall is False

    p.write_text("[server]\nopen_firewall = true\n", encoding="utf-8")
    assert load_config(p).server.open_firewall is True


def test_open_firewall_config_type_error(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[server]\nopen_firewall = "yes"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="open_firewall must be a TOML boolean"):
        load_config(p)


def test_write_config_omits_default_firewall(tmp_path):
    p = tmp_path / "config.toml"
    write_config(load_config(None), p)
    assert "open_firewall" not in p.read_text(encoding="utf-8")


def test_write_config_keeps_disabled_firewall(tmp_path):
    from windows_mcp.infrastructure.config import WindowsMCPConfig

    cfg = WindowsMCPConfig()
    cfg.server.open_firewall = False
    p = tmp_path / "config.toml"
    write_config(cfg, p)
    assert "open_firewall = false" in p.read_text(encoding="utf-8")
