"""CLI exit-code mapping and console/JSON error formatting adapters."""

from __future__ import annotations

from enum import IntEnum

from rich.markup import escape

from frame_compare.errors import FrameCompareError, JSONValue
from frame_compare.utils.terminal_theme import FAIL, MUTED, WARN


class ExitCode(IntEnum):
    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIG_ERROR = 2
    DEPENDENCY_ERROR = 3
    INPUT_ERROR = 4
    PROCESSING_ERROR = 5
    NETWORK_ERROR = 6
    INTERRUPTED = 130


def get_exit_code(error: FrameCompareError) -> ExitCode:
    """Map exception to exit code."""
    code = error.code
    if code.startswith("FC-"):
        category = code.split("-", 1)[1][:1]
        if category == "1":
            return ExitCode.CONFIG_ERROR
        if category == "2":
            return ExitCode.DEPENDENCY_ERROR
        if category == "3":
            return ExitCode.INPUT_ERROR
        if category == "4":
            return ExitCode.PROCESSING_ERROR
        if category == "5":
            return ExitCode.NETWORK_ERROR
    # Unknown FrameCompareError values map to 1
    return ExitCode.GENERAL_ERROR


def format_error_console(
    error: FrameCompareError,
    *,
    verbose: bool = False,
    verbose_hint: str | None = "--verbose",
) -> str:
    """Format error for Rich console output with styled code and hint."""
    output = (
        f"[bold {FAIL}]\u2717[/] Error [{FAIL}]{escape(f'[{error.code}]')}[/]: "
        f"{escape(error.context.message)}\n"
    )
    if error.hint:
        output += f"  [{WARN}]Hint:[/] {escape(error.hint)}\n"

    if (verbose or verbose_hint is None) and error.context.details:
        output += f"\n  [{MUTED}]Details:[/]\n"
        for k, v in error.context.details.items():
            output += f"    [{MUTED}]{escape(str(k))}:[/] {escape(str(v))}\n"
    elif error.context.details and verbose_hint is not None:
        output += f"\n  [{MUTED}]For more details, run with {escape(verbose_hint)}[/]"

    return output.rstrip()


def format_error_json(error: FrameCompareError) -> dict[str, JSONValue]:
    """Format error for JSON output."""
    return {
        "success": False,
        "error": error.context.to_dict(),
    }
