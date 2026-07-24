# -*- coding: utf-8 -*-
# Windows-MCP 独立 EXE 入口（供 PyInstaller 打包）
#
# 用法:
#   windows-mcp.exe serve              启动 MCP 服务器（默认）
#   windows-mcp.exe setup              交互式配置向导（命令行）
#   windows-mcp.exe setup --gui        图形界面配置向导
#   windows-mcp.exe setup --quick      一键默认配置（0.0.0.0:8000，SSE）
#   windows-mcp.exe init-config        生成默认配置模板文件
#   windows-mcp.exe [其他原生命令...]   透传给原版 CLI

import sys
from pathlib import Path


def run_setup():
    """运行配置向导"""
    from setup_wizard import console_wizard, gui_wizard
    if "--gui" in sys.argv:
        gui_wizard()
    elif "--quick" in sys.argv:
        from setup_wizard import default_config, generate_toml, CONFIG_DIR, CONFIG_FILE
        cfg = default_config()
        cfg["tools_exclude"] = ["PowerShell"]
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(generate_toml(cfg), encoding="utf-8")
        print(f"快速配置完成: {CONFIG_FILE}")
        print("启动服务: windows-mcp serve")
    else:
        console_wizard()


def run_init_config():
    """生成配置模板文件"""
    from setup_wizard import default_config, generate_toml, CONFIG_DIR, CONFIG_FILE
    cfg = default_config()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(generate_toml(cfg), encoding="utf-8")
    print(f"配置模板已生成: {CONFIG_FILE}")
    print("请编辑此文件后运行: windows-mcp serve")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "setup":
        run_setup()
    elif len(sys.argv) >= 2 and sys.argv[1] == "init-config":
        run_init_config()
    else:
        from windows_mcp.__main__ import main
        sys.exit(main())
