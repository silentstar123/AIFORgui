# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gui_operator_mcp import runtime, server, tools, vision  # noqa: E402


class ProtocolTest(unittest.TestCase):
    def test_tools_are_unique_and_typed(self) -> None:
        names = [tool["name"] for tool in server.TOOLS]
        self.assertEqual(len(names), len(set(names)))
        for tool in server.TOOLS:
            self.assertEqual(tool["inputSchema"].get("type"), "object")

    def test_initialize(self) -> None:
        reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(reply["result"]["protocolVersion"], server.PROTOCOL_VERSION)
        self.assertIn("tools", reply["result"]["capabilities"])

    def test_tools_list(self) -> None:
        reply = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(len(reply["result"]["tools"]), len(server.TOOLS))

    def test_notification_has_no_reply(self) -> None:
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_unknown_tool_is_error_result(self) -> None:
        reply = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                               "params": {"name": "nope", "arguments": {}}})
        self.assertTrue(reply["result"]["isError"])


class MatchingTest(unittest.TestCase):
    BOXES = [
        {"text": "开始", "center": [10, 20], "left": 0, "top": 10, "width": 20, "height": 20},
        {"text": "开始演示", "center": [50, 60], "left": 40, "top": 50, "width": 20, "height": 20},
    ]

    def test_contains_and_exact(self) -> None:
        self.assertEqual(len(vision.match("开始", self.BOXES)), 2)
        self.assertEqual(len(vision.match("开始", self.BOXES, exact=True)), 1)

    def test_nth_and_global(self) -> None:
        found = vision.match("开始", self.BOXES)
        target = vision.pick(found, 1)
        self.assertEqual(target["text"], "开始演示")
        screen = {"left": 100, "top": 200}
        self.assertEqual(vision.to_global(target, screen), (150, 260))

    def test_pick_out_of_range(self) -> None:
        with self.assertRaises(LookupError):
            vision.pick([], 0)

    def test_click_text_dry_run_uses_ocr_center(self) -> None:
        image = object()
        screen = {"left": 100, "top": 200, "width": 800, "height": 600, "dpi": 96}
        with mock.patch.object(vision, "capture", return_value=(image, screen)), \
             mock.patch.object(vision, "ocr", return_value=self.BOXES), \
             mock.patch.object(tools.win, "click") as click:
            result = tools.click_text("开始演示", exact=True, dry_run=True)
        self.assertFalse(result["clicked"])
        self.assertEqual((result["x"], result["y"]), (150, 260))
        click.assert_not_called()

    def test_run_steps_dry_run_stops_on_error(self) -> None:
        result = tools.run_steps([
            {"action": "sleep", "seconds": 0.01},
            {"action": "click_at", "x": 10, "y": 20},
        ], dry_run=True)
        self.assertTrue(result["ok"])
        self.assertEqual([item["action"] for item in result["steps"]], ["sleep", "click_at"])

    def test_run_steps_failure_skips_rest(self) -> None:
        result = tools.run_steps([
            {"action": "nope"},
            {"action": "sleep", "seconds": 0.01},
        ])
        self.assertFalse(result["ok"])
        self.assertEqual(result["failedAt"], 0)
        self.assertEqual(len(result["steps"]), 1)

    def test_run_steps_expect_failure(self) -> None:
        with mock.patch.object(tools, "wait_for_text", return_value={"found": False}):
            result = tools.run_steps([{"action": "sleep", "seconds": 0.01,
                                       "expect": "首页"}], dry_run=True)
        self.assertFalse(result["ok"])
        self.assertIn("首页", result["steps"][0]["error"])

    def test_region_is_forwarded(self) -> None:
        image = object()
        screen = {"left": 0, "top": 0, "width": 800, "height": 600, "dpi": 96}
        with mock.patch.object(vision, "capture", return_value=(image, screen)) as capture, \
             mock.patch.object(vision, "ocr", return_value=self.BOXES):
            tools.click_text("开始", dry_run=True, region=[10, 20, 100, 50])
        self.assertEqual(capture.call_args.args[1], (10, 20, 100, 50))

    def test_stop_blocks_mutations(self) -> None:
        runtime.stop()
        try:
            with self.assertRaises(tools.ToolError):
                tools.click_at(1, 2)
            with self.assertRaises(tools.ToolError):
                tools.run_steps([{"action": "sleep", "seconds": 0.01}])
        finally:
            runtime.reset()

    def test_stop_and_reset_tools(self) -> None:
        stopped = server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                 "params": {"name": "stop", "arguments": {}}})
        self.assertFalse(stopped["result"]["isError"])
        reset = server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                               "params": {"name": "reset_stop", "arguments": {}}})
        self.assertFalse(reset["result"]["isError"])
        self.assertFalse(runtime.STOP.is_set())

    def test_shift_delete_is_rejected(self) -> None:
        runtime.reset()
        with self.assertRaises(tools.ToolError):
            tools.press_key("shift+delete")

    def test_publish_saves_evidence(self) -> None:
        import tempfile
        from pathlib import Path

        boxes = [{"text": "发布", "center": [10, 10], "left": 0, "top": 0,
                  "width": 10, "height": 10}]
        screen = {"left": 0, "top": 0, "width": 100, "height": 100, "dpi": 96}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(tools, "EVIDENCE", Path(tmp)), \
             mock.patch.object(vision, "capture", return_value=(object(), screen)), \
             mock.patch.object(vision, "ocr", return_value=boxes), \
             mock.patch.object(vision, "encode_png", return_value=b"png"), \
             mock.patch.object(tools.win, "click"):
            result = tools.click_text("发布")
            self.assertTrue(result["evidence"])
            self.assertTrue(Path(result["evidence"]).is_file())

    def test_prune_audit_drops_old_entries(self) -> None:
        import json
        import tempfile
        from datetime import datetime, timedelta
        from pathlib import Path

        old = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
        new = datetime.now().isoformat(timespec="seconds")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            path.write_text(json.dumps({"at": old}) + "\n" + json.dumps({"at": new}) + "\n",
                            encoding="utf-8")
            with mock.patch.object(tools, "AUDIT", path):
                stats = tools.prune_audit(30)
            self.assertEqual(stats, {"kept": 1, "dropped": 1})
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_recycle_moves_file(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delete-me.txt"
            path.write_text("x", encoding="utf-8")
            result = tools.recycle_paths([str(path)])
            self.assertEqual(result["count"], 1)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
