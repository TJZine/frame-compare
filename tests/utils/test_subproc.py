import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from frame_compare.utils.subproc import resolve_executable, run_subprocess


@pytest.mark.parametrize(
    ("script", "check", "expected_code", "expected_stdout"),
    [
        ("print('hello')", True, 0, b"hello"),
        ("import sys; sys.exit(1)", False, 1, None),
        ("import sys; sys.exit(1)", True, None, None),
    ],
)
def test_run_subprocess_exit_handling(
    script: str, check: bool, expected_code: int | None, expected_stdout: bytes | None
) -> None:
    argv = [sys.executable, "-c", script]
    if expected_code is None:
        with pytest.raises(subprocess.CalledProcessError):
            run_subprocess(argv, timeout_seconds=10)
    else:
        result = (
            run_subprocess(argv, timeout_seconds=10)
            if check
            else run_subprocess(argv, check=False, timeout_seconds=10)
        )
        assert result.returncode == expected_code
        if expected_stdout is not None:
            assert expected_stdout in result.stdout


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
    assert result.stdout == f"from-loop{os.linesep}".encode()
    assert result.stderr == b""


@pytest.mark.parametrize(
    ("executable", "environment", "requested", "state", "message"),
    [
        ("ffmpeg.exe", "FRAME_COMPARE_FFMPEG_EXECUTABLE", "ffmpeg", "valid", None),
        ("ffmpeg.exe", "FRAME_COMPARE_FFMPEG_EXECUTABLE", "FFMPEG.EXE", "valid", None),
        ("ffprobe.exe", "FRAME_COMPARE_FFPROBE_EXECUTABLE", "ffprobe", "valid", None),
        ("ffprobe.exe", "FRAME_COMPARE_FFPROBE_EXECUTABLE", "FFPROBE.EXE", "valid", None),
        (
            "missing-ffmpeg.exe",
            "FRAME_COMPARE_FFMPEG_EXECUTABLE",
            "ffmpeg",
            "missing",
            "missing-ffmpeg",
        ),
        (
            "missing-ffprobe.exe",
            "FRAME_COMPARE_FFPROBE_EXECUTABLE",
            "ffprobe",
            "missing",
            "missing-ffprobe",
        ),
        (
            "ffmpeg",
            "FRAME_COMPARE_FFMPEG_EXECUTABLE",
            "ffmpeg",
            "empty",
            "FRAME_COMPARE_FFMPEG_EXECUTABLE is empty",
        ),
        (
            "ffprobe",
            "FRAME_COMPARE_FFPROBE_EXECUTABLE",
            "ffprobe",
            "empty",
            "FRAME_COMPARE_FFPROBE_EXECUTABLE is empty",
        ),
        pytest.param(
            "ffmpeg",
            "FRAME_COMPARE_FFMPEG_EXECUTABLE",
            "ffmpeg",
            "nonexec",
            "ffmpeg",
            marks=pytest.mark.skipif(
                os.name == "nt", reason="Windows does not expose POSIX execute bits"
            ),
        ),
    ],
)
def test_resolve_executable_media_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    executable: str,
    environment: str,
    requested: str,
    state: str,
    message: str | None,
) -> None:
    binary = tmp_path / executable
    if state in {"valid", "nonexec"}:
        binary.write_bytes(b"")
        binary.chmod(0o755 if state == "valid" else 0o644)
    monkeypatch.setenv(environment, "" if state == "empty" else str(binary.resolve()))
    if message is None:
        assert resolve_executable(requested) == str(binary.resolve())
    else:
        with pytest.raises(FileNotFoundError, match=message):
            resolve_executable(requested)
