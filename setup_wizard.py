# -*- coding: utf-8 -*-
# Windows-MCP 配置向导
# 支持命令行交互、Tkinter 图形界面、开机自启管理

import os, sys, subprocess
from pathlib import Path

CONFIG_DIR = Path.home() / '.windows-mcp'
CONFIG_FILE = CONFIG_DIR / 'config.toml'
AUTOSTART_KEY = r'HKCU\Software\Microsoft\Windows\CurrentVersion\Run'
AUTOSTART_NAME = 'Windows-MCP'

def default_config():
    return {
        'transport': 'sse', 'host': '0.0.0.0', 'port': 8000,
        'auth_key': '', 'ip_allowlist': [], 'cors_origins': [],
        'tools_exclude': ['PowerShell'], 'autostart': True,
    }

def generate_toml(cfg):
    lines = ['# Windows-MCP 配置文件', '# 由 setup_wizard 生成', '',
             '[server]', f'transport = "{cfg["transport"]}"',
             f'host = "{cfg["host"]}"', f'port = {cfg["port"]}']
    if cfg['auth_key']: lines.append(f'auth_key = "{cfg["auth_key"]}"')
    if cfg.get('ssl_certfile'): lines.append(f'ssl_certfile = "{cfg["ssl_certfile"]}"')
    if cfg.get('ssl_keyfile'): lines.append(f'ssl_keyfile = "{cfg["ssl_keyfile"]}"')
    lines.append('')
    if cfg['ip_allowlist'] or cfg['cors_origins']:
        lines.append('[security]')
        if cfg['ip_allowlist']:
            ips = ', '.join(f'"{ip}"' for ip in cfg['ip_allowlist'])
            lines.append(f'ip_allowlist = [{ips}]')
        if cfg['cors_origins']:
            origins = ', '.join(f'"{o}"' for o in cfg['cors_origins'])
            lines.append(f'cors_origins = [{origins}]')
        lines.append('')
    if cfg['tools_exclude']:
        lines.append('[tools]')
        tools = ', '.join(f'"{t}"' for t in cfg['tools_exclude'])
        lines.append(f'exclude = [{tools}]')
        lines.append('')
    return '
'.join(lines)

def get_exe_path():
    if getattr(sys, 'frozen', False): return sys.executable
    return sys.argv[0]

def enable_autostart():
    try:
        exe = get_exe_path()
        subprocess.run(['reg','add',AUTOSTART_KEY,'/v',AUTOSTART_NAME,'/t','REG_SZ','/d',f'"{exe}" serve','/f'], capture_output=True, check=True)
        return True
    except: return False

def disable_autostart():
    try:
        subprocess.run(['reg','delete',AUTOSTART_KEY,'/v',AUTOSTART_NAME,'/f'], capture_output=True, check=True)
        return True
    except: return False

def is_autostart_enabled():
    try:
        r = subprocess.run(['reg','query',AUTOSTART_KEY,'/v',AUTOSTART_NAME], capture_output=True)
        return r.returncode == 0
    except: return False

def start_server():
    exe = get_exe_path()
    flag = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    subprocess.Popen([exe, 'serve'], creationflags=flag)

def quick_setup():
    cfg = default_config()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(generate_toml(cfg), encoding='utf-8')
    print(f'配置完成: {CONFIG_FILE}')
    if cfg['autostart']:
        if enable_autostart(): print('已添加开机自启')
        else: print('警告: 开机自启设置失败')
    print('正在启动服务...')
    start_server()
    print('服务已启动！')

# ── 命令行向导 ─────────────────────────────────

def console_wizard():
    print('=' * 55)
    print('  Windows-MCP 配置向导（命令行）')
    print('=' * 55)
    print()

    cfg = default_config()

    print('传输协议:')
    print('  1. sse              — 适合内网共享（默认）')
    print('  2. streamable-http  — HTTP 流式传输')
    print('  3. stdio            — 仅本机')
    choice = input('请选择 [1/2/3，默认 1]: ').strip()
    if choice == '2': cfg['transport'] = 'streamable-http'
    elif choice == '3': cfg['transport'] = 'stdio'

    if cfg['transport'] != 'stdio':
        print()
        host = input(f'绑定地址 [默认 {cfg["host"]}]: ').strip()
        if host: cfg['host'] = host
        port_str = input(f'端口号 [默认 {cfg["port"]}]: ').strip()
        if port_str: cfg['port'] = int(port_str)
        print()
        auth = input('认证密钥 [留空不启用]: ').strip()
        if auth: cfg['auth_key'] = auth
        print()
        ips = input('IP 白名单（逗号分隔）[留空不限制]: ').strip()
        if ips: cfg['ip_allowlist'] = [ip.strip() for ip in ips.split(',') if ip.strip()]

    print()
    tools = input('禁用的工具 [默认 PowerShell]: ').strip()
    if tools: cfg['tools_exclude'] = [t.strip() for t in tools.split(',') if t.strip()]

    print()
    auto = input('开机自启？[Y/n]: ').strip().lower()
    cfg['autostart'] = auto != 'n'

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(generate_toml(cfg), encoding='utf-8')
    print(f'\n配置已保存: {CONFIG_FILE}')

    if cfg['autostart']:
        ok = enable_autostart()
        print('已添加开机自启' if ok else '警告: 开机自启设置失败')
    else:
        disable_autostart()
        print('已移除开机自启')

    print()
    start_now = input('是否立即启动服务？[Y/n]: ').strip().lower()
    if start_now != 'n':
        start_server()
        print('服务已启动！')

    if cfg['transport'] != 'stdio':
        print(f'\n其他电脑连接地址: http://{{本机IP}}:{cfg["port"]}/{cfg["transport"]}')
        if cfg['auth_key']:
            print(f'认证头: Authorization: Bearer {cfg["auth_key"]}')
    print()

# ── 图形界面向导 ─────────────────────────────────

def gui_wizard():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print('Tkinter 不可用，回退到命令行模式')
        return console_wizard()

    cfg = default_config()
    root = tk.Tk()
    root.title('Windows-MCP 配置向导')
    root.geometry('540x640')
    root.resizable(False, False)

    tk.Label(root, text='Windows-MCP 服务器配置', font=('Microsoft YaHei', 14, 'bold')).pack(pady=(15, 5))
    tk.Label(root, text='配置后内网其他电脑的 AI 即可通过网络操控本机', fg='gray').pack()

    main = ttk.Frame(root, padding=15)
    main.pack(fill='both', expand=True)
    r = 0

    # 传输协议
    ttk.Label(main, text='传输协议:').grid(row=r, column=0, sticky='w', pady=5)
    transport_var = tk.StringVar(value='sse')
    ttk.Combobox(main, textvariable=transport_var, values=['sse','streamable-http','stdio'], state='readonly', width=20).grid(row=r, column=1, sticky='w', pady=5, padx=5)
    r += 1

    # 地址
    ttk.Label(main, text='绑定地址:').grid(row=r, column=0, sticky='w', pady=5)
    host_var = tk.StringVar(value='0.0.0.0')
    ttk.Entry(main, textvariable=host_var, width=24).grid(row=r, column=1, sticky='w', pady=5, padx=5)
    r += 1

    # 端口
    ttk.Label(main, text='端口:').grid(row=r, column=0, sticky='w', pady=5)
    port_var = tk.IntVar(value=8000)
    ttk.Entry(main, textvariable=port_var, width=24).grid(row=r, column=1, sticky='w', pady=5, padx=5)
    r += 1

    # 密钥
    ttk.Label(main, text='认证密钥:').grid(row=r, column=0, sticky='w', pady=5)
    auth_var = tk.StringVar()
    ttk.Entry(main, textvariable=auth_var, width=24, show='*').grid(row=r, column=1, sticky='w', pady=5, padx=5)
    ttk.Label(main, text='留空不启用', foreground='gray').grid(row=r, column=2, sticky='w', pady=5)
    r += 1

    # IP白名单
    ttk.Label(main, text='IP 白名单:').grid(row=r, column=0, sticky='w', pady=5)
    ip_var = tk.StringVar()
    ttk.Entry(main, textvariable=ip_var, width=24).grid(row=r, column=1, sticky='w', pady=5, padx=5)
    ttk.Label(main, text='逗号分隔', foreground='gray').grid(row=r, column=2, sticky='w', pady=5)
    r += 1

    # 禁用工具
    ttk.Label(main, text='禁用工具:').grid(row=r, column=0, sticky='w', pady=5)
    tools_var = tk.StringVar(value='PowerShell')
    ttk.Entry(main, textvariable=tools_var, width=24).grid(row=r, column=1, sticky='w', pady=5, padx=5)
    r += 1

    # 开机自启
    ttk.Label(main, text='开机自启:').grid(row=r, column=0, sticky='w', pady=5)
    autostart_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(main, variable=autostart_var, text='Windows 启动时自动运行服务').grid(row=r, column=1, columnspan=2, sticky='w', pady=5, padx=5)
    r += 1

    # 连接说明
    info = ttk.LabelFrame(main, text='内网连接说明', padding=10)
    info.grid(row=r, column=0, columnspan=3, sticky='ew', pady=(15, 10))
    tk.Label(info, text='启动后，其他电脑的 AI Agent 连接地址:\n  http://<本机IP>:端口/sse\n\n如果设置了认证密钥，需在请求头中添加:\n  Authorization: Bearer <密钥>', justify='left', fg='darkblue').pack()
    r += 1

    # 状态
    status_var = tk.StringVar(value='就绪')
    ttk.Label(main, textvariable=status_var, foreground='gray').grid(row=r, column=0, columnspan=3, pady=(5,0))
    r += 1

    # 按钮
    btn = ttk.Frame(main)
    btn.grid(row=r, column=0, columnspan=3, pady=15)

    def do_save_and_start():
        _save(cfg, transport_var, host_var, port_var, auth_var, ip_var, tools_var, autostart_var)
        status_var.set('正在启动服务...')
        root.update()
        start_server()
        messagebox.showinfo('配置完成',
            f'服务已启动！\n\n配置文件: {CONFIG_FILE}\n开机自启: {"是" if cfg["autostart"] else "否"}\n\n其他电脑连接地址:\nhttp://本机IP:{cfg["port"]}/{cfg["transport"]}')
        root.destroy()

    def do_save_only():
        _save(cfg, transport_var, host_var, port_var, auth_var, ip_var, tools_var, autostart_var)
        messagebox.showinfo('已保存', f'配置文件: {CONFIG_FILE}\n\n运行 windows-mcp serve 启动服务。')
        root.destroy()

    ttk.Button(btn, text='保存并启动', command=do_save_and_start, width=15).pack(side='left', padx=5)
    ttk.Button(btn, text='仅保存', command=do_save_only, width=12).pack(side='left', padx=5)
    ttk.Button(btn, text='取消', command=root.destroy, width=10).pack(side='left', padx=5)

    root.mainloop()


def _save(cfg, transport_var, host_var, port_var, auth_var, ip_var, tools_var, autostart_var):
    cfg['transport'] = transport_var.get()
    cfg['host'] = host_var.get()
    cfg['port'] = port_var.get()
    cfg['auth_key'] = auth_var.get()
    if ip_var.get():
        cfg['ip_allowlist'] = [ip.strip() for ip in ip_var.get().split(',') if ip.strip()]
    if tools_var.get():
        cfg['tools_exclude'] = [t.strip() for t in tools_var.get().split(',') if t.strip()]
    cfg['autostart'] = autostart_var.get()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(generate_toml(cfg), encoding='utf-8')
    if cfg['autostart']:
        enable_autostart()
    else:
        disable_autostart()
