import asyncio
import os
import subprocess
import sys

import pytest

from frame_compare.utils.subproc import resolve_executable, run_subprocess


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
    assert result.stdout == f"from-loop{os.linesep}".encode()
    assert result.stderr == b""


@pytest.mark.parametrize(
    ("executable", "environment", "requested"),
    [
        ("ffmpeg.exe", "FRAME_COMPARE_FFMPEG_EXECUTABLE", "ffmpeg"),
        ("ffmpeg.exe", "FRAME_COMPARE_FFMPEG_EXECUTABLE", "FFMPEG.EXE"),
        ("ffprobe.exe", "FRAME_COMPARE_FFPROBE_EXECUTABLE", "ffprobe"),
        ("ffprobe.exe", "FRAME_COMPARE_FFPROBE_EXECUTABLE", "FFPROBE.EXE"),
    ],
)
def test_resolve_executable_prefers_absolute_media_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    executable: str,
    environment: str,
    requested: str,
) -> None:
    binary = tmp_path / executable
    binary.write_bytes(b"")
    binary.chmod(0o755)
    monkeypatch.setenv(environment, str(binary.resolve()))

    assert resolve_executable(requested) == str(binary.resolve())


@pytest.mark.parametrize(
    ("executable", "environment"),
    [
        ("ffmpeg", "FRAME_COMPARE_FFMPEG_EXECUTABLE"),
        ("ffprobe", "FRAME_COMPARE_FFPROBE_EXECUTABLE"),
    ],
)
def test_resolve_executable_fails_closed_for_invalid_media_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    executable: str,
    environment: str,
) -> None:
    missing = tmp_path / f"missing-{executable}.exe"
    monkeypatch.setenv(environment, str(missing.resolve()))

    with pytest.raises(FileNotFoundError, match=f"missing-{executable}"):
        resolve_executable(executable)


@pytest.mark.parametrize(
    ("executable", "environment"),
    [
        ("ffmpeg", "FRAME_COMPARE_FFMPEG_EXECUTABLE"),
        ("ffprobe", "FRAME_COMPARE_FFPROBE_EXECUTABLE"),
    ],
)
def test_resolve_executable_fails_closed_for_empty_media_override(
    monkeypatch: pytest.MonkeyPatch,
    executable: str,
    environment: str,
) -> None:
    monkeypatch.setenv(environment, "")

    with pytest.raises(FileNotFoundError, match=f"{environment} is empty"):
        resolve_executable(executable)


@pytest.mark.skipif(os.name == "nt", reason="Windows does not expose POSIX execute bits")
def test_resolve_executable_rejects_non_executable_media_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    binary = tmp_path / "ffmpeg"
    binary.write_bytes(b"")
    binary.chmod(0o644)
    monkeypatch.setenv("FRAME_COMPARE_FFMPEG_EXECUTABLE", str(binary.resolve()))

    with pytest.raises(FileNotFoundError, match="ffmpeg"):
        resolve_executable("ffmpeg")
