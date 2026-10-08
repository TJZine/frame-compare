"""Validated process execution helpers."""

from __future__ import annotations

import os
import site
import sys
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from shutil import which
from subprocess import PIPE, CompletedProcess, Popen, TimeoutExpired, run
from time import monotonic

_MEDIA_EXECUTABLE_ENV = {
    "ffmpeg": "FRAME_COMPARE_FFMPEG_EXECUTABLE",
    "ffprobe": "FRAME_COMPARE_FFPROBE_EXECUTABLE",
}
_PYTHON_INJECTION_ENV_KEYS = (
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONNOUSERSITE",
)


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _resolve_cwd(cwd: Path | None) -> Path | None:
    if cwd is None:
        return None
    resolved = cwd.resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError(str(cwd))
    return resolved


def resolve_executable(executable: str, cwd: Path | None = None) -> str:
    """Resolve an executable, honoring fail-closed bundled media overrides.

    The Windows portable launcher sets absolute FFmpeg/ffprobe paths rather than
    adding the standalone FFmpeg DLL directory to ``PATH``. This prevents native
    VapourSynth plugins from accidentally resolving FFmpeg libraries from the
    standalone command-line distribution.
    """
    if not executable:
        raise ValueError("argv[0] must be a non-empty executable name")

    executable_name = Path(executable).name.casefold()
    if executable_name.endswith(".exe"):
        executable_name = executable_name[:-4]
    override_name = _MEDIA_EXECUTABLE_ENV.get(executable_name)
    if override_name is not None and (override := os.environ.get(override_name)) is not None:
        override_path = Path(override)
        if not override_path.is_absolute() or not _is_executable_file(override_path):
            raise FileNotFoundError(override or f"{override_name} is empty")
        return str(override_path)

    executable_path = Path(executable)
    if executable_path.is_absolute():
        if not _is_executable_file(executable_path):
            raise FileNotFoundError(executable)
        return str(executable_path)

    if executable_path.parent != Path():
        base_dir = cwd if cwd is not None else Path.cwd()
        candidate = (base_dir / executable_path).resolve(strict=True)
        if not _is_executable_file(candidate):
            raise FileNotFoundError(executable)
        return str(candidate)

    resolved = which(executable)
    if resolved is None:
        raise FileNotFoundError(executable)
    return resolved


def _normalize_argv(argv: Sequence[str], cwd: Path | None) -> list[str]:
    if not argv:
        raise ValueError("argv must contain at least one element")

    normalized = [str(part) for part in argv]
    normalized[0] = resolve_executable(normalized[0], cwd)
    return normalized


def prepare_python_child(
    argv: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Prepare a child Python command with the parent's trusted import policy.

    Safe-path mode excludes the working and script directories from imports.
    Caller-controlled Python injection variables are removed, while an enabled
    parent user site and its ``PYTHONUSERBASE`` remain available to the child.
    When the parent has user-site imports disabled, ``-s`` keeps the child from
    discovering a user site of its own.
    """
    if not argv:
        raise ValueError("argv must contain at least one element")

    child_env = dict(os.environ if env is None else env)
    for key in _PYTHON_INJECTION_ENV_KEYS:
        child_env.pop(key, None)

    user_site_enabled = site.ENABLE_USER_SITE and not sys.flags.no_user_site
    python_flags = ["-P"]
    if user_site_enabled:
        if env is not None and "PYTHONUSERBASE" in env:
            child_env["PYTHONUSERBASE"] = env["PYTHONUSERBASE"]
    else:
        child_env.pop("PYTHONUSERBASE", None)
        python_flags.append("-s")

    child_env["PYTHONSAFEPATH"] = "1"
    return [str(argv[0]), *python_flags, *(str(part) for part in argv[1:])], child_env


def run_subprocess(
    argv: Sequence[str],
    *,
    timeout_seconds: float | None = None,
    cwd: Path | None = None,
    check: bool = True,
    abort: Callable[[], bool] | None = None,
) -> CompletedProcess[bytes]:
    """
    Execute a command with explicit argv validation and captured output.

    Args:
        argv: Command arguments sequence (e.g. ["ffprobe", "-version"])
        timeout_seconds: Maximum execution time in seconds
        cwd: Working directory
        check: Whether to raise CalledProcessError on non-zero exit code
        abort: Optional owner-provided check for stopping and reaping the child
    """
    resolved_cwd = _resolve_cwd(cwd)
    normalized_argv = _normalize_argv(argv, resolved_cwd)
    if abort is not None:
        return _run_abortable(normalized_argv, resolved_cwd, timeout_seconds, check, abort)
    return run(
        normalized_argv,
        cwd=resolved_cwd,
        capture_output=True,
        timeout=timeout_seconds,
        check=check,
        shell=False,
    )


class SubprocessAborted(Exception):
    """The owner stopped a process; incomplete output is not a successful result."""


def _reap_stopped_process(process: Popen[bytes]) -> None:
    # Keep the original failure, including a repeated interrupt, during cleanup.
    with suppress(BaseException):
        process.terminate()
    try:
        process.wait(timeout=2.0)
        return
    except BaseException:
        pass
    with suppress(BaseException):
        process.kill()
    with suppress(BaseException):
        process.wait(timeout=2.0)


def _run_abortable(
    argv: list[str],
    cwd: Path | None,
    timeout_seconds: float | None,
    check: bool,
    abort: Callable[[], bool],
) -> CompletedProcess[bytes]:
    if abort():
        raise SubprocessAborted()
    process = Popen(argv, cwd=cwd, stdout=PIPE, stderr=PIPE, shell=False)
    deadline = None if timeout_seconds is None else monotonic() + timeout_seconds
    last_timeout: TimeoutExpired | None = None
    try:
        while True:
            if abort():
                raise SubprocessAborted()
            remaining = None if deadline is None else deadline - monotonic()
            if timeout_seconds is not None and remaining is not None and remaining <= 0:
                raise TimeoutExpired(
                    argv,
                    timeout_seconds,
                    output=None if last_timeout is None else last_timeout.output,
                    stderr=None if last_timeout is None else last_timeout.stderr,
                )
            try:
                stdout, stderr = process.communicate(
                    timeout=0.1 if remaining is None else min(0.1, remaining)
                )
                break
            except TimeoutExpired as exc:
                last_timeout = exc
    except BaseException:
        _reap_stopped_process(process)
        raise
    finally:
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
    result = CompletedProcess(argv, process.returncode, stdout, stderr)
    if check:
        result.check_returncode()
    return result


__all__ = ["SubprocessAborted", "prepare_python_child", "resolve_executable", "run_subprocess"]
