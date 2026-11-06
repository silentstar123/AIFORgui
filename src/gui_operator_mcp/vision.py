# -*- coding: utf-8 -*-
"""Screen geometry, capture, Chinese OCR, and text matching."""
from __future__ import annotations

import ctypes
from typing import Any

import mss
import numpy as np

_ENGINE = None


def monitors() -> list[dict[str, Any]]:
    """Physical-pixel rectangles and per-monitor DPI, including virtual displays."""
    import win32api

    result: list[dict[str, Any]] = []
    for handle, _hdc, _rect in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(handle)
        left, top, right, bottom = info["Monitor"]
        dpi = _dpi_for(handle)
        result.append({
            "index": len(result) + 1,
            "left": left,
            "top": top,
            "width": right - left,
            "height": bottom - top,
            "primary": bool(info.get("Flags", 0) & 1),
            "dpi": dpi,
        })
    result.sort(key=lambda item: (item["left"], item["top"]))
    for index, item in enumerate(result, start=1):
        item["index"] = index
    return result


def _dpi_for(handle) -> int:
    try:
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        ctypes.windll.shcore.GetDpiForMonitor(handle, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
        return int(dpi_x.value) or 96
    except Exception:
        return 96


def monitor(index: int) -> dict[str, Any]:
    items = monitors()
    if not items:
        raise RuntimeError("no monitors reported")
    if index < 1 or index > len(items):
        raise ValueError(f"screen {index} out of range 1..{len(items)}")
    return items[index - 1]


def capture(index: int = 1,
            region: tuple[int, int, int, int] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Capture a monitor, or a local rectangle inside it.

    ``region`` is (x, y, width, height) in that monitor's pixels. The returned
    screen box keeps global ``left``/``top`` so callers can add OCR centers.
    """
    box = monitor(index)
    left, top, width, height = box["left"], box["top"], box["width"], box["height"]
    if region is not None:
        x, y, w, h = (int(value) for value in region)
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(1, min(w, width - x))
        h = max(1, min(h, height - y))
        left, top, width, height = box["left"] + x, box["top"] + y, w, h
    grab = {"left": left, "top": top, "width": width, "height": height}
    with mss.mss() as grabber:
        shot = grabber.grab(grab)
    image = np.array(shot)[:, :, :3]
    return image, {**box, "left": left, "top": top, "width": width, "height": height}


def encode_png(image: np.ndarray) -> bytes:
    import cv2

    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return buffer.tobytes()


def ocr(image: np.ndarray, *, max_side: int = 1280) -> list[dict[str, Any]]:
    """OCR every text box; coordinates are local to the captured image.

    Downscaling to ``max_side`` cuts CPU time roughly in half on 1080p screens;
    boxes are scaled back to original pixels.
    """
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _ENGINE = RapidOCR()
    scale = 1.0
    height, width = image.shape[:2]
    longest = max(height, width)
    if max_side > 0 and longest > max_side:
        import cv2

        scale = max_side / float(longest)
        image = cv2.resize(image, (int(width * scale), int(height * scale)),
                           interpolation=cv2.INTER_AREA)
    result, _elapsed = _ENGINE(image)
    boxes: list[dict[str, Any]] = []
    for item in result or []:
        points, text, score = item[0], item[1], item[2]
        if not str(text).strip():
            continue
        xs = [point[0] / scale for point in points]
        ys = [point[1] / scale for point in points]
        boxes.append({
            "text": str(text),
            "score": round(float(score), 3),
            "left": int(min(xs)),
            "top": int(min(ys)),
            "width": int(max(xs) - min(xs)),
            "height": int(max(ys) - min(ys)),
            "center": [int(sum(xs) / len(xs)), int(sum(ys) / len(ys))],
        })
    return boxes


def match(text: str, boxes: list[dict[str, Any]], *, exact: bool = False) -> list[dict[str, Any]]:
    needle = "".join((text or "").split())
    if not needle:
        return []
    found = []
    for box in boxes:
        haystack = "".join(box["text"].split())
        hit = haystack == needle if exact else needle in haystack
        if hit:
            found.append(box)
    return found


def pick(found: list[dict[str, Any]], nth: int = 0) -> dict[str, Any]:
    if not found:
        raise LookupError("text not found on screen")
    if nth < 0 or nth >= len(found):
        raise LookupError(f"only {len(found)} match(es), nth={nth} out of range")
    return found[nth]


def to_global(box: dict[str, Any], screen: dict[str, Any]) -> tuple[int, int]:
    x, y = box["center"]
    return screen["left"] + int(x), screen["top"] + int(y)
