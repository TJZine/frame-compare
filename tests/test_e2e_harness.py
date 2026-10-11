"""Platform text-capture regression for the real-console E2E harness."""

from __future__ import annotations

import sys
from pathlib import Path

from tests.e2e.harness import run_command


def test_run_command_normalizes_windows_newlines(tmp_path: Path) -> None:
    result = run_command(
        Path(sys.executable),
        tmp_path,
        [
            "-c",
            "import sys; "
            "sys.stdout.buffer.write('café\\r\\n'.encode('utf-8')); "
            "sys.stderr.buffer.write(b'warning\\r\\n'); "
            "sys.exit(2)",
        ],
        timeout=10,
    )

    assert result.exit_code == 2
    assert result.stdout == "café\n"
    assert result.stderr == "warning\n"
