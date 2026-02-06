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
    """Assert subprocess.CalledProcessError raised on exit 1 (when check=True)."""
    with pytest.raises(subprocess.CalledProcessError):
        run_subprocess([sys.executable, "-c", "import sys; sys.exit(1)"])


def test_run_subprocess_timeout():
    """Assert subprocess.TimeoutExpired raised."""
    # Sleep for 2 seconds, but timeout is 0.1s
    with pytest.raises(subprocess.TimeoutExpired):
        run_subprocess([sys.executable, "-c", "import time; time.sleep(2)"], timeout_seconds=0.1)


def test_run_subprocess_not_found():
    """Assert FileNotFoundError raised when bin missing."""
    with pytest.raises(FileNotFoundError):
        run_subprocess(["non_existent_command_12345"])
