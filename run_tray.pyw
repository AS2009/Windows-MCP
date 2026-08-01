#!/usr/bin/env pythonw
"""
Windows-MCP Tray Launcher (thin wrapper, no console window)

Delegates to: pythonw -m windows_mcp serve --tray ...
The .pyw extension ensures pythonw.exe is used (no console window).

All server settings (host / port / transport / auth key) are read from
~/.windows-mcp/config.toml — this launcher does NOT hardcode or override
them. Command-line flags are optional overrides only:

    pythonw run_tray.pyw
    pythonw run_tray.pyw --port 9000
"""

import sys

# ---------------------------------------------------------------------------
# Hide console window (redundant with .pyw, but safety net)
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def _fatal(message: str) -> None:
    """Show an error dialog; pythonw has no usable stdout."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "Windows-MCP", 0x10)
        except Exception:
            pass
    print(message)


# ---------------------------------------------------------------------------
# Parse optional command-line overrides (--key=value or --key value)
# ---------------------------------------------------------------------------
_OVERRIDABLE = ("host", "port", "transport", "auth-key")
_overrides: dict[str, str] = {}
_args = sys.argv[1:]
for _i, _a in enumerate(_args):
    if _a in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    for _key in _OVERRIDABLE:
        if _a.startswith(f"--{_key}="):
            _overrides[_key] = _a.split("=", 1)[1]
            break
        elif _a == f"--{_key}" and _i + 1 < len(_args):
            _overrides[_key] = _args[_i + 1]
            break

# ---------------------------------------------------------------------------
# Delegate to windows_mcp serve --tray
# ---------------------------------------------------------------------------
try:
    from windows_mcp.infrastructure import CONFIG_FILE
    from windows_mcp.__main__ import main
except ImportError:
    _fatal(
        "windows_mcp 未安装。\n\n"
        "请先安装 Windows-MCP（运行安装包，或 pip install windows-mcp）。"
    )
    sys.exit(1)

if not CONFIG_FILE.exists():
    _fatal(
        f"未找到配置文件: {CONFIG_FILE}\n\n"
        "请先运行配置向导（windows-mcp.exe，或 windows-mcp setup）生成配置。"
    )
    sys.exit(1)

sys.argv = ["windows_mcp", "serve", "--tray"]
for _key, _value in _overrides.items():
    sys.argv.extend([f"--{_key}", _value])

main()
