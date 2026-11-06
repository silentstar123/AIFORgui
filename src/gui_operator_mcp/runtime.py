# -*- coding: utf-8 -*-
"""Global stop switch: Ctrl+Alt+Q sets an event that every mutating action checks."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import threading

from .tools import ToolError

STOP = threading.Event()
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
VK_Q = 0x51


def check() -> None:
    if STOP.is_set():
        raise ToolError("stopped by user (Ctrl+Alt+Q); call reset_stop to continue")


def reset() -> None:
    STOP.clear()


def stop() -> None:
    STOP.set()


def install_hotkey() -> bool:
    """Register a process-wide hotkey; return False when another app owns it."""

    def loop() -> None:
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_Q):
            return
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY:
                STOP.set()

    threading.Thread(target=loop, daemon=True, name="gui-operator-hotkey").start()
    return True
