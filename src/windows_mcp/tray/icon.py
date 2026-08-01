"""System tray icon for Windows-MCP using pywin32."""

from __future__ import annotations

import logging
import socket
import subprocess
import threading
import time
import webbrowser
from typing import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import Windows-specific tray dependencies
# ---------------------------------------------------------------------------
try:
    import win32api
    import win32con
    import win32gui
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


def _notify_const(name: str) -> int:
    """Resolve a Shell_NotifyIcon constant from win32gui or win32con."""
    value = getattr(win32gui, name, None)
    if value is None:
        value = getattr(win32con, name)
    return value


if HAVE_WIN32:
    NIF_ICON = _notify_const("NIF_ICON")
    NIF_MESSAGE = _notify_const("NIF_MESSAGE")
    NIF_TIP = _notify_const("NIF_TIP")
    NIF_INFO = _notify_const("NIF_INFO")
    NIIF_INFO = _notify_const("NIIF_INFO")
    NIM_ADD = _notify_const("NIM_ADD")
    NIM_DELETE = _notify_const("NIM_DELETE")
    NIM_MODIFY = _notify_const("NIM_MODIFY")

IDM_OPEN_WEB = 1001
IDM_COPY_URL = 1002
IDM_STATUS = 1003
IDM_SEPARATOR = 0
IDM_EXIT = 1004
IDM_IFACE_BASE = 2000  # Connection-URL menu items: IDM_IFACE_BASE + index


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
    """Convert a PIL RGBA image to a Windows HICON handle.

    Uses a 32-bit DIBSection (so alpha is respected) plus a 1-bit AND mask
    derived from the alpha channel. This renders cleanly on Windows 8.1+
    (including the small 16px tray size).
    """
    if not HAVE_WIN32:
        raise RuntimeError("pywin32 is required on Windows")

    import ctypes
    from ctypes import wintypes

    if pil_image.mode != "RGBA":
        pil_image = pil_image.convert("RGBA")

    w, h = pil_image.size
    if w <= 0 or h <= 0:
        raise ValueError("icon image must be non-empty")

    rgba = pil_image.tobytes()  # tightly packed RGBA rows
    stride = ((w * 4 + 3) // 4) * 4

    # BGRA pixel buffer with DWORD-aligned stride
    bgra = bytearray(stride * h)
    for y in range(h):
        src = y * w * 4
        dst = y * stride
        for x in range(w):
            r, g, b, a = rgba[src], rgba[src + 1], rgba[src + 2], rgba[src + 3]
            bgra[dst] = b
            bgra[dst + 1] = g
            bgra[dst + 2] = r
            bgra[dst + 3] = a
            src += 4
            dst += 4

    # 1-bit AND mask: bit set => transparent
    mask_stride = ((w + 31) // 32) * 4
    and_mask = bytearray(mask_stride * h)
    for y in range(h):
        src = y * w * 4
        for x in range(w):
            if rgba[src + 3] < 128:
                byte_idx = y * mask_stride + x // 8
                and_mask[byte_idx] |= 0x80 >> (x % 8)
            src += 4

    gdi32 = ctypes.windll.gdi32
    user32 = ctypes.windll.user32

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", wintypes.BOOL),
            ("xHotspot", wintypes.DWORD),
            ("yHotspot", wintypes.DWORD),
            ("hbmMask", wintypes.HBITMAP),
            ("hbmColor", wintypes.HBITMAP),
        ]

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h  # negative => top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    hdc = win32gui.GetDC(0)
    try:
        bits = ctypes.c_void_p()
        hbm_color = gdi32.CreateDIBSection(
            hdc,
            ctypes.byref(bmi),
            0,  # DIB_RGB_COLORS
            ctypes.byref(bits),
            None,
            0,
        )
        if not hbm_color or not bits:
            raise ctypes.WinError()
        ctypes.memmove(bits, bytes(bgra), len(bgra))

        hbm_mask = gdi32.CreateBitmap(w, h, 1, 1, None)
        if not hbm_mask:
            gdi32.DeleteObject(hbm_color)
            raise ctypes.WinError()
        try:
            n = gdi32.SetBitmapBits(hbm_mask, len(and_mask), bytes(and_mask))
            if n != len(and_mask):
                raise ctypes.WinError()

            ii = ICONINFO()
            ii.fIcon = True
            ii.hbmMask = hbm_mask
            ii.hbmColor = hbm_color
            hicon = user32.CreateIconIndirect(ctypes.byref(ii))
            if not hicon:
                raise ctypes.WinError()
            return hicon
        finally:
            # CreateIconIndirect copies the bitmaps into the icon, so the
            # source DIB/mask can be released immediately after creation.
            gdi32.DeleteObject(hbm_mask)
            gdi32.DeleteObject(hbm_color)
    finally:
        win32gui.ReleaseDC(0, hdc)


# ---------------------------------------------------------------------------
# Network interface discovery
# ---------------------------------------------------------------------------
def _ps_get_interfaces() -> list[dict]:
    """Discover IPv4 interfaces via PowerShell (Windows 8+)."""
    interfaces: list[dict] = []
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
                "Where-Object { $_.IPAddress -ne '127.0.0.1' } | "
                "Select-Object IPAddress, InterfaceAlias | "
                "ConvertTo-Json -Compress",
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
                ip = str(item.get("IPAddress", "")).strip()
                if ip:
                    interfaces.append(
                        {"name": str(item.get("InterfaceAlias", "Unknown")), "ip": ip}
                    )
    except Exception:
        logger.debug("PowerShell interface discovery failed", exc_info=True)
    return interfaces


def _ipconfig_get_interfaces() -> list[dict]:
    """Fallback: parse ``ipconfig`` output (works on all Windows versions)."""
    interfaces: list[dict] = []
    try:
        result = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, timeout=10
        )
    except Exception:
        logger.debug("ipconfig failed", exc_info=True)
        return interfaces

    current_name = "Unknown"
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.endswith(":") and "adapter" in line.lower():
            current_name = line.rsplit("adapter", 1)[-1].strip().rstrip(":")
            continue
        if line.lower().startswith(("ipv4 address", "ip address")):
            ip = line.split(":", 1)[-1].strip()
            if ip and ip != "127.0.0.1":
                interfaces.append({"name": current_name, "ip": ip})
    return interfaces


def _socket_fallback() -> list[dict]:
    """Last-resort fallback: hostname resolution."""
    interfaces: list[dict] = []
    try:
        hostname = socket.gethostname()
        seen: set[str] = set()
        for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = sockaddr[0]
            if ip not in seen and ip != "127.0.0.1":
                seen.add(ip)
                interfaces.append({"name": hostname, "ip": ip})
    except Exception:
        logger.debug("socket fallback failed", exc_info=True)
    return interfaces


def get_network_interfaces() -> list[dict]:
    """Return a list of available IPv4 network interfaces.

    Each dict contains: name, ip. The first entry is always the
    "All Interfaces (0.0.0.0)" option so callers have a stable default.
    On a dual-NIC machine both adapters appear, which is exactly what the
    tray "Connection URLs" menu needs.
    """
    interfaces = _ps_get_interfaces()
    if not interfaces:
        interfaces = _ipconfig_get_interfaces()
    if not interfaces:
        interfaces = _socket_fallback()

    # Deduplicate by IP (e.g. when PowerShell and fallbacks overlap)
    seen: set[str] = set()
    unique: list[dict] = []
    for iface in interfaces:
        ip = iface["ip"]
        if ip in seen:
            continue
        seen.add(ip)
        unique.append(iface)

    if unique:
        return [{"name": "All Interfaces (0.0.0.0)", "ip": "0.0.0.0"}, *unique]
    return [{"name": "All Interfaces (0.0.0.0)", "ip": "0.0.0.0"}]


def _copy_text_to_clipboard(text: str) -> bool:
    """Copy text to the Windows clipboard; returns success."""
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:
        logger.debug("win32clipboard failed; trying clip.exe", exc_info=True)
    try:
        subprocess.run(
            ["clip.exe"],
            input=text,
            text=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        logger.debug("clip.exe failed", exc_info=True)
        return False


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
        self._interfaces: list[dict] = []

    @property
    def ready(self) -> bool:
        """True once the hidden tray window exists."""
        return bool(self._hwnd)

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

    def connection_urls(self) -> list[str]:
        """Return per-interface SSE URLs for this machine.

        With ``host=0.0.0.0`` the server listens on every NIC, so on a
        dual-network machine this yields one URL per adapter — clients on
        either network can connect using their own subnet's address.
        """
        urls: list[str] = []
        for iface in get_network_interfaces():
            ip = iface["ip"]
            if ip in ("0.0.0.0", "::"):
                continue
            urls.append(f"http://{ip}:{self._port}/sse")
        return urls

    def wait_ready(self, timeout: float = 10.0) -> None:
        """Block until the tray window exists (or the timeout elapses)."""
        deadline = time.monotonic() + timeout
        while not self.ready and time.monotonic() < deadline:
            time.sleep(0.05)

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

    def show_balloon(self, title: str, message: str) -> None:
        """Show a balloon notification (safe to call before the window exists)."""
        if not self.ready:
            logger.debug("Tray window not ready; balloon skipped: %s", title)
            return
        try:
            flags = (
                NIF_INFO
                | NIF_MESSAGE
                | NIF_ICON
                | NIF_TIP
            )
            nid = (
                self._hwnd,
                1,
                flags,
                WM_TRAYICON,
                self._hicon,
                "Windows-MCP",
                message,
                10000,  # min supported timeout (ms); Windows clamps below 10s
                title,
                NIIF_INFO,
            )
            win32gui.Shell_NotifyIcon(NIM_MODIFY, nid)
        except Exception:
            logger.warning("Failed to show balloon", exc_info=True)

    # Backwards-compatible private alias
    _show_balloon = show_balloon

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
            time.sleep(0.1)

        # Cleanup
        self._remove_tray_icon()
        if self._hicon:
            try:
                win32gui.DestroyIcon(self._hicon)
            except Exception:
                pass
        if self._hwnd:
            try:
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                pass
            self._hwnd = None

    def _add_tray_icon(self) -> None:
        """Add the tray icon to the system tray."""
        flags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid = (
            self._hwnd,
            1,  # uid
            flags,
            WM_TRAYICON,
            self._hicon,
            f"Windows-MCP ({self._host}:{self._port})",
        )
        win32gui.Shell_NotifyIcon(NIM_ADD, nid)

    def _remove_tray_icon(self) -> None:
        """Remove the tray icon."""
        if not self._hwnd:
            return
        try:
            nid = (self._hwnd, 1)
            win32gui.Shell_NotifyIcon(NIM_DELETE, nid)
        except Exception:
            pass

    def _show_context_menu(self) -> None:
        """Show the right-click context menu."""
        menu = win32gui.CreatePopupMenu()
        self._interfaces = get_network_interfaces()

        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_OPEN_WEB, "Open Web Interface")
        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_COPY_URL, "Copy SSE URL")

        # Connection URLs for every detected NIC (dual-NIC friendly)
        submenu = win32gui.CreatePopupMenu()
        for i, iface in enumerate(self._interfaces):
            ip = iface["ip"]
            label = f"{iface['name']} ({ip})" if ip != "0.0.0.0" else iface["name"]
            win32gui.AppendMenu(submenu, win32con.MF_STRING, IDM_IFACE_BASE + i, label)
        win32gui.AppendMenu(menu, win32con.MF_POPUP, submenu, "Connection URLs")

        win32gui.AppendMenu(
            menu,
            win32con.MF_STRING | win32con.MF_GRAYED,
            IDM_STATUS,
            f"SSE: {self.sse_url}",
        )
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, IDM_SEPARATOR, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, IDM_EXIT, "Stop Server and Exit")

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
        elif cmd == IDM_COPY_URL:
            self._copy_url(self.sse_url)
        elif cmd == IDM_EXIT:
            self._do_exit()
        elif IDM_IFACE_BASE <= cmd < IDM_IFACE_BASE + 100:
            idx = cmd - IDM_IFACE_BASE
            if 0 <= idx < len(self._interfaces):
                ip = self._interfaces[idx]["ip"]
                if ip in ("0.0.0.0", "::"):
                    url = self.sse_url
                else:
                    url = f"http://{ip}:{self._port}/sse"
                copied = _copy_text_to_clipboard(url)
                if copied:
                    self.show_balloon("URL Copied", f"{url}\n已复制到剪贴板，可直接粘贴到 MCP 客户端配置。")
                else:
                    self.show_balloon("Connection URL", url)

        win32gui.DestroyMenu(menu)

    def _copy_url(self, url: str) -> None:
        """Copy a URL to the clipboard and confirm with a balloon."""
        if _copy_text_to_clipboard(url):
            self.show_balloon("URL Copied", f"{url}\n已复制到剪贴板。")
        else:
            self.show_balloon("SSE URL", url)

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
