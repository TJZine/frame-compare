"""Repository-owned execution boundary for JavaScript report harnesses."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import cast

from nodejs_wheel import node


def run_node_harness(
    harness: Path,
    *,
    args: tuple[str, ...] = (),
    timeout: float = 10,
) -> subprocess.CompletedProcess[str]:
    """Execute a JavaScript harness with the locked, cross-platform Node runtime."""
    result = node(
        [str(harness), *args],
        return_completed_process=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=timeout,
    )
    return cast(subprocess.CompletedProcess[str], result)


def assert_node_harness(harness: Path, *, timeout: float = 10) -> None:
    """Require completion of every selected scenario without mirroring behavior."""
    selected = re.split(r"[\s,]+", os.environ.get("FC_NODE_SCENARIOS", "").strip())
    requested = [name for name in selected if name]
    if not requested:
        listed = run_node_harness(harness, args=("--list",), timeout=timeout)
        assert listed.returncode == 0, listed.stdout + listed.stderr
        requested = json.loads(listed.stdout)
        assert requested, "harness exports no scenarios"
    result = run_node_harness(harness, timeout=timeout)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    assert summary == {"ran": requested, "failed": []}
