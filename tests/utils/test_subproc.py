import asyncio
import ctypes
import json
import os
import signal
import subprocess
import sys
import textwrap
from contextlib import suppress
from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, call

import pytest

import frame_compare.utils.subproc as subproc_module
from frame_compare.utils.child_environment import child_environment
from frame_compare.utils.subproc import (
    SubprocessAborted,
    SubprocessCleanupError,
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


@pytest.mark.parametrize("route", ["path", "override", "absolute", "relative"])
@pytest.mark.parametrize("suffix", [".cmd", ".BAT", ".CmD", ".exe"])
def test_windows_executable_suffix_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str, suffix: str
) -> None:
    binary = tmp_path / "bin" / f"tool{suffix}"
    binary.parent.mkdir()
    binary.touch()
    binary.chmod(0o755)
    monkeypatch.setattr(sys, "platform", "win32")
    discovered: list[str] = []

    def find(executable: str) -> str:
        discovered.append(executable)
        return str(binary)

    monkeypatch.setattr(subproc_module, "which", find)
    requested = "tool"
    if route == "override":
        requested = "ffmpeg"
        monkeypatch.setenv("FRAME_COMPARE_FFMPEG_EXECUTABLE", str(binary))
    elif route == "absolute":
        requested = str(binary)
    elif route == "relative":
        requested = str(binary.relative_to(tmp_path))

    if suffix == ".exe":
        assert resolve_executable(requested, cwd=tmp_path) == str(binary)
    else:
        with pytest.raises(FileNotFoundError, match="Windows batch executables are unsupported"):
            resolve_executable(requested, cwd=tmp_path)
        if route == "override":
            with pytest.raises(FileNotFoundError, match="use a native executable"):
                resolve_optional_executable(requested, cwd=tmp_path)
    assert discovered == ([requested] if route == "path" else [])


@pytest.mark.skipif(os.name == "nt", reason="Uses POSIX symlinks to simulate Windows resolution")
@pytest.mark.parametrize("route", ["path", "override", "absolute", "relative"])
@pytest.mark.parametrize("batch_target", [False, True])
def test_windows_executable_policy_checks_link_and_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str, batch_target: bool
) -> None:
    target = tmp_path / ("target.bAt" if batch_target else "target.exe")
    target.touch()
    target.chmod(0o755)
    binary = tmp_path / "bin" / ("tool.exe" if batch_target else "tool.CmD")
    binary.parent.mkdir()
    binary.symlink_to(target)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subproc_module, "which", lambda _: str(binary))
    requested = "tool"
    if route == "override":
        requested = "ffprobe"
        monkeypatch.setenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", str(binary))
    elif route == "absolute":
        requested = str(binary)
    elif route == "relative":
        requested = str(binary.relative_to(tmp_path))
    with pytest.raises(FileNotFoundError, match="Windows batch executables are unsupported"):
        resolve_executable(requested, cwd=tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows batch dispatch semantics")
@pytest.mark.parametrize("route", ["absolute", "path"])
def test_windows_batch_wrapper_is_refused_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    sentinel = tmp_path / "wrapper-ran"
    wrapper = tmp_path / "wrapper.cmd"
    wrapper.write_bytes(b'@echo off\r\necho ran>"%~dp0wrapper-ran"\r\n')
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    executable = str(wrapper) if route == "absolute" else wrapper.name
    with pytest.raises(FileNotFoundError, match="use a native executable"):
        run_subprocess([executable, "input & output | text > file"], timeout_seconds=5)
    assert not sentinel.exists()


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX executable script semantics")
def test_posix_script_with_batch_suffix_remains_executable(tmp_path: Path) -> None:
    script = tmp_path / "script.cmd"
    script.write_text("#!/bin/sh\nprintf 'script ran'\n", encoding="utf-8")
    script.chmod(0o755)
    assert run_subprocess([str(script)], timeout_seconds=5).stdout == b"script ran"


@pytest.mark.parametrize("stop", ["abort", "timeout", "abort-kill"])
def test_run_subprocess_abort_path_reaps_real_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stop: str
) -> None:
    ready = tmp_path / "ready"
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen

    def popen(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        process = cast("subprocess.Popen[bytes]", original_popen(argv, **kwargs))
        if kwargs.get("stdout") == subprocess.PIPE:
            processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", popen)
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
    original_popen = subprocess.Popen

    def popen(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        process = cast("subprocess.Popen[bytes]", original_popen(argv, **kwargs))
        if kwargs.get("stdout") == subprocess.PIPE:
            processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", popen)
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


def test_run_subprocess_reports_failed_final_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    reap_attempts = 0
    original_popen = subprocess.Popen
    original_wait = subprocess.Popen.wait
    final_wait_error = OSError("injected final wait failure")
    stop_error = RuntimeError("stop the child")

    def popen(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        process = cast("subprocess.Popen[bytes]", original_popen(argv, **kwargs))
        processes.append(process)
        return process

    def wait(process: subprocess.Popen[bytes], timeout: float | None = None) -> int:
        nonlocal reap_attempts
        if timeout == 1.0:
            reap_attempts += 1
            raise subprocess.TimeoutExpired(process.args, 1.0)
        if timeout == 2.0:
            reap_attempts += 1
            raise final_wait_error
        return original_wait(process, timeout)

    def abort() -> bool:
        if processes:
            raise stop_error
        return False

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(original_popen, "wait", wait)
    try:
        with pytest.raises(SubprocessCleanupError) as error:
            run_subprocess(_streaming_child_command(), timeout_seconds=10, abort=abort)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            original_wait(process, timeout=5)
    assert reap_attempts == 2
    assert error.value.__cause__ is final_wait_error
    assert final_wait_error.__context__ is stop_error
    assert len(processes) == 1
    child = processes[0]
    assert child.stdout is not None and child.stdout.closed
    assert child.stderr is not None and child.stderr.closed


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


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
@pytest.mark.parametrize("mode", ["exit-zero", "exit-nonzero", "live", "streaming"])
def test_independent_output_caps_stop_and_reap_flooding_children(
    stream: str,
    mode: str,
    streaming_children: list[subprocess.Popen[bytes]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "fixture-signing-secret"
    monkeypatch.setenv("WINDOWS_UPDATE_SIGNING_KEY_XML", secret)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    cap = 48 * 1024 if stream == "stdout" else 16 * 1024
    fd = 1 if stream == "stdout" else 2
    write = f"os.write({fd}, {secret.encode()!r} + b'\\x1b\\x07' + b'x' * {cap})"
    ending = {
        "exit-zero": "",
        "exit-nonzero": "raise SystemExit(7)",
        "live": "time.sleep(30)",
        "streaming": "time.sleep(30)",
    }[mode]
    with pytest.raises(SubprocessOutputLimitExceeded) as error:
        run_subprocess(
            [sys.executable, "-c", f"import os,time\n{write}\n{ending}"],
            timeout_seconds=3,
            max_stdout_bytes=48 * 1024,
            max_stderr_bytes=16 * 1024,
            stdout_consumer=(lambda _chunk: None) if mode == "streaming" else None,
        )
    violation = error.value
    assert (violation.stream, violation.limit, violation.observed) == (stream, cap, cap + 1)
    assert violation.truncated
    assert len(violation.diagnostics) < 9_000
    assert b"<redacted>" in violation.diagnostics
    assert secret.encode() not in violation.diagnostics
    assert b"\x1b" not in violation.diagnostics and b"\x07" not in violation.diagnostics
    assert len(streaming_children) == 1
    child = streaming_children[0]
    assert child.returncode is not None
    assert child.stdout is not None and child.stdout.closed
    assert child.stderr is not None and child.stderr.closed
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("outcome", ["failure", "timeout"])
def test_retained_diagnostics_are_bounded_and_sanitized(
    outcome: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "fixture-webhook-secret"
    tmdb_section = '{"api_key":"fixture-section-key"}'
    slowpics_section = '{"webhook_url":"fixture-section-hook"}'
    monkeypatch.setenv("FRAME_COMPARE_SLOWPICS__WEBHOOK_URL", secret)
    monkeypatch.setenv("frame_compare_tmdb", tmdb_section)
    environment = os.environ | {"FRAME_COMPARE_SLOWPICS": slowpics_section}
    secret_values = (secret, tmdb_section, slowpics_section)
    payload = " ".join(secret_values).encode()
    finish = "raise SystemExit(3)" if outcome == "failure" else "time.sleep(30)"
    script = (
        "import os,time\n"
        f"payload = b'head\\x1b' + {payload!r} + b'x' * 20000 + b'tail\\x07'\n"
        "os.write(1, payload)\nos.write(2, payload)\n"
        f"{finish}"
    )
    kind = subprocess.CalledProcessError if outcome == "failure" else subprocess.TimeoutExpired
    with pytest.raises(kind) as error:
        run_subprocess([sys.executable, "-c", script], env=environment, timeout_seconds=0.5)
    for output in (error.value.stdout, error.value.stderr):
        assert output is not None and 0 < len(output) < 9_000
        assert output.startswith(b"head") and output.rstrip().endswith(b"tail")
        assert b"<redacted> <redacted> <redacted>" in output
        assert all(value.encode() not in output for value in secret_values)
        assert b"\x1b" not in output and b"\x07" not in output
    assert all(value not in str(error.value) for value in secret_values)


@pytest.mark.parametrize("fd", [1, 2], ids=["stdout", "stderr"])
def test_cancel_after_cap_sized_output_closes_both_pipes(
    fd: int, streaming_children: list[subprocess.Popen[bytes]], tmp_path: Path
) -> None:
    cap = 32 * 1024
    ready = tmp_path / "ready"
    script = (
        "import os,pathlib,sys,time; "
        f"os.write({fd}, b'x' * {cap}); "
        "pathlib.Path(sys.argv[1]).touch(); time.sleep(30)"
    )
    with pytest.raises(SubprocessAborted):
        run_subprocess(
            [sys.executable, "-c", script, str(ready)],
            max_stdout_bytes=cap,
            max_stderr_bytes=cap,
            timeout_seconds=3,
            abort=ready.exists,
        )
    [child] = streaming_children
    assert child.returncode is not None
    assert child.stdout is not None and child.stdout.closed
    assert child.stderr is not None and child.stderr.closed


@pytest.mark.skipif(os.name != "posix", reason="Requires a POSIX process group")
def test_overflow_stops_a_descendant_that_inherited_capture_pipes(tmp_path: Path) -> None:
    ready = tmp_path / "grandchild-pid"
    grandchild = (
        "import os,pathlib,signal,sys,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
    )
    leader = (
        "import os,pathlib,subprocess,sys,time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}, sys.argv[1]])\n"
        "while not pathlib.Path(sys.argv[1]).exists(): time.sleep(0.01)\n"
        "os.write(2, b'x' * 8192)\ntime.sleep(30)"
    )
    with pytest.raises(SubprocessOutputLimitExceeded):
        run_subprocess(
            [sys.executable, "-c", leader, str(ready)],
            timeout_seconds=3,
            max_stderr_bytes=4096,
        )
    pid = int(ready.read_text())
    state = "running"
    try:
        deadline = monotonic() + 2
        while monotonic() < deadline:
            status = subprocess.run(
                ["ps", "-o", "stat=", "-p", str(pid)],
                capture_output=True,
                check=False,
                timeout=1,
            )
            state = status.stdout.decode().strip()
            if status.returncode or state.startswith("Z"):
                return
        pytest.fail(f"grandchild remained live after overflow: {state}")
    finally:
        if state and not state.startswith("Z"):
            with suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)


def test_nonzero_leader_cannot_leave_devnull_descendant_alive(tmp_path: Path) -> None:
    ready = tmp_path / "grandchild-pid"
    grandchild = (
        "import os,pathlib,sys,time; "
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
    )
    leader = (
        "import pathlib,subprocess,sys,time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}, sys.argv[1]], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "while not pathlib.Path(sys.argv[1]).exists(): time.sleep(0.01)\n"
        "raise SystemExit(7)"
    )
    result = run_subprocess(
        [sys.executable, "-c", leader, str(ready)], check=False, timeout_seconds=5
    )

    assert result.returncode == 7
    pid = int(ready.read_text())
    deadline = monotonic() + 3
    while monotonic() < deadline:
        if sys.platform == "win32":
            status = subprocess.run(
                ["tasklist.exe", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                capture_output=True,
                check=False,
                timeout=1,
            )
            if f'"{pid}"'.encode() not in status.stdout:
                return
        else:
            status = subprocess.run(
                ["ps", "-o", "stat=", "-p", str(pid)],
                capture_output=True,
                check=False,
                timeout=1,
            )
            state = status.stdout.decode().strip()
            if status.returncode or state.startswith("Z"):
                return
        sleep(0.02)
    pytest.fail(f"grandchild {pid} survived its process-tree owner")


def test_successful_leader_cannot_leave_a_capture_pipe_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = tmp_path / "grandchild-pid"
    owned = tmp_path / "tree-owned"
    spawn = subproc_module.spawn_owned_process

    def spawn_and_release(*args: Any, **kwargs: Any) -> Any:
        child_and_tree = spawn(*args, **kwargs)
        owned.touch()
        return child_and_tree

    # Exercise descendants created after ownership, including on Windows where
    # the leader runs briefly before job assignment.
    monkeypatch.setattr(subproc_module, "spawn_owned_process", spawn_and_release)
    grandchild = (
        "import os,pathlib,sys,time; "
        "print('descendant ready', flush=True); "
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
    )
    leader = (
        "import pathlib,subprocess,sys,time\n"
        "while not pathlib.Path(sys.argv[2]).exists(): time.sleep(0.01)\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}, sys.argv[1]], "
        "stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr)\n"
        "while not pathlib.Path(sys.argv[1]).exists(): time.sleep(0.01)\n"
        "print('leader done', flush=True)"
    )

    try:
        result = run_subprocess(
            [sys.executable, "-c", leader, str(ready), str(owned)],
            timeout_seconds=5,
        )
        assert result.returncode == 0
        assert b"leader done" in result.stdout
        assert b"descendant ready" in result.stdout
        pid = int(ready.read_text())
        deadline = monotonic() + 2
        while monotonic() < deadline:
            if sys.platform == "win32":
                status = subprocess.run(
                    ["tasklist.exe", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                    capture_output=True,
                    check=True,
                    timeout=2,
                )
                exited = f'"{pid}"'.encode() not in status.stdout
            else:
                status = subprocess.run(
                    ["ps", "-o", "stat=", "-p", str(pid)],
                    capture_output=True,
                    check=False,
                    timeout=1,
                )
                exited = bool(status.returncode or status.stdout.strip().startswith(b"Z"))
            if exited:
                return
            sleep(0.02)
        pytest.fail(f"grandchild {pid} retained the completed leader's capture pipe")
    except BaseException:
        if ready.exists():
            with suppress(OSError):
                os.kill(int(ready.read_text()), signal.SIGTERM)
        raise


@pytest.fixture
def windows_kernel(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Exercise the Job Object boundary with a simulated Windows kernel."""
    kernel = MagicMock()
    kernel.CreateJobObjectW.return_value = 789
    kernel.SetInformationJobObject.return_value = True
    kernel.OpenProcess.return_value = 456
    kernel.AssignProcessToJobObject.return_value = True
    kernel.CloseHandle.return_value = True
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
    monkeypatch.setattr(ctypes, "WinError", lambda code: OSError(code, "job error"), raising=False)
    monkeypatch.setattr(subproc_module, "sys", SimpleNamespace(platform="win32"))
    return kernel


def test_windows_child_uses_kill_on_close_job(
    monkeypatch: pytest.MonkeyPatch, windows_kernel: MagicMock
) -> None:
    process = MagicMock(pid=123)

    def launch(*_args: object, **kwargs: Any) -> object:
        assert kwargs.get("creationflags", 0) == 0
        assert kwargs["close_fds"] is True
        assert kwargs["start_new_session"] is False
        windows_kernel.AssignProcessToJobObject.assert_not_called()
        return process

    monkeypatch.setattr(subprocess, "Popen", launch)
    child, tree = subproc_module.spawn_owned_process(["example.exe"], env={})
    assert child is process
    windows_kernel.AssignProcessToJobObject.assert_called_once_with(789, 456)
    _, info_class, limits, _ = windows_kernel.SetInformationJobObject.call_args.args
    assert info_class == 9
    assert limits._obj.basic_limit_information.limit_flags == 0x00002000
    windows_kernel.CloseHandle.assert_called_once_with(456)

    process.poll.return_value = 0
    tree.signal(child, force=True)
    assert windows_kernel.CloseHandle.call_args_list == [call(456), call(789)]
    tree.reap(child)
    assert windows_kernel.CloseHandle.call_args_list == [call(456), call(789)]
    process.kill.assert_not_called()
    process.wait.assert_called_once_with(timeout=1.0)


@pytest.mark.parametrize("interrupt", [False, True], ids=["assignment-failure", "interrupt"])
def test_windows_failed_assignment_stops_and_reaps_child(
    monkeypatch: pytest.MonkeyPatch, windows_kernel: MagicMock, interrupt: bool
) -> None:
    process = MagicMock(pid=123)
    monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=process))
    windows_kernel.AssignProcessToJobObject.return_value = False
    if interrupt:
        windows_kernel.AssignProcessToJobObject.side_effect = KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt if interrupt else OSError):
        subproc_module.spawn_owned_process(["example.exe"], env={}, capture_output=True)

    process.kill.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=1.0)
    process.stdout.close.assert_called_once_with()
    process.stderr.close.assert_called_once_with()
    assert windows_kernel.CloseHandle.call_args_list == [call(456), call(789)]


def test_windows_reports_job_close_failure_after_reaping_leader(
    monkeypatch: pytest.MonkeyPatch, windows_kernel: MagicMock
) -> None:
    process = MagicMock(pid=123)
    monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=process))
    child, tree = subproc_module.spawn_owned_process(["example.exe"], env={})
    windows_kernel.CloseHandle.return_value = False

    with pytest.raises(SubprocessCleanupError, match="could not close child process job"):
        tree.reap(child)

    process.kill.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=1.0)
    assert windows_kernel.CloseHandle.call_args_list == [call(456), call(789), call(789)]


def test_child_environment_filters_app_credentials_after_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "synthetic-api-key")
    monkeypatch.setenv("FRAME_COMPARE_TMDB", '{"api_key":"synthetic-inherited-key"}')
    overrides = {
        "FRAME_COMPARE_TMDB": '{"api_key":"synthetic-overridden-key"}',
        "frame_compare_slowpics": '{"webhook_url":"synthetic-section-hook"}',
        "frame_compare_slowpics__webhook_url": "synthetic-hook",
        "FRAME_COMPARE_SLOWPICS__API_TOKEN": "synthetic-token",
        "WINDOWS_UPDATE_SIGNING_KEY_XML": "synthetic-key",
        "SIGNING_KEY_MIGRATION_TOKEN": "synthetic-migration-token",
        "SOURCE_SIGNING_KEY": "synthetic-source-key",
        "SIGNING_KEY_XML_PATH": "synthetic-path",
    }
    runtime = {
        "VAPOURSYNTH_EXTRA_PLUGIN_PATH": "fixture/plugins",
        "FRAME_COMPARE_LIBPLACEBO_EXPECTED_SHA256": "fixture-fingerprint",
        "FRAME_COMPARE_ANALYSIS": '{"random_frame_count":7}',
    }
    effective = os.environ | overrides | runtime
    credential_names = {*overrides, "FRAME_COMPARE_TMDB__API_KEY"}
    observed_names = sorted({name.upper() for name in credential_names} | runtime.keys())
    script = (
        "import json, os; "
        f"names = {observed_names!r}; "
        "print(json.dumps({k.upper(): v for k, v in os.environ.items() if k.upper() in names}))"
    )
    argv = [sys.executable, "-c", script]
    command, prepared = prepare_python_child(argv, env=effective)
    result = run_subprocess(argv, env=effective, timeout_seconds=3)
    assert json.loads(result.stdout) == runtime
    assert credential_names.isdisjoint(child_environment())
    for filtered in (child_environment(effective), prepared):
        assert credential_names.isdisjoint(filtered)
        assert {name: filtered[name] for name in runtime} == runtime
    result = run_subprocess(command, env=prepared, timeout_seconds=3)
    assert json.loads(result.stdout) == runtime
