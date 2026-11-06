# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class StdioTest(unittest.TestCase):
    def test_initialize_and_tools_list(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            [sys.executable, "-m", "gui_operator_mcp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env, cwd=ROOT,
        )
        try:
            request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            reply = json.loads(process.stdout.readline())
            self.assertEqual(reply["result"]["serverInfo"]["name"], "gui-operator")

            request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            reply = json.loads(process.stdout.readline())
            names = [tool["name"] for tool in reply["result"]["tools"]]
            self.assertIn("screenshot", names)
            self.assertIn("run_steps", names)
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
