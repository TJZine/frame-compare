#!/usr/bin/env python3
"""Validate RUN_ID format for Frame Compare 2.0 workflow.

Formats:
  - Checklist runs: YYYY-MM-DD__p<phase>-<item>__<short_slug>
    - `<phase>` is an integer (e.g. `1`)
    - `<item>` is one or more integers separated by `-` (e.g. `1-1-1` or `3`)
  - Meta runs (non-checklist): YYYY-MM-DD__meta__<short_slug>

Examples:
  2025-12-25__p1-1-1__config-module
  2025-12-25__meta__ai-readiness-audit
  2025-12-26__p2-3__frame-extraction

Usage:
  python scripts/validate_run_id.py 2025-12-25__p1-1__config-module
  python scripts/validate_run_id.py --check-exists 2025-12-25__p1-1__config-module

Exit codes:
  0: Valid (and exists if --check-exists)
  1: Invalid format
  2: Valid format but directory doesn't exist (when --check-exists)
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# RUN_ID pattern:
#   - Checklist: YYYY-MM-DD__p<phase>-<item>__<slug>
#   - Meta:      YYYY-MM-DD__meta__<slug>
RUN_ID_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})__(?P<kind>p\d+-\d+(?:-\d+)*|meta)__(?P<slug>[a-z0-9][a-z0-9-]*)$"
)

PROJECT_ROOT = Path(__file__).parent.parent
RUNS_DIR = PROJECT_ROOT / ".agent-workflow" / "runs"


def validate_run_id(run_id: str) -> tuple[bool, str]:
    """Validate RUN_ID format.

    Returns:
        Tuple of (is_valid, message)
    """
    match = RUN_ID_PATTERN.match(run_id)
    if not match:
        return (
            False,
            "Invalid format: "
            f"'{run_id}' must match either "
            "YYYY-MM-DD__p<phase>-<item>__<short_slug> or YYYY-MM-DD__meta__<short_slug>",
        )

    date_str = match.group("date")

    # Validate date is parseable
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False, f"Invalid date: '{date_str}' is not a valid date"

    return True, f"Valid RUN_ID: {run_id}"


def check_run_dir_exists(run_id: str) -> tuple[bool, str]:
    """Check if the run directory exists.

    Returns:
        Tuple of (exists, message)
    """
    run_dir = RUNS_DIR / run_id
    if run_dir.exists() and run_dir.is_dir():
        return True, f"Run directory exists: {run_dir}"
    return False, f"Run directory not found: {run_dir}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate RUN_ID format for Frame Compare 2.0 workflow"
    )
    parser.add_argument("run_id", help="RUN_ID to validate")
    parser.add_argument(
        "--check-exists",
        action="store_true",
        help="Also check if .agent-workflow/runs/<RUN_ID>/ exists",
    )
    args = parser.parse_args()

    # Validate format
    is_valid, message = validate_run_id(args.run_id)
    print(message)

    if not is_valid:
        return 1

    # Optionally check existence
    if args.check_exists:
        exists, exist_msg = check_run_dir_exists(args.run_id)
        print(exist_msg)
        if not exists:
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
