"""Validated process execution helpers."""

from __future__ import annotations

import asyncio
from asyncio.subprocess import PIPE
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from shutil import which
from threading import Thread
from typing import Any


@dataclass(frozen=True)
class CompletedProcess:
    """Completed child-process result."""

    args: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes


class CalledProcessError(RuntimeError):
    """Raised when a child process exits non-zero and check=True."""

    def __init__(
        self,
        returncode: int,
        cmd: Sequence[str],
        *,
        output: bytes = b"",
        stderr: bytes = b"",
    ) -> None:
        super().__init__(f"Command {list(cmd)!r} returned non-zero exit status {returncode}.")
        self.returncode = returncode
        self.cmd = list(cmd)
        self.output = output
        self.stderr = stderr


class TimeoutExpired(RuntimeError):
    """Raised when a child process exceeds the configured timeout."""

    def __init__(
        self,
        cmd: Sequence[str],
        timeout: float,
        *,
        output: bytes = b"",
        stderr: bytes = b"",
    ) -> None:
        super().__init__(f"Command {list(cmd)!r} timed out after {timeout} seconds.")
        self.cmd = list(cmd)
        self.timeout = timeout
        self.output = output
        self.stderr = stderr


def _resolve_cwd(cwd: Path | None) -> Path | None:
    if cwd is None:
        return None
    resolved = cwd.resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError(str(cwd))
    return resolved


def _resolve_executable(executable: str, cwd: Path | None) -> str:
    if not executable:
        raise ValueError("argv[0] must be a non-empty executable name")

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
    normalized[0] = _resolve_executable(normalized[0], cwd)
    return normalized


async def _run_async(
    argv: Sequence[str],
    *,
    timeout_seconds: float | None,
    cwd: Path | None,
    check: bool,
) -> CompletedProcess:
    resolved_cwd = _resolve_cwd(cwd)
    normalized_argv = _normalize_argv(argv, resolved_cwd)
    proc = await asyncio.create_subprocess_exec(
        *normalized_argv,
        cwd=str(resolved_cwd) if resolved_cwd is not None else None,
        stdout=PIPE,
        stderr=PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except TimeoutError as exc:
        proc.kill()
        stdout, stderr = await proc.communicate()
        raise TimeoutExpired(
            normalized_argv,
            timeout_seconds if timeout_seconds is not None else 0.0,
            output=stdout,
            stderr=stderr,
        ) from exc

    returncode = proc.returncode
    if returncode is None:  # pragma: no cover - communicate() should finalize the process
        raise RuntimeError("process finished without return code")

    result = CompletedProcess(
        args=tuple(normalized_argv),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
    if check and result.returncode != 0:
        raise CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def _run_awaitable(awaitable: Coroutine[Any, Any, CompletedProcess]) -> CompletedProcess:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    queue: Queue[tuple[bool, object]] = Queue(maxsize=1)

    def _thread_main() -> None:
        try:
            queue.put((True, asyncio.run(awaitable)))
        except BaseException as exc:  # pragma: no cover - thread bridge
            queue.put((False, exc))

    thread = Thread(target=_thread_main, daemon=True)
    thread.start()
    thread.join()
    ok, value = queue.get()
    if ok:
        if not isinstance(value, CompletedProcess):  # pragma: no cover - defensive
            raise RuntimeError("process thread returned unexpected result type")
        return value
    if not isinstance(value, BaseException):  # pragma: no cover - defensive
        raise RuntimeError("process thread returned unexpected error type")
    raise value


def run_subprocess(
    argv: Sequence[str],
    *,
    timeout_seconds: float | None = None,
    cwd: Path | None = None,
    check: bool = True,
) -> CompletedProcess:
    """
    Execute a command with explicit argv validation and captured output.

    Args:
        argv: Command arguments sequence (e.g. ["ffprobe", "-version"])
        timeout_seconds: Maximum execution time in seconds
        cwd: Working directory
        check: Whether to raise CalledProcessError on non-zero exit code
    """
    return _run_awaitable(
        _run_async(
            argv,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
            check=check,
        )
    )
