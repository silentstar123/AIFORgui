# -*- coding: utf-8 -*-
"""Turn DSH's approval policy to 'never' and sandbox to 'danger-full-access'.

Default is dry-run: it only prints the rows and the target file. Use --apply to
write them with a timestamped backup; --revert removes the managed block.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

BEGIN = "# >>> gui-operator allow-all (managed)"
END = "# <<< gui-operator allow-all"

ROWS = f"""{BEGIN}
- id: sandbox-policy
  config:
    mode: danger-full-access
- id: approval
  config:
    policy: never
{END}
"""


def dsh_home() -> Path:
    import os

    return Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")


def patch_path(profile: str) -> Path:
    return dsh_home() / "profiles" / profile / "cordis.patch.yml"


def has_block(text: str) -> bool:
    return BEGIN in text and END in text


def add_block(text: str) -> str:
    if has_block(text):
        return text
    if text and not text.endswith("\n"):
        text += "\n"
    return text + "\n" + ROWS


def remove_block(text: str) -> str:
    if not has_block(text):
        return text
    before, rest = text.split(BEGIN, 1)
    _inside, after = rest.split(END, 1)
    return (before.rstrip() + "\n" + after.lstrip("\n")).strip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Allow all DSH permissions for a profile")
    parser.add_argument("--profile", default="desktop")
    parser.add_argument("--apply", action="store_true", help="write the patch (default: show only)")
    parser.add_argument("--revert", action="store_true", help="remove the managed block")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    path = patch_path(args.profile)
    print(f"patch: {path}")
    if not path.is_file():
        print("not found; start DSH once for this profile, or pass --profile", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    if args.revert:
        new_text = remove_block(text)
        if new_text == text:
            print("no managed block; nothing to revert")
            return 0
        backup = path.with_suffix(path.suffix + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(path, backup)
        path.write_text(new_text, encoding="utf-8")
        print(f"reverted; backup {backup}")
        print("restart DSH for the change to take effect")
        return 0

    if not args.apply:
        print("\n--- rows that would be appended ---")
        print(ROWS)
        print("dry run; add --apply to write")
        print("prefer the built-in command inside a session: /permission danger-full-access")
        return 0

    new_text = add_block(text)
    backup = path.with_suffix(path.suffix + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(path, backup)
    path.write_text(new_text, encoding="utf-8")
    print(f"applied; backup {backup}")
    print("restart DSH for the change to take effect")
    print("revert with --revert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
