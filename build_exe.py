# -*- coding: utf-8 -*-
# Windows-MCP 独立 EXE 入口
#
# 双击运行              →  图形配置向导
# setup                 →  命令行配置向导
# setup --gui           →  图形配置向导
# setup --quick         →  一键默认配置
# serve                 →  启动 MCP 服务器（仅主端口）
# serve-all             →  同时启动主端口 + 本机端口（需先配置）
# 其他参数               →  透传给原版 CLI

import sys
import subprocess


def _read_local_config():
    """读取 [local] 配置段，返回 (enabled, port)"""
    from pathlib import Path
    cfg_file = Path.home() / '.windows-mcp' / 'config.toml'
    if not cfg_file.exists():
        return False, 8001
    try:
        text = cfg_file.read_text(encoding='utf-8')
        in_local = False
        enabled = False
        port = 8001
        for line in text.split('\n'):
            line = line.strip()
            if line == '[local]':
                in_local = True
            elif line.startswith('[') and line != '[local]':
                in_local = False
            elif in_local:
                if line.startswith('enabled'):
                    enabled = 'true' in line.lower()
                elif line.startswith('port'):
                    try:
                        port = int(line.split('=')[1].strip())
                    except:
                        pass
        return enabled, port
    except:
        return False, 8001


def run_serve_all():
    """启动双端口：主端口 + 127.0.0.1 本机端口"""
    import os
    exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
    flag = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

    enabled, local_port = _read_local_config()

    # 主服务（内网共享）
    p1 = subprocess.Popen([exe, 'serve'], creationflags=flag)
    print(f'[主服务] PID {p1.pid} 已启动')

    # 本机专用服务
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
        from setup_wizard import gui_wizard
        gui_wizard()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'serve-all':
        run_serve_all()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'setup':
        from setup_wizard import console_wizard, gui_wizard
        if '--gui' in sys.argv:
            gui_wizard()
        elif '--quick' in sys.argv:
            from setup_wizard import quick_setup
            quick_setup()
        else:
            console_wizard()
    else:
        from windows_mcp.__main__ import main
        sys.exit(main())
