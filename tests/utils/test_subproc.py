import asyncio
import subprocess
import sys

import pytest

from frame_compare.utils.subproc import run_subprocess


def test_run_subprocess_check_true():
    """Assert usage of check=True defaults."""
    # Running a simple command that succeeds
    result = run_subprocess([sys.executable, "-c", "print('hello')"])
    assert result.returncode == 0
    assert b"hello" in result.stdout


def test_run_subprocess_check_false():
    """Assert non-zero exit does NOT raise; returns CompletedProcess with returncode != 0."""
    # Running a simple command that fails
    result = run_subprocess([sys.executable, "-c", "import sys; sys.exit(1)"], check=False)
    assert result.returncode == 1


def test_run_subprocess_failure():
    """Assert CalledProcessError raised on exit 1 (when check=True)."""
    with pytest.raises(subprocess.CalledProcessError):
        run_subprocess([sys.executable, "-c", "import sys; sys.exit(1)"])


def test_run_subprocess_timeout():
    """Assert TimeoutExpired raised."""
    argv = [sys.executable, "-c", "import time; time.sleep(1)"]
    timeout_seconds = 0.01

    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        run_subprocess(argv, timeout_seconds=timeout_seconds)

    assert exc_info.value.cmd[-2:] == ["-c", "import time; time.sleep(1)"]
    assert exc_info.value.timeout == timeout_seconds


def test_run_subprocess_not_found():
    """Assert FileNotFoundError raised when bin missing."""
    with pytest.raises(FileNotFoundError):
        run_subprocess(["non_existent_command_12345"])


def test_run_subprocess_inside_running_event_loop() -> None:
    """Assert the synchronous helper is safe to call while an event loop is running."""

    async def invoke() -> subprocess.CompletedProcess[bytes]:
        asyncio.get_running_loop()
        return run_subprocess([sys.executable, "-c", "print('from-loop')"])

    result = asyncio.run(invoke())

    assert isinstance(result, subprocess.CompletedProcess)
    assert result.stdout == b"from-loop\n"
    assert result.stderr == b""
