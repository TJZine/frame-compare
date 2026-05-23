import subprocess
import sys

import pytest

import frame_compare.utils.subproc as subproc
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


def test_run_subprocess_timeout(monkeypatch):
    """Assert subprocess.TimeoutExpired raised."""
    argv = [sys.executable, "-c", "print('never reached')"]
    timeout_seconds = 0.1

    def raise_timeout(
        command,
        *,
        check,
        cwd,
        timeout,
        capture_output,
        shell,
    ):
        assert command == argv
        assert check is True
        assert cwd is None
        assert timeout == timeout_seconds
        assert capture_output is True
        assert shell is False
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

    monkeypatch.setattr(subproc.subprocess, "run", raise_timeout)

    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        run_subprocess(argv, timeout_seconds=timeout_seconds)

    assert exc_info.value.cmd == argv
    assert exc_info.value.timeout == timeout_seconds


def test_run_subprocess_not_found():
    """Assert FileNotFoundError raised when bin missing."""
    with pytest.raises(FileNotFoundError):
        run_subprocess(["non_existent_command_12345"])
