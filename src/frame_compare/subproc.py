"""
Helper utilities for invoking subprocesses with consistent safeguards.

`run_checked` wraps `subprocess.run` so callers get predictable defaults:
argv lists only, `shell=False`, text mode enabled unless explicitly
overridden, and optional `check` semantics without repeating boilerplate.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from typing import IO, Any, Literal, overload

StdIO = int | IO[Any] | None

Argv = Sequence[str]
PathLikeStr = os.PathLike[str]
EnvMapping = Mapping[str, str]


@overload
def run_checked(
    argv: Argv,
    *,
    cwd: str | PathLikeStr | None = ...,
    env: EnvMapping | None = ...,
    timeout: float | None = ...,
    stdin: StdIO = ...,
    stdout: StdIO = ...,
    stderr: StdIO = ...,
    text: Literal[True] = ...,
    check: bool = ...,
) -> subprocess.CompletedProcess[str]:
    ...


@overload
def run_checked(
    argv: Argv,
    *,
    cwd: str | PathLikeStr | None = ...,
    env: EnvMapping | None = ...,
    timeout: float | None = ...,
    stdin: StdIO = ...,
    stdout: StdIO = ...,
    stderr: StdIO = ...,
    text: Literal[False],
    check: bool = ...,
) -> subprocess.CompletedProcess[bytes]:
    ...


def run_checked(
    argv: Argv,
    *,
    cwd: str | PathLikeStr | None = None,
    env: EnvMapping | None = None,
    timeout: float | None = None,
    stdin: StdIO = subprocess.DEVNULL,
    stdout: StdIO = subprocess.PIPE,
    stderr: StdIO = subprocess.PIPE,
    text: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess[Any]:
    """
    Run *argv* via `subprocess.run` with consistent safe defaults.

    Raises:
        ValueError: if *argv* is empty.
        subprocess.CalledProcessError: when `check=True` and the child exits non-zero.
    """

    if not argv:
        raise ValueError("run_checked requires at least one argv entry.")
    if isinstance(argv, (str, bytes)):
        raise TypeError("run_checked expects a sequence of arguments, not a string.")

    command: list[str] = list(argv)
    completed: subprocess.CompletedProcess[Any] = subprocess.run(
        command,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        timeout=timeout,
        text=text,
        shell=False,
        check=False,
    )
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed


__all__ = ["run_checked"]
