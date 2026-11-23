"""Check that shared test helpers can be imported without loading a pytest test module."""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    graph = json.loads(
        subprocess.check_output([sys.executable, "-m", "ruff", "analyze", "graph", "tests"])
    )
    test_modules = {
        path for path in graph if Path(path).match("test_*.py") or Path(path).match("*_test.py")
    }
    if not test_modules:
        raise SystemExit("Ruff found no test modules. Run this check from the repository root.")

    violations = [
        (importer, dependency)
        for importer, dependencies in graph.items()
        for dependency in dependencies
        if dependency in test_modules
    ]
    for importer, dependency in violations:
        print(f"{importer} imports {dependency}. Move shared helpers to a test support module.")
    return int(bool(violations))


if __name__ == "__main__":
    sys.exit(main())
