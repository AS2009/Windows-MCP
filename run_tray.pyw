#!/usr/bin/env pythonw
"""
Windows-MCP System Tray Launcher (no console window)

Starts the MCP server as a subprocess and shows a system tray icon.
Uses pythonw.exe (via .pyw extension) to suppress the console window.

Usage:
    pythonw run_tray.pyw
    pythonw run_tray.pyw --host 0.0.0.0 --port 8000 --auth-key 86882382
"""

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def _parse_args():
    """Parse simple command-line arguments."""
    args = {
        "host": "0.0.0.0",
        "port": 8000,
        "auth_key": os.environ.get("WINDOWS_MCP_AUTH_KEY"),
        "transport": "sse",
        "python": sys.executable.replace("pythonw.exe", "python.exe"),
    }
    
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--host", "-H") and i + 1 < len(argv):
            i += 1; args["host"] = argv[i]
        elif arg.startswith("--host="):
            args["host"] = arg.split("=", 1)[1]
        elif arg in ("--port", "-P") and i + 1 < len(argv):
            i += 1; args["port"] = int(argv[i])
        elif arg.startswith("--port="):
            args["port"] = int(arg.split("=", 1)[1])
        elif arg in ("--auth-key", "--auth_key") and i + 1 < len(argv):
            i += 1; args["auth_key"] = argv[i]
        elif arg.startswith("--auth-key=") or arg.startswith("--auth_key="):
            args["auth_key"] = arg.split("=", 1)[1]
        elif arg in ("--transport", "-t") and i + 1 < len(argv):
            i += 1; args["transport"] = argv[i]
        elif arg.startswith("--transport="):
            args["transport"] = arg.split("=", 1)[1]
        elif arg in ("-h", "--help"):
            print(__doc__)
            print("\nOptions:")
            print("  --host HOST       Bind address (default: 0.0.0.0)")
            print("  --port PORT       Listen port (default: 8000)")
            print("  --auth-key KEY    Bearer token for authentication")
            print("  --transport MODE  sse or streamable-http (default: sse)")
            sys.exit(0)
        i += 1
    
    return args


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _setup_logging():
    log_dir = Path.home() / ".windows-mcp"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "tray-launcher.log", encoding="utf-8"),
        ],
    )
    return logging.getLogger("tray-launcher")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    logger = _setup_logging()
    args = _parse_args()
    
    host = args["host"]
    port = args["port"]
    auth_key = args["auth_key"]
    transport = args["transport"]
    python_exe = args["python"]
    
    # Validate
    if not auth_key and host not in ("localhost", "127.0.0.1", "::1"):
        logger.warning("Binding to %s without auth-key. Use --auth-key for security.", host)
    
    # Display info
    if host == "0.0.0.0":
        logger.info("Binding to ALL network interfaces (0.0.0.0)")
        # Discover local IPs
        try:
            import socket
            hostname = socket.gethostname()
            local_ips = socket.gethostbyname_ex(hostname)[2]
            for ip in local_ips:
                if ip != "127.0.0.1":
                    logger.info("  Available at: http://%s:%s/sse", ip, port)
        except Exception:
            pass
    
    # Import tray module
    try:
        from windows_mcp.tray import WindowsMCPTray
    except ImportError:
        logger.error("Tray module not found. Run install_patches.py first.")
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            "System tray module not found.\n\n"
            "Please run:  python install_patches.py\n"
            "Then try again.",
            "Windows-MCP - Setup Required",
            0x10,  # MB_ICONERROR
        )
        sys.exit(1)
    
    # Build server command
    server_cmd = [
        python_exe,
        "-m", "windows_mcp",
        "serve",
        "--transport", transport,
        "--host", host,
        "--port", str(port),
    ]
    if auth_key:
        server_cmd.extend(["--auth-key", auth_key])
    else:
        server_cmd.append("--allow-insecure-remote")
    
    logger.info("Launching server: %s", " ".join(server_cmd))
    
    # Start server subprocess (hidden window)
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
    
    server_proc = subprocess.Popen(
        server_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    
    logger.info("Server started (PID: %d)", server_proc.pid)
    
    # Shared state
    stop_event = threading.Event()
    
    def on_exit():
        logger.info("Exit requested from tray menu")
        stop_event.set()
    
    # Start tray icon
    tray = WindowsMCPTray(host=host, port=port, on_exit=on_exit)
    tray.start()
    logger.info("Tray icon active — right-click for menu")
    
    # Monitor server process
    def monitor_server():
        server_proc.wait()
        if server_proc.returncode != 0 and not stop_event.is_set():
            logger.error("Server exited unexpectedly (code %d)", server_proc.returncode)
            tray._show_balloon(
                "Windows-MCP Server Stopped",
                f"Server process exited with code {server_proc.returncode}."
            )
        stop_event.set()
    
    monitor_thread = threading.Thread(target=monitor_server, daemon=True)
    monitor_thread.start()
    
    # Wait for exit
    try:
        while not stop_event.is_set():
            time.sleep(0.5)
            # Check if server is still alive
            if server_proc.poll() is not None:
                break
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    
    # Cleanup
    logger.info("Shutting down...")
    
    # Stop the server subprocess
    if server_proc.poll() is None:
        logger.info("Terminating server process...")
        try:
            if sys.platform == "win32":
                server_proc.terminate()
            else:
                server_proc.send_signal(signal.SIGTERM)
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Server did not stop, forcing kill...")
            server_proc.kill()
        except Exception as e:
            logger.error("Error stopping server: %s", e)
    
    # Stop tray icon
    tray.stop()
    
    logger.info("Goodbye!")


if __name__ == "__main__":
    # Extra safety: hide console window even with .pyw
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
    
    main()
