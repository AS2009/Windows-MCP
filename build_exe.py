# -*- coding: utf-8 -*-
# Windows-MCP 独立 EXE 入口（供 PyInstaller 打包）
#
# 双击运行 / 无参数  →  打开图形配置向导
# setup              →  命令行配置向导
# setup --gui        →  图形配置向导
# setup --quick      →  一键默认配置
# serve              →  启动 MCP 服务器
# 其他参数            →  透传给原版 CLI

import sys


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # 双击运行，无参数 → 图形向导
        from setup_wizard import gui_wizard
        gui_wizard()
    elif len(sys.argv) >= 2 and sys.argv[1] == "setup":
        from setup_wizard import console_wizard, gui_wizard
        if "--gui" in sys.argv:
            gui_wizard()
        elif "--quick" in sys.argv:
            from setup_wizard import quick_setup
            quick_setup()
        else:
            console_wizard()
    else:
        from windows_mcp.__main__ import main
        sys.exit(main())
