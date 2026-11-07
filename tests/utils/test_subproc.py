import asyncio
import os
import subprocess
import sys
import textwrap
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from time import monotonic
from typing import IO

import pytest

import frame_compare.utils.subproc as subproc_module
from frame_compare.utils.subproc import (
    SubprocessAborted,
    SubprocessOutputLimitExceeded,
    prepare_python_child,
    resolve_executable,
    resolve_optional_executable,
    run_subprocess,
)


def test_prepare_python_child_strips_injection_and_keeps_native_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONHOME", "/caller/python-home")
    monkeypatch.setenv("PYTHONPATH", "/caller/python-path")
    monkeypatch.setenv("PYTHONSTARTUP", "/caller/startup.py")
    monkeypatch.setenv("PYTHONUSERBASE", "/caller/user-base")
    environment = {
        "PYTHONHOME": "/caller/python-home",
        "PYTHONPATH": "/caller/python-path",
        "PYTHONSTARTUP": "/caller/startup.py",
        "PYTHONUSERBASE": "/caller/user-base",
        "VAPOURSYNTH_EXTRA_PLUGIN_PATH": "/runtime/plugins",
        "FRAME_COMPARE_RUNTIME_KIND": "docker",
    }

    child_argv, child_env = prepare_python_child(
        [sys.executable, "-c", "print('ok')"], env=environment
    )

    assert child_argv[:2] == [sys.executable, "-P"]
    assert child_env["PYTHONSAFEPATH"] == "1"
    assert "PYTHONHOME" not in child_env
    assert "PYTHONPATH" not in child_env
    assert "PYTHONSTARTUP" not in child_env
    assert "VAPOURSYNTH_EXTRA_PLUGIN_PATH" in child_env
    assert "FRAME_COMPARE_RUNTIME_KIND" in child_env
    if subproc_module.site.ENABLE_USER_SITE and not sys.flags.no_user_site:
        assert "-s" not in child_argv
        assert child_env["PYTHONUSERBASE"] == "/caller/user-base"
    else:
        assert "-s" in child_argv
        assert "PYTHONUSERBASE" not in child_env


def test_prepare_python_child_real_disabled_user_site_child_uses_no_user_site(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "sitecustomize-imported"
    environment = os.environ.copy()
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONUSERBASE",
        "PYTHONNOUSERSITE",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "PYTHONPATH": str(Path(__file__).parents[2] / "src"),
            "PYTHONUSERBASE": str(tmp_path / "userbase"),
        }
    )
    script = textwrap.dedent(
        f"""
        import os
        import site
        import subprocess
        import sys
        from pathlib import Path

        from frame_compare.utils.subproc import prepare_python_child

        marker = Path({str(marker)!r})
        user_site = Path(site.getusersitepackages())
        user_site.mkdir(parents=True, exist_ok=True)
        (user_site / "sitecustomize.py").write_text(
            "from pathlib import Path\\nPath({str(marker)!r}).touch()\\n",
            encoding="utf-8",
        )
        child_argv, child_env = prepare_python_child(
            [sys.executable, "-c", "import site; print(site.ENABLE_USER_SITE)"],
            env=os.environ.copy(),
        )
        assert "-s" in child_argv
        assert "PYTHONUSERBASE" not in child_env
        result = subprocess.run(
            child_argv,
            cwd={str(tmp_path)!r},
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0 or result.stdout.strip() != "False" or marker.exists():
            raise SystemExit(
                f"child user-site policy failed: {{result.returncode=}}, "
                f"{{result.stdout=!r}}, {{result.stderr=!r}}, {{marker.exists()=}}"
            )
        """
    )
    result = subprocess.run(
        [sys.executable, "-s", "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert not marker.exists()


@pytest.mark.parametrize("abortable", [False, True])
@pytest.mark.parametrize(
    ("script", "check", "expected_code", "expected_stdout"),
    [
        ("print('hello')", True, 0, b"hello"),
        ("import sys; sys.exit(1)", False, 1, None),
        ("import sys; sys.exit(1)", True, None, None),
    ],
)
def test_run_subprocess_exit_handling(
    script: str,
    check: bool,
    expected_code: int | None,
    expected_stdout: bytes | None,
    abortable: bool,
) -> None:
    argv = [sys.executable, "-c", script]
    abort = (lambda: False) if abortable else None
    if expected_code is None:
        with pytest.raises(subprocess.CalledProcessError):
            run_subprocess(argv, timeout_seconds=10, abort=abort)
    else:
        result = (
            run_subprocess(argv, timeout_seconds=10, abort=abort)
            if check
            else run_subprocess(argv, check=False, timeout_seconds=10, abort=abort)
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
    assert resolve_optional_executable("non_existent_command_12345") is None


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
    monkeypatch.setenv("PATH", "")
    binary = tmp_path / executable
    if state in {"valid", "nonexec"}:
        binary.write_bytes(b"")
        binary.chmod(0o755 if state == "valid" else 0o644)
    monkeypatch.setenv(environment, "" if state == "empty" else str(binary.resolve()))
    if message is None:
        assert resolve_executable(requested) == str(binary.resolve())
        assert resolve_optional_executable(requested) == str(binary.resolve())
    else:
        with pytest.raises(FileNotFoundError, match=message):
            resolve_executable(requested)
        with pytest.raises(FileNotFoundError, match=message):
            resolve_optional_executable(requested)


@pytest.mark.parametrize("stop", ["abort", "timeout", "abort-kill"])
def test_run_subprocess_abort_path_reaps_real_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stop: str
) -> None:
    ready = tmp_path / "ready"
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen

    def popen(
        argv: list[str], *, cwd: Path | None, stdout: int, stderr: int, shell: bool
    ) -> subprocess.Popen[bytes]:
        process = original_popen(argv, cwd=cwd, stdout=stdout, stderr=stderr, shell=shell)
        processes.append(process)
        return process

    monkeypatch.setattr(subproc_module, "Popen", popen)
    argv = [
        sys.executable,
        "-c",
        "import pathlib,signal,sys,time; "
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN); " if stop == "abort-kill" else "")
        + "pathlib.Path(sys.argv[1]).touch(); "
        "print('started', flush=True); time.sleep(30)",
        str(ready),
    ]
    began = monotonic()
    with pytest.raises(
        subprocess.TimeoutExpired if stop == "timeout" else SubprocessAborted
    ) as error:
        run_subprocess(
            argv,
            timeout_seconds=0.4 if stop == "timeout" else 5,
            abort=lambda: stop.startswith("abort") and ready.exists(),
        )
    assert monotonic() - began < (4.5 if stop == "abort-kill" else 3)
    if isinstance(error.value, subprocess.TimeoutExpired):
        assert error.value.output is not None and b"started" in error.value.output
    assert len(processes) == 1
    assert processes[0].returncode is not None
    assert ready.exists()


@pytest.fixture
def streaming_children(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.Popen[bytes]]:
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subproc_module.Popen

    def popen(
        argv: list[str],
        *,
        cwd: Path | None,
        stdout: IO[bytes],
        stderr: IO[bytes] | int,
        shell: bool,
    ) -> subprocess.Popen[bytes]:
        process = original_popen(argv, cwd=cwd, stdout=stdout, stderr=stderr, shell=shell)
        processes.append(process)
        return process

    monkeypatch.setattr(subproc_module, "Popen", popen)
    return processes


def _streaming_child_command() -> list[str]:
    return [
        sys.executable,
        "-c",
        "import sys, time\n"
        "for index in range(8):\n"
        "    sys.stdout.buffer.write(bytes([index]) * 65536)\n"
        "    sys.stdout.buffer.flush()\n"
        "    time.sleep(0.03)\n",
    ]


def test_run_subprocess_streaming_consumes_all_bytes(
    streaming_children: list[subprocess.Popen[bytes]],
) -> None:
    chunks: list[bytes] = []
    expected = b"".join(bytes([index]) * 65536 for index in range(8))

    result = run_subprocess(
        _streaming_child_command(),
        timeout_seconds=10,
        stdout_consumer=chunks.append,
        max_stdout_bytes=len(expected),
    )

    assert b"".join(chunks) == expected
    assert result.stdout == b""
    assert result.returncode == 0
    assert len(streaming_children) == 1
    assert streaming_children[0].poll() == 0


def test_run_subprocess_streaming_keeps_only_stderr_tail() -> None:
    result = run_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; sys.stderr.buffer.write(b'x' * (4 * 1024 * 1024) + b'y' * 65536)",
        ],
        timeout_seconds=15,
        stdout_consumer=lambda _chunk: None,
        max_stdout_bytes=1,
    )
    assert result.returncode == 0
    assert result.stderr == b"y" * 65536


@pytest.mark.parametrize("teardown_fails", [False, True], ids=["reap", "reap-and-teardown"])
def test_run_subprocess_reports_failed_final_wait(
    streaming_children: list[subprocess.Popen[bytes]],
    monkeypatch: pytest.MonkeyPatch,
    teardown_fails: bool,
) -> None:
    reap_attempts = 0
    original_wait = subprocess.Popen.wait
    final_wait_error = OSError("injected final wait failure")
    stop_error = RuntimeError("stop the child")
    teardown_error = PermissionError("injected stdout capture unlink failure")
    original_tempfile = subproc_module.NamedTemporaryFile

    @contextmanager
    def stdout_capture(*, delete_on_close: bool) -> Generator[IO[bytes]]:
        try:
            with original_tempfile(delete_on_close=delete_on_close) as capture:
                yield capture
        finally:
            # Stand in for Windows rejecting deletion while the child still
            # holds the file. The real temporary file is removed on this host.
            raise teardown_error

    def wait(process: subprocess.Popen[bytes], timeout: float | None = None) -> int:
        nonlocal reap_attempts
        if timeout == 2.0:
            reap_attempts += 1
            if reap_attempts == 1:
                raise subprocess.TimeoutExpired(process.args, 2.0)
            raise final_wait_error
        return original_wait(process, timeout)

    def abort() -> bool:
        if streaming_children:
            raise stop_error
        return False

    monkeypatch.setattr(subprocess.Popen, "wait", wait)
    if teardown_fails:
        monkeypatch.setattr(subproc_module, "NamedTemporaryFile", stdout_capture)
    try:
        with pytest.raises(Exception) as error:
            run_subprocess(_streaming_child_command(), timeout_seconds=10, abort=abort)
    finally:
        for process in streaming_children:
            if process.poll() is None:
                process.kill()
            original_wait(process, timeout=5)
    assert reap_attempts == 2
    assert type(error.value).__name__ == "SubprocessCleanupError"
    assert error.value.__cause__ is final_wait_error
    assert final_wait_error.__context__ is stop_error
    if teardown_fails:
        assert any("PermissionError" in note for note in getattr(error.value, "__notes__", ()))


def test_run_subprocess_streaming_enforces_cap_and_reaps_child(
    streaming_children: list[subprocess.Popen[bytes]],
) -> None:
    chunks: list[bytes] = []
    cap = 100_000

    with pytest.raises(SubprocessOutputLimitExceeded):
        run_subprocess(
            _streaming_child_command(),
            timeout_seconds=10,
            stdout_consumer=chunks.append,
            max_stdout_bytes=cap,
        )

    assert sum(map(len, chunks)) <= cap
    assert len(streaming_children) == 1
    assert streaming_children[0].poll() is not None


def test_run_subprocess_streaming_propagates_abort_and_reaps_child(
    streaming_children: list[subprocess.Popen[bytes]],
) -> None:
    chunks: list[bytes] = []
    interruption = RuntimeError("owner cancelled streaming")

    def abort() -> bool:
        if chunks:
            raise interruption
        return False

    with pytest.raises(RuntimeError, match="owner cancelled streaming") as exc_info:
        run_subprocess(
            _streaming_child_command(),
            timeout_seconds=10,
            abort=abort,
            stdout_consumer=chunks.append,
            max_stdout_bytes=8 * 65536,
        )

    assert exc_info.value is interruption
    assert chunks
    assert len(streaming_children) == 1
    assert streaming_children[0].poll() is not None


@pytest.mark.parametrize("cap", [None, -1])
def test_run_subprocess_streaming_validates_cap(cap: int | None) -> None:
    with pytest.raises(ValueError, match="supplied together|nonnegative"):
        run_subprocess(
            _streaming_child_command(), stdout_consumer=lambda _chunk: None, max_stdout_bytes=cap
        )
