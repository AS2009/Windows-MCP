"""System tray icon for Windows-MCP using pywin32."""

from __future__ import annotations

import logging
import threading
import webbrowser
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import Windows-specific tray dependencies
# ---------------------------------------------------------------------------
try:
    import win32api
    import win32con
    import win32gui
    import win32gui_struct
    HAVE_WIN32 = True
except ImportError:
    HAVE_WIN32 = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WM_TRAYICON = win32con.WM_USER + 20 if HAVE_WIN32 else 0

# Menu item IDs
IDM_OPEN_WEB = 1001
IDM_SWITCH_INTERFACE = 1002
IDM_STATUS = 1003
IDM_SEPARATOR = 0
IDM_EXIT = 1004


# ---------------------------------------------------------------------------
# Icon generation (embedded fallback – no external .ico required)
# ---------------------------------------------------------------------------
def _generate_icon(size: int = 32) -> "Image.Image":
    """Generate a simple Windows-MCP tray icon programmatically."""
    if not HAVE_PIL:
        raise RuntimeError("Pillow is required to generate the tray icon")
    
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle
    margin = 2
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(0, 120, 212),  # Windows blue
        outline=(255, 255, 255),
        width=2,
    )
    
    # Letter "W" in center
    try:
        font_size = int(size * 0.55)
        font = ImageFont.truetype("segoeui.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), "W", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), "W", fill=(255, 255, 255), font=font)
    
    return img


def _pil_to_hicon(pil_image: "Image.Image") -> int:
    """Convert a PIL Image to a Windows HICON handle."""
    if not HAVE_WIN32:
        raise RuntimeError("pywin32 is required on Windows")
    
    # Ensure RGBA
    if pil_image.mode != "RGBA":
        pil_image = pil_image.convert("RGBA")
    
    # Create bitmap from raw pixel data
    w, h = pil_image.size
    pixels = list(pil_image.getdata())
    
    # Build BITMAPINFO
    import struct
    hdc = win32gui.GetDC(0)
    
    # Create color bitmap
    hbm = win32gui.CreateCompatibleBitmap(hdc, w, h)
    hdc_mem = win32gui.CreateCompatibleDC(hdc)
    win32gui.SelectObject(hdc_mem, hbm)
    
    # Set pixel data
    buf = bytearray()
    for r, g, b, a in pixels:
        buf.extend([b, g, r, a])  # BGRA
    
    # Use SetBitmapBits
    ctypes = __import__("ctypes")
    gdi32 = ctypes.windll.gdi32
    buf_arr = (ctypes.c_byte * len(buf)).from_buffer(buf)
    gdi32.SetBitmapBits(hbm, len(buf), buf_arr)
    
    # Create mask bitmap
    hbm_mask = win32gui.CreateBitmap(w, h, 1, 1, None)
    
    # Create ICONINFO
    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", ctypes.c_bool),
            ("xHotspot", ctypes.c_uint32),
            ("yHotspot", ctypes.c_uint32),
            ("hbmMask", ctypes.c_void_p),
            ("hbmColor", ctypes.c_void_p),
        ]
    
    ii = ICONINFO()
    ii.fIcon = True
    ii.xHotspot = 0
    ii.yHotspot = 0
    ii.hbmMask = hbm_mask
    ii.hbmColor = hbm
    
    user32 = ctypes.windll.user32
    hicon = user32.CreateIconIndirect(ctypes.byref(ii))
    
    # Cleanup
    gdi32.DeleteObject(hbm)
    gdi32.DeleteObject(hbm_mask)
    win32gui.DeleteDC(hdc_mem)
    win32gui.ReleaseDC(0, hdc)
    
    return hicon


# ---------------------------------------------------------------------------
# Network interface discovery
# ---------------------------------------------------------------------------
def get_network_interfaces() -> list[dict]:
    """Return a list of available IPv4 network interfaces.
    
    Each dict contains: name, ip, description
    """
    import socket
    import subprocess
    
    interfaces: list[dict] = []
    
    try:
        # Use PowerShell to get network adapter info
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-NetIPAddress -AddressFamily IPv4 | "
                "Where-Object { $_.IPAddress -ne '127.0.0.1' } | "
                "Select-Object IPAddress, InterfaceAlias, InterfaceIndex | "
                "ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                interfaces.append({
                    "name": item.get("InterfaceAlias", "Unknown"),
                    "ip": item.get("IPAddress", ""),
                })
    except Exception:
        pass
    
    # Add "All Interfaces" as an option
    if interfaces:
        interfaces.insert(0, {"name": "All Interfaces (0.0.0.0)", "ip": "0.0.0.0"})
    
    # Fallback: get hostname's IP
    if not interfaces:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            interfaces = [
                {"name": "All Interfaces (0.0.0.0)", "ip": "0.0.0.0"},
                {"name": hostname, "ip": ip},
            ]
        except Exception:
            interfaces = [{"name": "All Interfaces (0.0.0.0)", "ip": "0.0.0.0"}]
    
    return interfaces


# ---------------------------------------------------------------------------
# System Tray Application
# ---------------------------------------------------------------------------
class WindowsMCPTray:
    """Windows system tray icon for Windows-MCP server."""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        on_exit: Callable[[], None] | None = None,
    ):
        if not HAVE_WIN32:
            raise RuntimeError(
                "System tray requires pywin32. Install with: pip install pywin32"
            )
        if not HAVE_PIL:
            raise RuntimeError(
                "System tray requires Pillow. Install with: pip install Pillow"
            )
        
        self._host = host
        self._port = port
        self._on_exit = on_exit
        self._running = False
        self._thread: threading.Thread | None = None
        self._hwnd: int | None = None
        self._hicon: int | None = None
    
    @property
    def web_url(self) -> str:
        """Return the web interface URL."""
        display_host = self._host if self._host != "0.0.0.0" else "localhost"
        return f"http://{display_host}:{self._port}"
    
    @property
    def sse_url(self) -> str:
        """Return the SSE endpoint URL."""
        display_host = self._host if self._host != "0.0.0.0" else "localhost"
        return f"http://{display_host}:{self._port}/sse"
    
    def start(self) -> None:
        """Start the tray icon in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_message_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the tray icon and clean up."""
        self._running = False
        if self._hwnd:
            try:
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
    
    def _run_message_loop(self) -> None:
        """Windows message loop for the tray icon."""
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "WindowsMCPTrayClass"
        wc.hInstance = win32api.GetModuleHandle(None)
        
        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass  # Already registered
        
        self._hwnd = win32gui.CreateWindow(
            wc.lpszClassName,
            "Windows-MCP Tray",
            0,
            0, 0, 0, 0,
            0, 0,
            wc.hInstance,
            None,
        )
        
        # Generate icon
        try:
            pil_icon = _generate_icon(32)
            self._hicon = _pil_to_hicon(pil_icon)
        except Exception as e:
            logger.warning("Failed to generate tray icon: %s", e)
            # Use default application icon
            self._hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        
        # Add tray icon
        self._add_tray_icon()
        
        # Message loop
        while self._running:
            try:
                win32gui.PumpWaitingMessages()
            except Exception:
                pass
            import time
            time.sleep(0.1)
        
        # Cleanup
        self._remove_tray_icon()
        if self._hwnd:
            try:
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                pass
    
    def _add_tray_icon(self) -> None:
        """Add the tray icon to the system tray."""
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        nid = (
            self._hwnd,
            1,  # uid
            flags,
            WM_TRAYICON,
            self._hicon,
            f"Windows-MCP ({self._host}:{self._port})",
        )
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
    
    def _remove_tray_icon(self) -> None:
        """Remove the tray icon."""
        try:
            nid = (self._hwnd, 1)
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        except Exception:
            pass
    
    def _show_context_menu(self) -> None:
        """Show the right-click context menu."""
        menu = win32gui.CreatePopupMenu()
        
        # Open Web Interface
        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_OPEN_WEB, "🌐 Open Web Interface")
        
        # Switch Interface (submenu)
        submenu = win32gui.CreatePopupMenu()
        interfaces = get_network_interfaces()
        for i, iface in enumerate(interfaces):
            check = win32con.MF_CHECKED if iface["ip"] == self._host else 0
            win32gui.AppendMenu(
                submenu,
                win32con.MF_STRING | check,
                IDM_SWITCH_INTERFACE + i,
                f"{iface['name']} ({iface['ip']})",
            )
        win32gui.AppendMenu(menu, win32con.MF_POPUP, submenu, "🔀 Switch Interface")
        
        # Status
        win32gui.AppendMenu(
            menu,
            win32con.MF_STRING | win32con.MF_GRAYED,
            IDM_STATUS,
            f"📡 SSE: {self.sse_url}",
        )
        
        # Separator
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, IDM_SEPARATOR, "")
        
        # Exit
        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_EXIT, "❌ Stop Server && Exit")
        
        # Show menu at cursor
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self._hwnd)
        cmd = win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_LEFTALIGN | win32con.TPM_RIGHTBUTTON | win32con.TPM_RETURNCMD,
            pos[0], pos[1],
            0, self._hwnd, None,
        )
        win32gui.PostMessage(self._hwnd, win32con.WM_NULL, 0, 0)
        
        if cmd == IDM_OPEN_WEB:
            self._open_web()
        elif cmd == IDM_EXIT:
            self._do_exit()
        elif IDM_SWITCH_INTERFACE <= cmd < IDM_SWITCH_INTERFACE + 100:
            idx = cmd - IDM_SWITCH_INTERFACE
            iface_list = get_network_interfaces()
            if 0 <= idx < len(iface_list):
                new_ip = iface_list[idx]["ip"]
                logger.info("Interface switch requested to %s (restart required)", new_ip)
                self._show_balloon(
                    "Interface Changed",
                    f"Restart the server with --host {new_ip} to apply.",
                )
        
        win32gui.DestroyMenu(menu)
    
    def _show_balloon(self, title: str, message: str) -> None:
        """Show a balloon notification from the tray icon."""
        try:
            flags = win32gui.NIF_INFO | win32gui.NIF_MESSAGE | win32gui.NIF_ICON | win32gui.NIF_TIP
            nid = (
                self._hwnd,
                1,
                flags,
                WM_TRAYICON,
                self._hicon,
                f"Windows-MCP",
                message,
                2000,  # timeout ms
                title,
                win32gui.NIIF_INFO,
            )
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
        except Exception:
            pass
    
    def _open_web(self) -> None:
        """Open the web interface in the default browser."""
        try:
            webbrowser.open(self.web_url)
        except Exception as e:
            logger.error("Failed to open browser: %s", e)
    
    def _do_exit(self) -> None:
        """Stop the server and exit."""
        logger.info("Exit requested from tray menu")
        if self._on_exit:
            self._on_exit()
        self._running = False
    
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure for the hidden tray window."""
        if msg == WM_TRAYICON:
            if lparam == win32con.WM_RBUTTONUP:
                self._show_context_menu()
            elif lparam == win32con.WM_LBUTTONDBLCLK:
                self._open_web()
            return 0
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def run_tray(
    host: str = "0.0.0.0",
    port: int = 8000,
    on_exit: Callable[[], None] | None = None,
) -> WindowsMCPTray:
    """Convenience function to create and start the tray icon.
    
    Args:
        host: The host the server is bound to.
        port: The port the server is listening on.
        on_exit: Called when the user clicks Exit in the tray menu.
    
    Returns:
        The WindowsMCPTray instance.
    """
    tray = WindowsMCPTray(host=host, port=port, on_exit=on_exit)
    tray.start()
    return tray
