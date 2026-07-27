#!/usr/bin/env pythonw
"""
Windows-MCP Tray Launcher (thin wrapper, no console window)

Delegates to: pythonw -m windows_mcp serve --tray ...
The .pyw extension ensures pythonw.exe is used (no console window).

Usage:
    pythonw run_tray.pyw
    pythonw run_tray.pyw --auth-key MYKEY --port 9000
"""

import os
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

# ---------------------------------------------------------------------------
# Build defaults
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "host": "0.0.0.0",
    "port": "8000",
    "auth_key": os.environ.get("WINDOWS_MCP_AUTH_KEY", "86882382"),
    "transport": "sse",
}

# Parse command-line overrides
_args = sys.argv[1:]
for _i, _a in enumerate(_args):
    if _a in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    for _key in _DEFAULTS:
        if _a.startswith(f"--{_key}="):
            _DEFAULTS[_key] = _a.split("=", 1)[1]
            break
        elif _a == f"--{_key}" and _i + 1 < len(_args):
            _DEFAULTS[_key] = _args[_i + 1]
            break

# ---------------------------------------------------------------------------
# Delegate to windows_mcp serve --tray
# ---------------------------------------------------------------------------
sys.argv = [
    "windows_mcp",
    "serve",
    "--tray",
    "--transport", _DEFAULTS["transport"],
    "--host", _DEFAULTS["host"],
    "--port", _DEFAULTS["port"],
]
if _DEFAULTS["auth_key"]:
    sys.argv.extend(["--auth-key", _DEFAULTS["auth_key"]])

from windows_mcp.__main__ import main
main()
