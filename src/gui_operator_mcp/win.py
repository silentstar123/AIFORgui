# -*- coding: utf-8 -*-
"""Windows input primitives: cursor, clicks, keys, clipboard paste, windows."""
from __future__ import annotations

import ctypes
import time
from typing import Any

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

VK = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
}
for _i in range(1, 13):
    VK[f"f{_i}"] = 0x6F + _i
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK[_c] = ord(_c.upper())
for _d in "0123456789":
    VK[_d] = ord(_d)


def dpi_aware() -> None:
    """Physical pixels everywhere; without this every coordinate drifts at 125%."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwarenessContext(
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def move(x: int, y: int) -> None:
    import win32api

    win32api.SetCursorPos((int(x), int(y)))


def click(x: int, y: int, *, double: bool = False, button: str = "left") -> None:
    import win32api
    import win32con

    down, up = ((win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP)
                if button == "left" else
                (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP))
    move(x, y)
    time.sleep(0.03)
    for _ in range(2 if double else 1):
        win32api.mouse_event(down, 0, 0, 0, 0)
        win32api.mouse_event(up, 0, 0, 0, 0)
        if double:
            time.sleep(0.08)


def parse_combo(combo: str) -> list[int]:
    keys = [part.strip().lower() for part in combo.replace("+", " ").split() if part.strip()]
    if not keys:
        raise ValueError("empty key combination")
    codes = []
    for key in keys:
        if key not in VK:
            raise ValueError(f"unknown key {key!r}")
        codes.append(VK[key])
    return codes


def key_combo(combo: str) -> None:
    import win32api
    import win32con

    codes = parse_combo(combo)
    for code in codes:
        win32api.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 0)


def type_text(text: str, *, enter: bool = False) -> None:
    """Paste through the clipboard so IMEs and Chinese text behave like a user paste."""
    import win32clipboard
    import win32con

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()
    time.sleep(0.03)
    key_combo("ctrl+v")
    if enter:
        time.sleep(0.05)
        key_combo("enter")


def scroll(dy: int, *, x: int | None = None, y: int | None = None) -> None:
    import win32api
    import win32con

    if x is not None and y is not None:
        move(x, y)
    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, int(dy) * 120, 0)


def list_windows() -> list[dict[str, Any]]:
    import win32gui

    windows: list[dict[str, Any]] = []

    def collect(hwnd: int, _param: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return True
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if right - left <= 1 or bottom - top <= 1:
            return True
        windows.append({
            "hwnd": hwnd,
            "title": title,
            "rect": {"left": left, "top": top, "width": right - left, "height": bottom - top},
        })
        return True

    win32gui.EnumWindows(collect, None)
    return windows


def foreground(hwnd: int) -> bool:
    import win32gui

    try:
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False
