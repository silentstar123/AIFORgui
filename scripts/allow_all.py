# -*- coding: utf-8 -*-
"""Run the allow-all helper from a source checkout."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gui_operator_mcp.allow_all import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
