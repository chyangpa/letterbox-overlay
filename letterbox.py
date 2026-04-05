"""Letterbox Overlay — 활성 창 외 영역을 검정으로 채우는 프로그램."""

__version__ = "1.2.0"

import ctypes
import ctypes.wintypes as wintypes
import time
import os

# Win API constants
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

VK_C = 0x43
VK_D = 0x44
VK_CONTROL = 0xA2
VK_MENU = 0xA4  # Alt

MONITOR_DEFAULTTONEAREST = 2

# Win32 window creation constants
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
WS_POPUP = 0x80000000
WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1

# Tray icon constants
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_MESSAGE = 0x00000001
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
WM_RBUTTONUP = 0x0205
TPM_RIGHTALIGN = 0x0008
TPM_BOTTOMALIGN = 0x0020
MF_STRING = 0x00000000

IDM_EXIT = 1001

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32

# 다크모드 메뉴 활성화 (Windows 10 1903+)
try:
    uxtheme = ctypes.windll.uxtheme
    _SetPreferredAppMode = uxtheme[135]
    _SetPreferredAppMode.argtypes = [ctypes.c_int]
    _SetPreferredAppMode(1)
    _FlushMenuThemes = uxtheme[136]
    _FlushMenuThemes()
except Exception:
    pass

# SetWindowPos argtypes 설정 (64비트에서 HWND 제대로 전달)
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint,
]
user32.SetWindowPos.restype = wintypes.BOOL

HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)

user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_long

user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = wintypes.HANDLE

user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.LoadImageW.restype = wintypes.HANDLE

# Window procedure callback type
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM,
)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('style', ctypes.c_uint),
        ('lpfnWndProc', WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HANDLE),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
        ('hIconSm', wintypes.HICON),
    ]


shell32 = ctypes.windll.shell32
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.c_void_p]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL


NIF_INFO = 0x00000010
NIIF_NONE = 0x00000000


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('hWnd', wintypes.HWND),
        ('uID', ctypes.c_uint),
        ('uFlags', ctypes.c_uint),
        ('uCallbackMessage', ctypes.c_uint),
        ('hIcon', wintypes.HICON),
        ('szTip', wintypes.WCHAR * 128),
        ('dwState', wintypes.DWORD),
        ('dwStateMask', wintypes.DWORD),
        ('szInfo', wintypes.WCHAR * 256),
        ('uVersion', ctypes.c_uint),
        ('szInfoTitle', wintypes.WCHAR * 64),
        ('dwInfoFlags', wintypes.DWORD),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('rcMonitor', wintypes.RECT),
        ('rcWork', wintypes.RECT),
        ('dwFlags', wintypes.DWORD),
    ]


class LetterboxOverlay:
    def __init__(self):
        self.target_hwnd = None
        self.target_was_topmost = False
        self.active = False
        self.overlay_visible = False
        self._quit_requested = False

        self._create_overlay_window()
        self._create_tray_icon()

        self._key_was_down = False
        self._center_key_was_down = False
        self._centered = False
        self._original_pos = None
        self._last_fg = None

    # ── 오버레이 창 생성 (Win32 직접) ──

    def _create_overlay_window(self):
        hInstance = kernel32.GetModuleHandleW(None)

        self._black_brush = gdi32.CreateSolidBrush(0x00000000)
        self._arrow_cursor = user32.LoadCursorW(None, wintypes.LPCWSTR(32512))

        WM_SETCURSOR = 0x0020
        def _wndproc(hwnd, msg, wp, lp):
            if msg == WM_SETCURSOR:
                user32.SetCursor(self._arrow_cursor)
                return 1
            if msg == WM_TRAYICON:
                if lp == WM_RBUTTONUP:
                    self._show_tray_menu()
                    return 0
            if msg == WM_COMMAND:
                cmd_id = wp & 0xFFFF
                if cmd_id == IDM_EXIT:
                    self._quit_requested = True
                    return 0
            return user32.DefWindowProcW(hwnd, msg, wp, lp)
        self._wndproc = WNDPROC(_wndproc)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = CS_HREDRAW | CS_VREDRAW
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hInstance
        wc.hCursor = self._arrow_cursor
        wc.hbrBackground = self._black_brush
        wc.lpszClassName = "LetterboxOverlayClass"

        user32.RegisterClassExW(ctypes.byref(wc))

        self.overlay_hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            "LetterboxOverlayClass",
            "LetterboxOverlay",
            WS_POPUP,
            0, 0, 1, 1,
            None, None, hInstance, None,
        )

    # ── 트레이 아이콘 ──

    def _create_tray_icon(self):
        base = os.path.dirname(os.path.abspath(__file__))
        self._icon_on = user32.LoadImageW(
            None, os.path.join(base, "activated.ico"), 1,
            16, 16, 0x00000010,
        )
        self._icon_off = user32.LoadImageW(
            None, os.path.join(base, "deactivated.ico"), 1,
            16, 16, 0x00000010,
        )

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.overlay_hwnd
        nid.uID = 1
        nid.uFlags = NIF_ICON | NIF_TIP | NIF_MESSAGE
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._icon_off
        nid.szTip = "Letterbox Overlay\n활성화(Ctrl+Alt+D)"
        self._nid = nid

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))

        # 시작 알림
        self._nid.uFlags |= NIF_INFO
        self._nid.szInfoTitle = "Letterbox Overlay"
        self._nid.szInfo = "트레이에서 실행 중\nCtrl+Alt+D로 활성화"
        self._nid.dwInfoFlags = NIIF_NONE
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))
        self._nid.uFlags &= ~NIF_INFO

    def _update_tray(self, icon=None, target_title=None):
        if icon:
            self._nid.hIcon = icon
        if target_title:
            display = target_title[:20] + "…" if len(target_title) > 20 else target_title
            self._nid.szTip = f"Letterbox Overlay\n{display}\n비활성화(Ctrl+Alt+D)"
        else:
            self._nid.szTip = "Letterbox Overlay\n활성화(Ctrl+Alt+D)"
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def _remove_tray_icon(self):
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))

    def _show_tray_menu(self):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, IDM_EXIT, "종료")

        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))

        user32.SetForegroundWindow(self.overlay_hwnd)
        user32.TrackPopupMenu(
            menu, TPM_RIGHTALIGN | TPM_BOTTOMALIGN,
            pt.x, pt.y, 0, self.overlay_hwnd, None,
        )
        user32.DestroyMenu(menu)

    # ── 폴링 ──

    def _poll(self):
        ctrl = user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
        alt = user32.GetAsyncKeyState(VK_MENU) & 0x8000
        d = user32.GetAsyncKeyState(VK_D) & 0x8000
        key_down = bool(ctrl and alt and d)

        if key_down and not self._key_was_down:
            self._toggle()
        self._key_was_down = key_down

        if self.active:
            if not user32.IsWindow(self.target_hwnd):
                self._deactivate()
            else:
                fg = user32.GetForegroundWindow()
                if fg == self.overlay_hwnd:
                    user32.SetForegroundWindow(self.target_hwnd)
                elif fg != self.target_hwnd and fg != self._last_fg:
                    self._last_fg = fg
                    self._hide_overlay()
                else:
                    if fg == self.target_hwnd and not self.overlay_visible:
                        self._last_fg = fg
                        self._show_overlay()
                    elif self.overlay_visible:
                        self._enforce_zorder()

    # ── 토글 ──

    def _toggle(self):
        if self.active:
            self._deactivate()
        else:
            self._activate()

    def _is_topmost(self, hwnd):
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        return bool(ex_style & WS_EX_TOPMOST)

    def _get_window_title(self, hwnd):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    def _activate(self):
        fg = user32.GetForegroundWindow()
        if not fg or fg == self.overlay_hwnd:
            return
        self.target_hwnd = fg
        self.target_was_topmost = self._is_topmost(fg)
        self.active = True
        self._center_window()
        self._show_overlay()

        title = self._get_window_title(fg)
        self._update_tray(icon=self._icon_on, target_title=title)

    def _toggle_center(self):
        if self._centered:
            self._restore_window_pos()
        else:
            self._center_window()

    def _center_window(self):
        if not self.target_hwnd:
            return
        rect = wintypes.RECT()
        user32.GetWindowRect(self.target_hwnd, ctypes.byref(rect))
        self._original_pos = (rect.left, rect.top)
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top
        mx, my, mw, mh = self._get_monitor_rect(self.target_hwnd)
        cx = mx + (mw - win_w) // 2
        cy = my + (mh - win_h) // 2
        user32.SetWindowPos(
            self.target_hwnd, HWND_TOPMOST,
            cx, cy, 0, 0,
            SWP_NOSIZE | SWP_NOACTIVATE,
        )
        self._centered = True

    def _restore_window_pos(self):
        if not self.target_hwnd or not self._original_pos:
            return
        ox, oy = self._original_pos
        user32.SetWindowPos(
            self.target_hwnd, HWND_TOPMOST,
            ox, oy, 0, 0,
            SWP_NOSIZE | SWP_NOACTIVATE,
        )
        self._centered = False
        self._original_pos = None

    def _deactivate(self):
        if self._centered:
            self._restore_window_pos()
        self.active = False
        self._hide_overlay()
        self.target_hwnd = None
        self.target_was_topmost = False
        self._update_tray(icon=self._icon_off)

    # ── 오버레이 ──

    def _get_monitor_rect(self, hwnd):
        hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcMonitor
        return r.left, r.top, r.right - r.left, r.bottom - r.top

    def _enforce_zorder(self):
        user32.SetWindowPos(
            self.target_hwnd, HWND_TOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )

    def _show_overlay(self):
        if not self.target_hwnd:
            return
        self.overlay_visible = True
        x, y, w, h = self._get_monitor_rect(self.target_hwnd)
        user32.SetWindowPos(
            self.overlay_hwnd, HWND_TOPMOST,
            x, y, w, h,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        user32.SetWindowPos(
            self.target_hwnd, HWND_TOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )

    def _hide_overlay(self):
        self.overlay_visible = False
        if self.target_hwnd and user32.IsWindow(self.target_hwnd):
            if not self.target_was_topmost:
                user32.SetWindowPos(
                    self.target_hwnd, HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
        user32.SetWindowPos(
            self.overlay_hwnd, HWND_NOTOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_HIDEWINDOW,
        )

    # ── 실행 ──

    def _pump_messages(self):
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def run(self):
        try:
            while not self._quit_requested:
                self._pump_messages()
                self._poll()
                time.sleep(0.016)
        except KeyboardInterrupt:
            pass
        finally:
            if self.active:
                self._deactivate()
            self._remove_tray_icon()
            if self._black_brush:
                gdi32.DeleteObject(self._black_brush)


if __name__ == "__main__":
    import subprocess
    import sys

    if "--worker" in sys.argv:
        app = LetterboxOverlay()
        app.run()
    else:
        mutex = kernel32.CreateMutexW(None, True, "LetterboxOverlay_SingleInstance")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(mutex)
            raise SystemExit
        try:
            while True:
                child = subprocess.Popen([sys.executable, "--worker"])
                child.wait()
                if child.returncode == 0:
                    break  # 정상 종료
                time.sleep(1)  # 크래시 → 재시작
        finally:
            kernel32.CloseHandle(mutex)
