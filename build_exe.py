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
# 顶层导入确保 PyInstaller 打包时发现 setup_wizard
from setup_wizard import gui_wizard, console_wizard, quick_setup, _read_config_safe


def _read_local_config():
    """读取 [local] 配置段，返回 (enabled, port)"""
    try:
        cfg = _read_config_safe()
        local = cfg.get('local', {})
        return local.get('enabled', False), local.get('port', 8001)
    except:
        return False, 8001


def run_serve_all():
    """启动双端口：主端口 + 127.0.0.1 本机端口"""
    import os
    exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    flag = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

    enabled, local_port = _read_local_config()

    p1 = subprocess.Popen([exe, 'serve'], creationflags=flag)
    print(f'[主服务] PID {p1.pid} 已启动')

    if enabled:
        p2 = subprocess.Popen(
            [exe, 'serve', '--host', '127.0.0.1', '--port', str(local_port)],
            creationflags=flag
        )
        print(f'[本机专用] PID {p2.pid}  127.0.0.1:{local_port}')

    print('服务运行中，关闭此窗口停止服务...')
    try:
        p1.wait()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    if len(sys.argv) == 1:
        gui_wizard()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'serve-all':
        run_serve_all()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'setup':
        if '--gui' in sys.argv:
            gui_wizard()
        elif '--quick' in sys.argv:
            quick_setup()
        else:
            console_wizard()
    else:
        from windows_mcp.__main__ import main
        sys.exit(main())
