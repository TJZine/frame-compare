"""Generate deterministic API documentation for Frame Compare.

This script generates `docs/api.md` by parsing a locked set of modules using the Python AST.
It intentionally avoids importing project code (so optional dependencies do not affect generation).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def main(argv: Sequence[str] | None = None) -> int:
    from api_docs.cli import main as run

    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
