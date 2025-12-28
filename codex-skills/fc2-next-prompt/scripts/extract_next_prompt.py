#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

NEXT_HEADER = "## NEXT AGENT PROMPT (COPY/PASTE)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print the NEXT AGENT PROMPT block from a run artifact."
    )
    parser.add_argument("artifact_path", type=Path, help="Path to an artifact .md file")
    args = parser.parse_args()

    path: Path = args.artifact_path
    if not path.exists() or not path.is_file():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    idx = text.rfind(NEXT_HEADER)
    if idx == -1:
        print(f"ERROR: missing {NEXT_HEADER!r} in {path}", file=sys.stderr)
        return 1

    block = text[idx:].strip("\n")
    sys.stdout.write(block + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
