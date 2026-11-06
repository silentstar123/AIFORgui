# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gui_operator_mcp import allow_all  # noqa: E402


class AllowAllTest(unittest.TestCase):
    def test_add_is_idempotent(self) -> None:
        once = allow_all.add_block("")
        twice = allow_all.add_block(once)
        self.assertEqual(once, twice)
        self.assertIn("danger-full-access", once)
        self.assertIn("policy: never", once)

    def test_remove_restores_original(self) -> None:
        original = "- id: ui-settings\n  config:\n    enabled: true\n"
        added = allow_all.add_block(original)
        self.assertTrue(allow_all.has_block(added))
        self.assertEqual(allow_all.remove_block(added), original)

    def test_remove_without_block(self) -> None:
        text = "- id: x\n"
        self.assertEqual(allow_all.remove_block(text), text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
