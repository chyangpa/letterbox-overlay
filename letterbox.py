"""Letterbox Overlay — 활성 창 뒤에 검정 오버레이를 배치하여 레터박스 효과를 만드는 프로그램."""

import ctypes
import ctypes.wintypes as wintypes
import time
import os
import re
import unicodedata

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

VK_D = 0x44
VK_CONTROL = 0xA2
VK_MENU = 0xA4  # Alt

MONITOR_DEFAULTTONEAREST = 2

# Win32 window creation constants
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WM_DESTROY = 0x0002
COLOR_BACKGROUND = 1

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32

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


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('rcMonitor', wintypes.RECT),
        ('rcWork', wintypes.RECT),
        ('dwFlags', wintypes.DWORD),
    ]


VERSION = "0.2.0"

# ── ANSI 색상 ──
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_DIM    = "\033[2m"
C_CYAN   = "\033[36m"
C_GREEN  = "\033[32m"
C_YELLOW = "\033[33m"
C_WHITE  = "\033[37m"
C_RED    = "\033[31m"


def vlen(s):
    clean = re.sub(r'\033\[[0-9;]*m', '', s)
    w = 0
    for c in clean:
        w += 2 if unicodedata.east_asian_width(c) in ('F', 'W') else 1
    return w


def pad(s, width):
    return s + ' ' * max(0, width - vlen(s))


class LetterboxOverlay:
    def __init__(self):
        self.target_hwnd = None
        self.target_was_topmost = False
        self.active = False
        self.overlay_visible = False

        self._build_banner()
        self._create_overlay_window()

        self._key_was_down = False
        self._last_fg = None

    # ── 오버레이 창 생성 (Win32 직접) ──

    def _create_overlay_window(self):
        hInstance = kernel32.GetModuleHandleW(None)

        # 검정 브러시
        self._black_brush = gdi32.CreateSolidBrush(0x00000000)  # RGB(0,0,0)

        # 커서
        self._arrow_cursor = user32.LoadCursorW(None, wintypes.LPCWSTR(32512))

        # 윈도우 프로시저
        WM_SETCURSOR = 0x0020
        def _wndproc(hwnd, msg, wp, lp):
            if msg == WM_SETCURSOR:
                user32.SetCursor(self._arrow_cursor)
                return 1
            return user32.DefWindowProcW(hwnd, msg, wp, lp)
        self._wndproc = WNDPROC(_wndproc)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = CS_HREDRAW | CS_VREDRAW
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hInstance
        wc.hCursor = user32.LoadCursorW(None, wintypes.LPCWSTR(32512))  # IDC_ARROW
        wc.hbrBackground = self._black_brush
        wc.lpszClassName = "LetterboxOverlayClass"

        user32.RegisterClassExW(ctypes.byref(wc))

        # 프로토타입: 800x600
        self.overlay_hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,  # exStyle
            "LetterboxOverlayClass",                # className
            "LetterboxOverlay",                     # windowName
            WS_POPUP,                               # style (타이틀바 없음, 숨김 상태)
            100, 100, 800, 600,                     # x, y, w, h
            None, None, hInstance, None,
        )

    # ── 터미널 배너 ──

    def _build_banner(self):
        term_w = os.get_terminal_size().columns
        self.TW = term_w - 2
        L = self.TW // 2
        R = self.TW - L - 1

        def row(left="", right=""):
            return f"│{pad(left, L)}{C_DIM}│{C_RESET}{pad(right, R)}│"

        self._row_fn = row
        self._L = L
        self._R = R

        self.banner_rows = [
            (None,     "", ""),
            (None,     f"   {C_WHITE}{C_BOLD}Letterbox Overlay{C_RESET}",
                       f" {C_WHITE}키 바인딩{C_RESET}"),
            (None,     f"   {C_DIM}[ v{VERSION} ]{C_RESET}",
                       f" {C_DIM}{'─' * (R - 1)}{C_RESET}"),
            (None,     "", f" {C_YELLOW}Ctrl+Alt+D{C_RESET} {C_DIM}·{C_RESET} 토글 ON/OFF"),
            ("status", f"   {C_DIM}○ 대기 중{C_RESET}",
                       ""),
            ("target", f"   {C_DIM}  대상: 없음{C_RESET}",
                       ""),
            (None,     "", ""),
        ]

        self.row_offset = {}
        total = len(self.banner_rows) + 2
        for i, (rid, _, _) in enumerate(self.banner_rows):
            if rid:
                self.row_offset[rid] = total - 1 - i

        title = f" Letterbox Overlay v{VERSION} "
        top = f"╭───{C_CYAN}{C_BOLD}{title}{C_RESET}{'─' * (self.TW - vlen(title) - 3)}╮"

        print(top)
        for _, left_text, right_text in self.banner_rows:
            print(row(left_text, right_text))
        print(f"╰{'─' * self.TW}╯")

        kernel32.SetConsoleTitleW("⚪ 대기")

    def _update_row(self, rid, left, right=None):
        up = self.row_offset[rid]
        if right is None:
            for r_id, _, r_right in self.banner_rows:
                if r_id == rid:
                    right = r_right
                    break
        line = self._row_fn(left, right)
        print(f"\033[{up}A\r{line}\033[{up}B\r", end="", flush=True)

    def _get_window_title(self, hwnd):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    # ── 폴링 ──

    def _poll(self):
        # 핫키 체크: Ctrl+Alt+D (edge detection)
        ctrl = user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
        alt = user32.GetAsyncKeyState(VK_MENU) & 0x8000
        d = user32.GetAsyncKeyState(VK_D) & 0x8000
        key_down = bool(ctrl and alt and d)

        if key_down and not self._key_was_down:
            self._toggle()
        self._key_was_down = key_down

        # 포커스 변경 감지 + Z-order 유지
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

    def _activate(self):
        fg = user32.GetForegroundWindow()
        if not fg or fg == self.overlay_hwnd:
            return
        self.target_hwnd = fg
        self.target_was_topmost = self._is_topmost(fg)
        self.active = True
        self._show_overlay()

        title = self._get_window_title(fg)
        self._update_row("status", f"   {C_GREEN}● ON{C_RESET}")
        self._update_row("target", f"   {C_WHITE}  대상: {title} ({fg:#x}){C_RESET}")
        kernel32.SetConsoleTitleW(f"🟢 {title} ({fg:#x})")

    def _deactivate(self):
        self.active = False
        self._hide_overlay()
        self.target_hwnd = None
        self.target_was_topmost = False

        self._update_row("status", f"   {C_DIM}○ 대기 중{C_RESET}")
        self._update_row("target", f"   {C_DIM}  대상: 없음{C_RESET}")
        kernel32.SetConsoleTitleW("⚪ 대기")

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
        # 1. 오버레이 TOPMOST + 모니터 전체 크기
        x, y, w, h = self._get_monitor_rect(self.target_hwnd)
        user32.SetWindowPos(
            self.overlay_hwnd, HWND_TOPMOST,
            x, y, w, h,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        # 2. 대상 창 TOPMOST (마지막 → 오버레이 위)
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
        """오버레이 창의 Windows 메시지 처리."""
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), self.overlay_hwnd, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def run(self):
        try:
            while True:
                self._pump_messages()
                self._poll()
                time.sleep(0.016)
        except KeyboardInterrupt:
            pass
        finally:
            if self.active:
                self._deactivate()
            if self._black_brush:
                gdi32.DeleteObject(self._black_brush)


if __name__ == "__main__":
    app = LetterboxOverlay()
    app.run()
