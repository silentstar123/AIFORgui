# -*- coding: utf-8 -*-
"""Minimal MCP stdio server exposing Windows GUI operation tools.

Protocol: newline-delimited JSON-RPC 2.0 on stdin/stdout; logs go to stderr.
"""
from __future__ import annotations

import base64
import json
import sys
from typing import Any, Callable

from . import __version__, runtime, tools, vision, win

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "gui-operator"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "screen_list",
        "description": "List physical and virtual monitors with pixel rectangles, DPI, and primary flag.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "screenshot",
        "description": "Capture one monitor and return a PNG image plus OCR text boxes with centers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "screen": {"type": "integer", "minimum": 1, "default": 1},
                "with_ocr": {"type": "boolean", "default": True},
                "region": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
            },
        },
    },
    {
        "name": "click_text",
        "description": "OCR the screen and click the center of the nth text match. Default is dry_run=false.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "screen": {"type": "integer", "minimum": 1, "default": 1},
                "nth": {"type": "integer", "minimum": 0, "default": 0},
                "region": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
                "exact": {"type": "boolean", "default": False},
                "double": {"type": "boolean", "default": False},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["text"],
        },
    },
    {
        "name": "click_at",
        "description": "Click global physical-pixel coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "double": {"type": "boolean", "default": False},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "type_text",
        "description": "Paste text through the clipboard into the focused control; optionally press Enter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "enter": {"type": "boolean", "default": False},
            },
            "required": ["text"],
        },
    },
    {
        "name": "press_key",
        "description": "Press a key combination such as ctrl+l, alt+tab, or enter.",
        "inputSchema": {
            "type": "object",
            "properties": {"combo": {"type": "string"}},
            "required": ["combo"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll the wheel; positive dy scrolls up.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dy": {"type": "integer"},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["dy"],
        },
    },
    {
        "name": "wait_for_text",
        "description": "Poll OCR until text appears or the timeout expires.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "timeout": {"type": "number", "default": 10},
                "screen": {"type": "integer", "minimum": 1, "default": 1},
                "interval": {"type": "number", "default": 0.5},
                "region": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
                "exact": {"type": "boolean", "default": False},
            },
            "required": ["text"],
        },
    },
    {
        "name": "window_list",
        "description": "List visible windows with titles and rectangles.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "window_focus",
        "description": "Bring the first window whose title contains the text to the foreground.",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "window_place",
        "description": "Move and resize a window to global pixel coordinates without maximizing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
            },
            "required": ["title", "x", "y", "width", "height"],
        },
    },
    {
        "name": "stop",
        "description": "Stop the current batch immediately. Same as the global hotkey Ctrl+Alt+Q.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "recycle_paths",
        "description": "Move files or folders to the Windows recycle bin. There is no permanent-delete tool.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            },
            "required": ["paths"],
        },
    },
    {
        "name": "reset_stop",
        "description": "Clear the stop flag after a stop so later calls can run again.",
        "inputSchema": {"type": "object", "properties": {}},
    },    {
        "name": "run_steps",
        "description": "Run an ordered batch of actions; stops on the first failure and writes an audit log. "
                       "Each step is {action, ...params, expect?, timeout?}; dry_run skips mutations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string",
                                       "enum": ["screen_list", "screenshot", "click_text", "click_at",
                                                "type_text", "press_key", "scroll", "wait_for_text",
                                                "window_list", "window_focus", "window_place", "sleep"]},
                            "expect": {"type": "string"},
                            "timeout": {"type": "number"},
                        },
                        "required": ["action"],
                    },
                },
                "stop_on_error": {"type": "boolean", "default": True},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["steps"],
        },
    },
]


def _run(name: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    if name == "stop":
        runtime.stop()
        return [{"type": "text", "text": json.dumps({"stopped": True}, ensure_ascii=False)}]
    if name == "reset_stop":
        runtime.reset()
        return [{"type": "text", "text": json.dumps({"stopped": False}, ensure_ascii=False)}]
    if name == "screenshot":
        data, meta = tools.screenshot(int(args.get("screen", 1)), bool(args.get("with_ocr", True)), region=args.get("region"))
        return [
            {"type": "image", "data": base64.b64encode(data).decode("ascii"),
             "mimeType": "image/png"},
            {"type": "text", "text": json.dumps(meta, ensure_ascii=False)},
        ]
    if name == "screen_list":
        result = tools.screen_list()
    elif name == "click_text":
        result = tools.click_text(
            str(args["text"]), screen=int(args.get("screen", 1)),
            nth=int(args.get("nth", 0)), exact=bool(args.get("exact", False)),
            double=bool(args.get("double", False)), dry_run=bool(args.get("dry_run", False)), region=args.get("region"))
    elif name == "click_at":
        result = tools.click_at(int(args["x"]), int(args["y"]),
                                double=bool(args.get("double", False)),
                                dry_run=bool(args.get("dry_run", False)))
    elif name == "type_text":
        result = tools.type_text(str(args["text"]), enter=bool(args.get("enter", False)))
    elif name == "press_key":
        result = tools.press_key(str(args["combo"]))
    elif name == "scroll":
        result = tools.scroll(int(args["dy"]),
                              x=args.get("x"), y=args.get("y"))
    elif name == "wait_for_text":
        result = tools.wait_for_text(str(args["text"]), timeout=float(args.get("timeout", 10)),
                                     screen=int(args.get("screen", 1)),
                                     interval=float(args.get("interval", 0.5)),
                                     exact=bool(args.get("exact", False)), region=args.get("region"))
    elif name == "window_list":
        result = tools.window_list()
    elif name == "window_focus":
        result = tools.window_focus(str(args["title"]))
    elif name == "window_place":
        result = tools.window_place(str(args["title"]), int(args["x"]), int(args["y"]),
                                    int(args["width"]), int(args["height"]))
    elif name == "run_steps":
        result = tools.run_steps(args.get("steps") or [],
                                 stop_on_error=bool(args.get("stop_on_error", True)),
                                 dry_run=bool(args.get("dry_run", False)))
    elif name == "recycle_paths":
        result = tools.recycle_paths([str(item) for item in (args.get("paths") or [])])
    else:
        raise tools.ToolError(f"unknown tool: {name}")
    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]


def _error(message: str, code: int = -32602) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": None, "error": {"code": code, "message": message}}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None:
        return None
    try:
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": request_id, "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
            }}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
        if method == "tools/call":
            params = message.get("params") or {}
            name = str(params.get("name") or "")
            arguments = params.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise tools.ToolError("arguments must be an object")
            content = _run(name, arguments)
            return {"jsonrpc": "2.0", "id": request_id,
                    "result": {"content": content, "isError": False}}
        if method in ("resources/list", "prompts/list"):
            key = "resources" if method.startswith("resources") else "prompts"
            return {"jsonrpc": "2.0", "id": request_id, "result": {key: []}}
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    except tools.ToolError as exc:
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}}
    except Exception as exc:  # noqa: BLE001 - MCP turns tool failures into results
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                            "isError": True}}


def serve() -> int:
    win.dpi_aware()
    runtime.install_hotkey()
    removed = tools.prune_audit()
    print(f"{SERVER_NAME} {__version__} ready (stdio); stop hotkey Ctrl+Alt+Q; "
          f"audit pruned {removed['dropped']} old entries", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps(_error("invalid JSON")), flush=True)
            continue
        response = handle(message)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0
