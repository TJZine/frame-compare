"""Subprocess utilities with security hardening.

Provides sanitized subprocess execution to prevent shell injection attacks.
All subprocess calls should use these utilities instead of raw subprocess.run().
"""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

from frame_compare.errors import ErrorContext, InputError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

# Shell metacharacters that could enable command injection
# Note: parentheses () are allowed as they're common in filenames like "Movie (2024)"
SHELL_METACHARACTERS = frozenset(";|&$`><")

# Control characters including tab (dangerous in subprocess args)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


def _escape_control_chars(value: str) -> str:
    """Escape control characters to a printable form."""
    parts: list[str] = []
    for char in value:
        codepoint = ord(char)
        if codepoint < 0x20 or codepoint == 0x7F:
            parts.append(f"\\x{codepoint:02x}")
        else:
            parts.append(char)
    return "".join(parts)


class ShellMetacharacterError(InputError):
    """Shell metacharacter detected in subprocess argument (FC-3010)."""

    def __init__(self, arg: str, char: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3010",
                name="INVALID_SUBPROCESS_ARG",
                message=f"Invalid character in argument: {arg}",
                details={"argument": arg[:100], "character": char},
                hint="Remove shell metacharacters from the argument",
            )
        )


class ControlCharacterError(InputError):
    """Control character detected in subprocess argument (FC-3011)."""

    def __init__(self, arg: str, char_repr: str) -> None:
        arg_display = _escape_control_chars(arg[:100])
        super().__init__(
            ErrorContext(
                code="FC-3011",
                name="CONTROL_CHAR_IN_ARG",
                message=f"Control character in argument: {arg_display}",
                details={"argument": arg_display, "character": char_repr},
                hint="Remove control characters from the argument",
            )
        )


def sanitize_arg(arg: str) -> str:
    """Validate and return argument, raising if dangerous characters found.

    Args:
        arg: The argument to validate

    Returns:
        The original argument if safe

    Raises:
        ShellMetacharacterError: If shell metacharacters detected (FC-3010)
        ControlCharacterError: If control characters detected (FC-3011)
    """
    # Check for shell metacharacters
    for char in arg:
        if char in SHELL_METACHARACTERS:
            raise ShellMetacharacterError(arg, char)

    # Check for control characters
    match = CONTROL_CHAR_PATTERN.search(arg)
    if match:
        raise ControlCharacterError(arg, repr(match.group()))

    return arg


def validate_subprocess_arg(arg: str | Path) -> str:
    """Validate and return argument, raising if dangerous characters found.

    This is the canonical public API for subprocess argument validation.
    Accepts both str and Path arguments for convenience.

    Args:
        arg: The argument to validate (str or Path)

    Returns:
        The argument as a string if safe

    Raises:
        ShellMetacharacterError: If shell metacharacters detected (FC-3010)
        ControlCharacterError: If control characters detected (FC-3011)
    """
    return sanitize_arg(str(arg))


def sanitize_args(args: Sequence[str | Path]) -> list[str]:
    """Sanitize all arguments in a command list.

    Args:
        args: Command and arguments to sanitize

    Returns:
        List of sanitized string arguments
    """
    return [sanitize_arg(str(arg)) for arg in args]


def run_subprocess(
    args: Sequence[str | Path],
    *,
    capture_output: bool = True,
    timeout: float | None = None,
    cwd: Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    """Run subprocess with security hardening.

    Always uses shell=False and sanitizes arguments.

    Args:
        args: Command and arguments
        capture_output: Capture stdout/stderr
        timeout: Optional timeout in seconds
        cwd: Working directory
        check: Raise CalledProcessError on non-zero exit

    Returns:
        CompletedProcess result

    Raises:
        ShellMetacharacterError: If shell metacharacters in args
        ControlCharacterError: If control characters in args
        subprocess.TimeoutExpired: If timeout exceeded
        subprocess.CalledProcessError: If check=True and non-zero exit
    """
    sanitized = sanitize_args(args)

    return subprocess.run(
        sanitized,
        capture_output=capture_output,
        timeout=timeout,
        cwd=cwd,
        check=check,
        shell=False,  # SECURITY: Always False to prevent shell injection
    )
