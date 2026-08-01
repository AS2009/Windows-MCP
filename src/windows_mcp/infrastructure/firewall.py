"""Automatic Windows Firewall rule management for Windows-MCP.

Windows Firewall blocks inbound connections by default, so a LAN client
cannot reach the MCP server until a rule opens the listening port. This
module adds/removes such rules via ``netsh advfirewall`` (available on
Windows 7 through 11, including 8.1). Adding rules requires elevation,
so a non-elevated attempt is made first and, when that fails, the command
is retried through the UAC prompt (``runas`` verb).
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

RULE_NAME_PREFIX = "Windows-MCP (TCP"
NETSH = r"C:\Windows\System32\netsh.exe"


def _is_windows() -> bool:
    return sys.platform == "win32"


def rule_name(port: int) -> str:
    """Return the exact Windows Firewall rule name for *port*."""
    return f"Windows-MCP (TCP {port})"


def _run_netsh(args: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    """Run netsh with the given argument list, hiding its console."""
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        ["netsh", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=creationflags,
    )


def rule_exists(port: int) -> bool:
    """Return True when an inbound TCP rule for *port* already exists."""
    if not _is_windows():
        return False
    try:
        proc = _run_netsh(
            ["advfirewall", "firewall", "show", "rule", f"name={rule_name(port)}"]
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        logger.debug("netsh show rule failed", exc_info=True)
        return False


def _add_rule_cmd(port: int) -> list[str]:
    return [
        "advfirewall",
        "firewall",
        "add",
        "rule",
        f"name={rule_name(port)}",
        "dir=in",
        "action=allow",
        "protocol=TCP",
        f"localport={port}",
        "profile=any",
        "enable=yes",
    ]


def _add_rule_cmd_line(port: int) -> str:
    """Command-line string form (for UAC / manual execution).

    The rule name contains spaces and parentheses, so the value MUST be
    double-quoted in the raw command line — otherwise netsh's tokenizer
    splits ``name=Windows-MCP (TCP 8999)`` into three arguments and the
    command fails. The list form (:func:`_add_rule_cmd`) relies on
    subprocess quoting instead and must stay unquoted here.
    """
    return (
        "advfirewall firewall add rule "
        f'name="{rule_name(port)}" dir=in action=allow protocol=TCP '
        f"localport={port} profile=any enable=yes"
    )


def _delete_rule_cmd(port: int) -> list[str]:
    return [
        "advfirewall",
        "firewall",
        "delete",
        "rule",
        f"name={rule_name(port)}",
    ]


def _delete_rule_cmd_line(port: int) -> str:
    return f'advfirewall firewall delete rule name="{rule_name(port)}"'


def _run_elevated_netsh(command_line: str, timeout: float = 150.0) -> tuple[bool, str]:
    """Run a netsh command elevated via the UAC prompt.

    Uses ``Start-Process -Verb RunAs -Wait`` so the elevated netsh runs
    hidden and PowerShell reports whether the user accepted the prompt.
    Returns ``(accepted, message)`` — a True result means netsh was
    launched, not necessarily that the rule changed; callers should verify
    with :func:`rule_exists`.
    """
    if not _is_windows():
        return False, "仅支持 Windows"

    # Single-quoted PowerShell string: literal, so the embedded double
    # quotes around the rule name survive into the elevated command line.
    ps_script = (
        "$ErrorActionPreference = 'Stop'; "
        "try { Start-Process -FilePath 'C:\\Windows\\System32\\netsh.exe' "
        f"-ArgumentList '{command_line}' -Verb RunAs -Wait -WindowStyle Hidden; "
        "Write-Output 'OK' } "
        "catch { Write-Output $_.Exception.Message }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return False, "提权执行超时（UAC 授权框可能未确认）。"
    except OSError as exc:
        return False, f"无法启动提权进程: {exc}"

    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0 and "OK" in output:
        return True, "ok"

    message = output.strip().splitlines()[-1] if output.strip() else f"退出码 {proc.returncode}"
    if "cancel" in message.lower() or "取消" in message:
        return False, "用户取消了管理员授权，未能开放防火墙端口。"
    return False, message


def _add_rule_elevated(port: int) -> tuple[bool, str]:
    """Add the rule through the UAC prompt and wait for it to appear."""
    accepted, message = _run_elevated_netsh(_add_rule_cmd_line(port))
    if not accepted:
        return False, message

    # Wait for the rule to appear (Start-Process -Wait can return before
    # the elevated netsh finishes on some PowerShell versions).
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if rule_exists(port):
            return True, "ok"
        time.sleep(1)
    return False, "提权添加超时，请以管理员身份手动执行 netsh 命令。"


def add_rule(port: int, elevate: bool = False) -> tuple[bool, str]:
    """Add an inbound TCP firewall rule for *port*.

    Returns ``(ok, message)``. When *elevate* is True and the normal attempt
    fails, the rule is retried through the UAC prompt.
    """
    if not _is_windows():
        return False, "防火墙管理仅支持 Windows。"
    if not (1 <= port <= 65535):
        return False, f"端口号无效: {port}"
    if rule_exists(port):
        return True, "ok"

    try:
        proc = _run_netsh(_add_rule_cmd(port))
    except (OSError, subprocess.TimeoutExpired) as exc:
        proc = None
        last_error = str(exc)

    if proc is not None and proc.returncode == 0:
        logger.info("Firewall rule added: %s", rule_name(port))
        return True, "ok"

    if proc is not None:
        last_error = (proc.stderr or proc.stdout or "").strip() or "未知错误"
    if not elevate:
        return False, last_error

    ok, msg = _add_rule_elevated(port)
    if ok:
        logger.info("Firewall rule added via UAC: %s", rule_name(port))
    return ok, msg


def _delete_rule_elevated(port: int) -> tuple[bool, str]:
    """Delete the rule through the UAC prompt and wait for it to disappear."""
    accepted, message = _run_elevated_netsh(_delete_rule_cmd_line(port))
    if not accepted:
        return False, message

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not rule_exists(port):
            return True, "ok"
        time.sleep(1)
    return False, "提权删除超时，请以管理员身份手动执行 netsh 命令。"


def delete_rule(port: int, elevate: bool = False) -> tuple[bool, str]:
    """Remove the inbound TCP firewall rule for *port*."""
    if not _is_windows():
        return False, "防火墙管理仅支持 Windows。"
    if not rule_exists(port):
        return True, "ok"

    try:
        proc = _run_netsh(_delete_rule_cmd(port))
    except (OSError, subprocess.TimeoutExpired) as exc:
        proc = None
        last_error = str(exc)

    if proc is not None and proc.returncode == 0:
        return True, "ok"

    if proc is not None:
        last_error = (proc.stderr or proc.stdout or "").strip() or "未知错误"
    if not elevate:
        return False, last_error

    ok, msg = _delete_rule_elevated(port)
    if ok:
        logger.info("Firewall rule removed via UAC: %s", rule_name(port))
    return ok, msg


def ensure_firewall_open(
    port: int, allow_elevate: bool = True
) -> tuple[bool, str]:
    """Make sure an inbound TCP rule exists for *port*.

    Idempotent: existing rules are left untouched. A non-elevated attempt
    is made first; when it fails and *allow_elevate* is True, the UAC prompt
    is used to retry.
    """
    return add_rule(port, elevate=allow_elevate)


def manual_netsh_hint(port: int) -> str:
    """Return the exact elevated command the user can run by hand."""
    return f'"{NETSH}" {_add_rule_cmd_line(port)}'
