#!/usr/bin/env python3
"""Lint docs for command-canon drift.

This repo uses a two-lane command canon:
  - Repo scripts/gates: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/...`
  - Tooling: prefer `.venv/bin/*` (pyright/ruff/pytest)

This linter prevents SSOT docs from drifting back to `uv run pyright|ruff|pytest` guidance.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_FORBIDDEN_TOOLING = re.compile(r"\buv run (pyright|ruff|pytest)\b")


def _iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted([p for p in root.rglob("*.md") if p.is_file()])


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint SSOT docs for command canon drift.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("docs") / "OPUS_REBUILD_FRAME_COMPARE"],
        help="File or directory paths to scan (default: docs/OPUS_REBUILD_FRAME_COMPARE)",
    )
    args = parser.parse_args()

    errors: list[str] = []
    for root in args.paths:
        for path in _iter_files(root):
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                match = _FORBIDDEN_TOOLING.search(line)
                if match is None:
                    continue
                errors.append(
                    f"{path}:{line_no}: command-canon drift: avoid {match.group(0)!r}; "
                    "prefer `.venv/bin/*` (see docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md)."
                )

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

