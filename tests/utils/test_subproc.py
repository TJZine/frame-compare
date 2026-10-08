import asyncio
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import frame_compare.utils.subproc as subproc_module
from frame_compare.utils.subproc import (
    prepare_python_child,
    resolve_executable,
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
