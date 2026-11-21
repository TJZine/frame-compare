"""Reject vacuous or malformed pip-audit JSON evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_REPORT_BYTES = 32 * 1024 * 1024


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 1024


def validate_report(path: Path) -> int:
    size = path.stat().st_size
    if not 0 < size <= MAX_REPORT_BYTES:
        raise ValueError("pip-audit evidence has an invalid size")
    report = json.loads(path.read_bytes())
    if not isinstance(report, dict):
        raise ValueError("pip-audit evidence is not a JSON object")
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        raise ValueError("pip-audit collected no dependencies")
    if not isinstance(report.get("fixes"), list):
        raise ValueError("pip-audit evidence lacks its fixes list")
    for dependency in dependencies:
        if (
            not isinstance(dependency, dict)
            or not _nonempty_text(dependency.get("name"))
            or not _nonempty_text(dependency.get("version"))
            or not isinstance(dependency.get("vulns"), list)
        ):
            raise ValueError("pip-audit evidence contains a malformed dependency")
    return len(dependencies)


def main() -> int:
    if len(sys.argv) != 2:
        raise ValueError("usage: validate_pip_audit.py REPORT.json")
    count = validate_report(Path(sys.argv[1]))
    print(f"Validated pip-audit evidence for {count} dependencies")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"pip-audit evidence rejected: {error}", file=sys.stderr)
        raise SystemExit(1) from None
