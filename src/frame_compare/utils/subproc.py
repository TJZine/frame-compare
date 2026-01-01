"""Secure subprocess execution wrapper."""

import subprocess
from collections.abc import Sequence
from pathlib import Path


def run_subprocess(
    argv: Sequence[str],
    *,
    timeout_seconds: float | None = None,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    """
    Execute a command securely using subprocess.run.

    Args:
        argv: Command arguments sequence (e.g. ["ls", "-l"])
        timeout_seconds: Maximum execution time in seconds
        cwd: Working directory
        check: Whether to raise CalledProcessError on non-zero exit code

    Returns:
        CompletedProcess with captured stdout/stderr

    Raises:
        FileNotFoundError: If the executable is missing
        subprocess.TimeoutExpired: If execution exceeds timeout
        subprocess.CalledProcessError: If check=True and process fails
    """
    try:
        return subprocess.run(
            argv,
            check=check,
            cwd=cwd,
            timeout=timeout_seconds,
            capture_output=True,
            shell=False,
        )
    except FileNotFoundError:
        # Re-raise with clearer context if needed, but spec says FileNotFoundError
        raise
