"""Repository-owned execution boundary for JavaScript report harnesses."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import cast

from nodejs_wheel import node


def run_node_harness(
    harness: Path,
    *,
    timeout: float = 10,
) -> subprocess.CompletedProcess[str]:
    """Execute a JavaScript harness with the locked, cross-platform Node runtime."""
    result = node(
        [str(harness)],
        return_completed_process=True,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    return cast(subprocess.CompletedProcess[str], result)
