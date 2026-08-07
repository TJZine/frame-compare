"""Validated process execution helpers."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from shutil import which
from subprocess import CompletedProcess, run

_MEDIA_EXECUTABLE_ENV = {
    "ffmpeg": "FRAME_COMPARE_FFMPEG_EXECUTABLE",
    "ffprobe": "FRAME_COMPARE_FFPROBE_EXECUTABLE",
}


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

    override_name = _MEDIA_EXECUTABLE_ENV.get(executable.casefold())
    if override_name is not None and (override := os.environ.get(override_name)):
        override_path = Path(override)
        if not override_path.is_absolute() or not override_path.is_file():
            raise FileNotFoundError(override)
        return str(override_path)

    executable_path = Path(executable)
    if executable_path.is_absolute():
        if not executable_path.is_file():
            raise FileNotFoundError(executable)
        return str(executable_path)

    if executable_path.parent != Path():
        base_dir = cwd if cwd is not None else Path.cwd()
        candidate = (base_dir / executable_path).resolve(strict=True)
        if not candidate.is_file():
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


def run_subprocess(
    argv: Sequence[str],
    *,
    timeout_seconds: float | None = None,
    cwd: Path | None = None,
    check: bool = True,
) -> CompletedProcess[bytes]:
    """
    Execute a command with explicit argv validation and captured output.

    Args:
        argv: Command arguments sequence (e.g. ["ffprobe", "-version"])
        timeout_seconds: Maximum execution time in seconds
        cwd: Working directory
        check: Whether to raise CalledProcessError on non-zero exit code
    """
    resolved_cwd = _resolve_cwd(cwd)
    normalized_argv = _normalize_argv(argv, resolved_cwd)
    return run(
        normalized_argv,
        cwd=resolved_cwd,
        capture_output=True,
        timeout=timeout_seconds,
        check=check,
        shell=False,
    )


__all__ = ["resolve_executable", "run_subprocess"]
