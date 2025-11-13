#!/usr/bin/env python3
"""Assert that release wheels include required Frame Compare assets."""

from __future__ import annotations

import argparse
import glob
import sys
import zipfile
from pathlib import Path

REQUIRED_MEMBERS = {
    "src/frame_compare/py.typed",
    "data/config.toml.template",
    "data/report/index.html",
    "data/report/app.css",
    "data/report/app.js",
}


def iter_wheels(patterns: list[str]) -> list[Path]:
    """Return a list of unique wheel paths matching the provided glob patterns."""
    seen: set[Path] = set()
    matches: list[Path] = []
    for pattern in patterns:
        for match in glob.glob(pattern):
            path = Path(match).resolve()
            if path in seen:
                continue
            seen.add(path)
            matches.append(path)
    return matches


def check_wheel(path: Path) -> list[str]:
    """Return which required members are missing from the given wheel."""
    with zipfile.ZipFile(path) as zf:
        members = set(zf.namelist())
    return [member for member in sorted(REQUIRED_MEMBERS) if member not in members]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that wheels contain Frame Compare data assets."
    )
    parser.add_argument(
        "wheels",
        nargs="*",
        help="Wheel files or glob expressions (default: dist/*.whl)",
    )
    args = parser.parse_args()

    patterns = args.wheels or ["dist/*.whl"]
    wheels = iter_wheels(patterns)
    if not wheels:
        parser.error(f"No wheels matched: {patterns!r}")

    failed = False
    for wheel in wheels:
        missing = check_wheel(wheel)
        if missing:
            failed = True
            print(f"{wheel}: missing {missing}", file=sys.stderr)
        else:
            print(f"{wheel}: wheel contents OK")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

