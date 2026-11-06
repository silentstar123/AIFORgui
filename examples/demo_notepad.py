# -*- coding: utf-8 -*-
"""End-to-end smoke test: place Notepad on the last screen, type, OCR it back.

Run from the repository root:
    python plugins/gui-operator/examples/demo_notepad.py
It starts Notepad, moves it to the right-most monitor, types one line, captures
that screen, and checks the text appears in OCR output.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gui_operator_mcp import tools, win  # noqa: E402

TEXT = "你好，gui-operator"


def main() -> int:
    screens = tools.screen_list()["screens"]
    target = screens[-1]
    subprocess.Popen(["notepad.exe"])
    time.sleep(1.5)

    windows = tools.window_list()["windows"]
    notepad = next((item for item in windows if "记事本" in item["title"] or "Notepad" in item["title"]), None)
    if not notepad:
        print("notepad window not found")
        return 1

    win.foreground(notepad["hwnd"])
    time.sleep(0.3)
    tools.window_place(notepad["title"], target["left"] + 60, target["top"] + 60, 900, 600)
    time.sleep(0.5)
    tools.type_text(TEXT, enter=True)
    time.sleep(0.8)

    data, meta = tools.screenshot(target["index"])
    hit = any("gui-operator" in text or "你好" in text for text in meta["texts"])
    print({"screen": target["index"], "png": len(data), "hit": hit,
           "texts": meta["texts"][:10]})
    subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], capture_output=True)
    return 0 if hit else 2


if __name__ == "__main__":
    raise SystemExit(main())
