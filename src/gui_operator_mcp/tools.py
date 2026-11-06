# -*- coding: utf-8 -*-
"""Tool implementations shared by the MCP server and tests."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from . import vision, win

AUDIT: Path = Path(os.environ.get("GUI_OPERATOR_AUDIT")
                   or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "gui-operator" / "audit.jsonl")
EVIDENCE: Path = Path(os.environ.get("GUI_OPERATOR_EVIDENCE")
                      or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "gui-operator" / "evidence")
AUDIT_DAYS = int(os.environ.get("GUI_OPERATOR_AUDIT_DAYS", "30"))
_PUBLISH_KEYS = ("发布", "发表", "发送", "提交", "publish", "post", "send", "submit")


class ToolError(RuntimeError):
    """A tool failed for a user-visible reason; MCP reports it as an error result."""


def screen_list() -> dict[str, Any]:
    return {"screens": vision.monitors()}


def _region(value: Any) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ToolError("region must be [x, y, width, height]")
    return tuple(int(item) for item in value)


def screenshot(screen: int = 1, with_ocr: bool = True,
               region: list[int] | None = None) -> tuple[bytes, dict[str, Any]]:
    image, box = vision.capture(screen, _region(region))
    meta: dict[str, Any] = {
        "screen": screen,
        "width": box["width"],
        "height": box["height"],
        "left": box["left"],
        "top": box["top"],
        "dpi": box["dpi"],
    }
    if with_ocr:
        boxes = vision.ocr(image)
        meta["texts"] = [item["text"] for item in boxes][:80]
        meta["boxes"] = boxes[:200]
    return vision.encode_png(image), meta


def click_text(text: str, *, screen: int = 1, nth: int = 0, exact: bool = False,
               double: bool = False, dry_run: bool = False,
               region: list[int] | None = None) -> dict[str, Any]:
    from . import runtime

    runtime.check()
    image, box = vision.capture(screen, _region(region))
    boxes = vision.ocr(image)
    found = vision.match(text, boxes, exact=exact)
    target = vision.pick(found, nth)
    x, y = vision.to_global(target, box)
    evidence = None
    if not dry_run:
        if _is_publish(target["text"]):
            evidence = _save_evidence(screen, target["text"])
        win.click(x, y, double=double)
    return {
        "text": target["text"],
        "screen": screen,
        "x": x,
        "y": y,
        "matches": len(found),
        "nth": nth,
        "clicked": not dry_run,
        "evidence": evidence,
    }


def click_at(x: int, y: int, *, double: bool = False, dry_run: bool = False) -> dict[str, Any]:
    from . import runtime

    runtime.check()
    if not dry_run:
        win.click(x, y, double=double)
    return {"x": x, "y": y, "clicked": not dry_run}


def type_text(text: str, *, enter: bool = False) -> dict[str, Any]:
    from . import runtime

    runtime.check()
    win.type_text(text, enter=enter)
    return {"typed": len(text), "enter": enter}


def press_key(combo: str) -> dict[str, Any]:
    from . import runtime

    runtime.check()
    folded = "".join(combo.replace("+", " ").split()).lower()
    if "delete" in folded and "shift" in folded:
        raise ToolError("Shift+Delete bypasses the recycle bin; use recycle_paths instead")
    win.key_combo(combo)
    return {"keys": combo}


def scroll(dy: int, *, x: int | None = None, y: int | None = None) -> dict[str, Any]:
    from . import runtime

    runtime.check()
    win.scroll(dy, x=x, y=y)
    return {"scrolled": dy}


def wait_for_text(text: str, *, timeout: float = 10.0, screen: int = 1,
                  interval: float = 0.5, exact: bool = False,
                  region: list[int] | None = None) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.1, timeout)
    attempts = 0
    while True:
        attempts += 1
        image, box = vision.capture(screen, _region(region))
        found = vision.match(text, vision.ocr(image), exact=exact)
        if found:
            return {"found": True, "attempts": attempts,
                    "text": found[0]["text"], "center": found[0]["center"]}
        if time.monotonic() >= deadline:
            return {"found": False, "attempts": attempts}
        time.sleep(max(0.1, interval))


def window_list() -> dict[str, Any]:
    return {"windows": win.list_windows()}


def window_focus(title: str) -> dict[str, Any]:
    needle = "".join(title.split()).lower()
    for item in win.list_windows():
        if needle in "".join(item["title"].split()).lower():
            return {"ok": win.foreground(item["hwnd"]), "window": item}
    raise ToolError(f"window not found: {title!r}")


def window_place(title: str, x: int, y: int, width: int, height: int) -> dict[str, Any]:
    import win32gui

    needle = "".join(title.split()).lower()
    for item in win.list_windows():
        if needle in "".join(item["title"].split()).lower():
            win32gui.SetWindowPos(item["hwnd"], 0, x, y, width, height, 0x0040)
            return {"ok": True, "window": item, "rect": {"x": x, "y": y, "width": width, "height": height}}
    raise ToolError(f"window not found: {title!r}")


def _audit(entry: dict[str, Any]) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _is_publish(text: str) -> bool:
    folded = "".join(str(text).split()).lower()
    return any(key in folded for key in _PUBLISH_KEYS)


def _save_evidence(screen: int, text: str) -> str:
    image, _box = vision.capture(screen)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in text if ch.isalnum() or ch in "-_")[:20] or "action"
    path = EVIDENCE / f"{datetime.now():%Y%m%d-%H%M%S}-{safe}.png"
    path.write_bytes(vision.encode_png(image))
    return str(path)


def prune_audit(days: int | None = None) -> dict[str, int]:
    """Drop audit entries older than ``days`` (default 30); malformed lines are kept."""
    keep_days = AUDIT_DAYS if days is None else max(1, int(days))
    if not AUDIT.is_file():
        return {"kept": 0, "dropped": 0}
    cutoff = datetime.now().timestamp() - keep_days * 86400
    kept: list[str] = []
    dropped = 0
    for line in AUDIT.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
            stamp = datetime.fromisoformat(str(entry.get("at"))).timestamp()
        except Exception:
            kept.append(line)
            continue
        if stamp >= cutoff:
            kept.append(line)
        else:
            dropped += 1
    if dropped:
        temp = AUDIT.with_suffix(".tmp")
        temp.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        temp.replace(AUDIT)
    return {"kept": len(kept), "dropped": dropped}


def recycle_paths(paths: list[str]) -> dict[str, Any]:
    from . import recycle

    moved = recycle.recycle(paths)
    _audit({"at": datetime.now().isoformat(timespec="seconds"), "action": "recycle_paths",
            "paths": moved})
    return {"recycled": moved, "count": len(moved)}


def _step(action: str, params: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    from . import runtime

    if action in ("click_text", "click_at", "type_text", "press_key", "scroll", "window_place"):
        runtime.check()
    if action == "screen_list":
        return screen_list()
    if action == "screenshot":
        _png, meta = screenshot(int(params.get("screen", 1)),
                                bool(params.get("with_ocr", True)),
                                region=params.get("region"))
        return {"screen": meta["screen"], "texts": meta.get("texts", [])[:40],
                "width": meta["width"], "height": meta["height"]}
    if action == "click_text":
        if dry_run:
            image, box = vision.capture(int(params.get("screen", 1)), _region(params.get("region")))
            found = vision.match(str(params["text"]), vision.ocr(image),
                                  exact=bool(params.get("exact", False)))
            target = vision.pick(found, int(params.get("nth", 0)))
            x, y = vision.to_global(target, box)
            return {"dryRun": True, "text": target["text"], "x": x, "y": y}
        return click_text(str(params["text"]), screen=int(params.get("screen", 1)),
                          nth=int(params.get("nth", 0)),
                          exact=bool(params.get("exact", False)),
                          double=bool(params.get("double", False)),
                          region=params.get("region"))
    if action == "click_at":
        if dry_run:
            return {"dryRun": True, "x": int(params["x"]), "y": int(params["y"])}
        return click_at(int(params["x"]), int(params["y"]),
                        double=bool(params.get("double", False)))
    if action == "type_text":
        if dry_run:
            return {"dryRun": True, "text": str(params["text"])}
        return type_text(str(params["text"]), enter=bool(params.get("enter", False)))
    if action == "press_key":
        if dry_run:
            return {"dryRun": True, "keys": str(params["combo"])}
        return press_key(str(params["combo"]))
    if action == "scroll":
        if dry_run:
            return {"dryRun": True, "dy": int(params["dy"])}
        return scroll(int(params["dy"]), x=params.get("x"), y=params.get("y"))
    if action == "wait_for_text":
        return wait_for_text(str(params["text"]), timeout=float(params.get("timeout", 10)),
                             screen=int(params.get("screen", 1)),
                             interval=float(params.get("interval", 0.5)),
                             exact=bool(params.get("exact", False)),
                             region=params.get("region"))
    if action == "window_list":
        return window_list()
    if action == "window_focus":
        return window_focus(str(params["title"]))
    if action == "window_place":
        return window_place(str(params["title"]), int(params["x"]), int(params["y"]),
                            int(params["width"]), int(params["height"]))
    if action == "sleep":
        time.sleep(min(30.0, max(0.0, float(params.get("seconds", 1)))))
        return {"slept": params.get("seconds", 1)}
    raise ToolError(f"unknown step action: {action}")


def run_steps(steps: list[dict[str, Any]], *, stop_on_error: bool = True,
              dry_run: bool = False) -> dict[str, Any]:
    """Execute an ordered batch, optionally verifying text after each step."""
    if not isinstance(steps, list) or not steps:
        raise ToolError("steps must be a non-empty array")
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(steps):
        from . import runtime

        runtime.check()
        if not isinstance(raw, dict):
            raise ToolError(f"step {index}: must be an object")
        action = str(raw.get("action") or "")
        params = {key: value for key, value in raw.items()
                  if key not in ("action", "expect", "timeout")}
        started = time.perf_counter()
        try:
            result = _step(action, params, dry_run=dry_run)
            if raw.get("expect"):
                probe = wait_for_text(str(raw["expect"]),
                                      timeout=float(raw.get("timeout", 8)),
                                      screen=int(params.get("screen", 1)))
                result["expect"] = probe
                if not probe.get("found"):
                    raise ToolError(f"expected text not found: {raw['expect']!r}")
            elapsed = round((time.perf_counter() - started) * 1000)
            entry = {"i": index, "action": action, "ms": elapsed, "ok": True, "result": result}
        except Exception as exc:  # noqa: BLE001 - batch reports each failure
            elapsed = round((time.perf_counter() - started) * 1000)
            entry = {"i": index, "action": action, "ms": elapsed, "ok": False,
                     "error": f"{type(exc).__name__}: {exc}"}
            results.append(entry)
            _audit({"at": datetime.now().isoformat(timespec="seconds"), "dryRun": dry_run, **entry})
            if stop_on_error:
                return {"ok": False, "failedAt": index, "steps": results}
            continue
        results.append(entry)
        _audit({"at": datetime.now().isoformat(timespec="seconds"), "dryRun": dry_run, **entry})
    return {"ok": all(item["ok"] for item in results), "steps": results}
