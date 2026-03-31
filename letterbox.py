"""Letterbox Overlay — 활성 창 뒤에 검정 오버레이를 배치하여 레터박스 효과를 만드는 프로그램."""

import ctypes
import ctypes.wintypes as wintypes
import tkinter as tk
import os
import re
import unicodedata

# Win API constants
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080

VK_D = 0x44
VK_CONTROL = 0xA2
VK_MENU = 0xA4  # Alt

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

user32 = ctypes.windll.user32


VERSION = "0.1.0"

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
        self.active = False
        self.overlay_visible = False

        self._build_banner()

        # tkinter overlay window
        self.root = tk.Tk()
        self.root.title("LetterboxOverlay")
        self.root.overrideredirect(True)
        self.root.configure(bg="black")
        self.root.geometry("800x600+100+1300")
        self.root.withdraw()

        self.root.update_idletasks()
        self.overlay_hwnd = int(self.root.frame(), 16)

        ex_style = user32.GetWindowLongW(self.overlay_hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            self.overlay_hwnd, GWL_EXSTYLE,
            ex_style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        )

        self._key_was_down = False
        self._last_fg = None

        self.root.after(16, self._poll)

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

        ctypes.windll.kernel32.SetConsoleTitleW("⚪ 대기")

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

    # ── 핫키 ──

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
                    # 오버레이 클릭됨 → 대상 창으로 포커스 복귀
                    user32.SetForegroundWindow(self.target_hwnd)
                elif fg != self.target_hwnd and fg != self._last_fg:
                    # 다른 창이 포커스 → 오버레이 숨김
                    self._last_fg = fg
                    self._hide_overlay()
                else:
                    if fg == self.target_hwnd and not self.overlay_visible:
                        self._last_fg = fg
                        self._show_overlay()
                    elif self.overlay_visible:
                        # 매 폴링마다 Z-order 강제 유지
                        self._enforce_zorder()

        self.root.after(16, self._poll)

    # ── 토글 ──

    def _toggle(self):
        if self.active:
            self._deactivate()
        else:
            self._activate()

    def _activate(self):
        fg = user32.GetForegroundWindow()
        if not fg or fg == self.overlay_hwnd:
            return
        self.target_hwnd = fg
        self.active = True
        self._show_overlay()

        title = self._get_window_title(fg)
        self._update_row("status", f"   {C_GREEN}● ON{C_RESET}")
        self._update_row("target", f"   {C_WHITE}  대상: {title} ({fg:#x}){C_RESET}")
        ctypes.windll.kernel32.SetConsoleTitleW(f"🟢 {title} ({fg:#x})")

    def _deactivate(self):
        self.active = False
        self.target_hwnd = None
        self._hide_overlay()

        self._update_row("status", f"   {C_DIM}○ 대기 중{C_RESET}")
        self._update_row("target", f"   {C_DIM}  대상: 없음{C_RESET}")
        ctypes.windll.kernel32.SetConsoleTitleW("⚪ 대기")

    # ── 오버레이 ──

    def _enforce_zorder(self):
        """오버레이를 대상 창 바로 뒤에 유지."""
        user32.SetWindowPos(
            self.overlay_hwnd, self.target_hwnd,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )

    def _show_overlay(self):
        if not self.target_hwnd:
            return
        self.overlay_visible = True
        # Z-order 배치 + 표시를 한 번에 — deiconify 깜빡임 방지
        user32.SetWindowPos(
            self.overlay_hwnd, self.target_hwnd,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

    def _hide_overlay(self):
        self.overlay_visible = False
        user32.SetWindowPos(
            self.overlay_hwnd, 0,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_HIDEWINDOW,
        )


    # ── 실행 ──

    def run(self):
        import signal
        self._quit = False

        def _on_sigint(sig, frame):
            self._quit = True

        signal.signal(signal.SIGINT, _on_sigint)

        def _check_quit():
            if self._quit:
                self.root.destroy()
                return
            self.root.after(200, _check_quit)

        self.root.after(200, _check_quit)

        try:
            self.root.mainloop()
        finally:
            pass


if __name__ == "__main__":
    app = LetterboxOverlay()
    app.run()
