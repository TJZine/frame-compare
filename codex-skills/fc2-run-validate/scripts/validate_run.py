#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> int:
    completed = subprocess.run(
        [sys.executable, *args],
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate FC-2.0 run directory artifacts (RUN_ID + artifact hygiene)."
    )
    parser.add_argument("run_id", help="RUN_ID (directory name under .agent-workflow/runs/)")
    args = parser.parse_args()

    run_id = args.run_id.strip()
    runs_dir = Path(".agent-workflow") / "runs"
    run_dir = runs_dir / run_id

    exit_code = _run("scripts/validate_run_id.py", "--check-exists", run_id)
    if exit_code != 0:
        return exit_code

    exit_code = _run("scripts/validate_run_artifacts.py", str(run_dir))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
