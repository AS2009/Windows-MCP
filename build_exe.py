# -*- coding: utf-8 -*-
# Windows-MCP 独立 EXE 入口
#
# 双击运行              →  图形配置向导
# setup                 →  命令行配置向导
# setup --gui           →  图形配置向导
# setup --quick         →  一键默认配置
# serve                 →  启动 MCP 服务器（仅主端口）
# serve-all             →  同时启动主端口 + 本机端口
# 其他参数               →  透传给原版 CLI

import sys
import subprocess
from windows_mcp.setup_wizard import gui_wizard, console_wizard, quick_setup, _read_config_safe


def _hide_console():
    """Hide the console window of this (console-built) EXE.

    The EXE is built with --console so `serve` keeps stdout/stderr for
    logging, but GUI/tray/autostart paths should not flash a console.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def _read_local_config():
    try:
        cfg = _read_config_safe()
        local = cfg.get('local', {})
        return local.get('enabled', False), local.get('port', 8001)
    except:
        return False, 8001


def _server_argv():
    """argv prefix to launch a windows-mcp server process."""
    if getattr(sys, 'frozen', False):
        return [sys.executable]
    return [sys.executable, '-m', 'windows_mcp']


def run_serve_all():
    exe = _server_argv()
    flag = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    enabled, local_port = _read_local_config()

    p1 = subprocess.Popen(exe + ['serve'], creationflags=flag)
    print(f'[主服务] PID {p1.pid} 已启动')
    if enabled:
        p2 = subprocess.Popen(
            exe + ['serve', '--host', '127.0.0.1', '--port', str(local_port)],
            creationflags=flag
        )
        print(f'[本机专用] PID {p2.pid}  127.0.0.1:{local_port}')
    print('服务运行中，关闭此窗口停止服务...')
    try:
        p1.wait()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    # A lone "--tray" (e.g. from a double-clicked launcher) means `serve --tray`.
    if len(sys.argv) >= 2 and sys.argv[1] == '--tray':
        sys.argv = [sys.argv[0], 'serve', '--tray', *sys.argv[2:]]

    if len(sys.argv) == 1:
        _hide_console()  # GUI wizard doesn't need the console
        gui_wizard()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'serve-all':
        _hide_console()  # autostart path: don't flash a console at logon
        run_serve_all()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'setup':
        if '--gui' in sys.argv:
            _hide_console()
            gui_wizard()
        elif '--quick' in sys.argv:
            quick_setup()
        else:
            console_wizard()
    else:
        if '--tray' in sys.argv:
            _hide_console()
        from windows_mcp.__main__ import main
        sys.exit(main())
