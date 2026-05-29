"""CLI exit-code mapping and console/JSON error formatting adapters."""

from __future__ import annotations

from enum import IntEnum

from frame_compare.errors import FrameCompareError, JSONValue


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
    # InternalError and unknown FrameCompareErrors map to 1
    return ExitCode.GENERAL_ERROR


def format_error_console(error: FrameCompareError, *, verbose: bool = False) -> str:
    """Format error for Rich console output with styled code and hint."""
    output = f"[bold red]\u2717[/] Error [red][[{error.code}]][/]: {error.context.message}\n"
    if error.hint:
        output += f"  [yellow]Hint:[/] {error.hint}\n"

    if verbose and error.context.details:
        output += "\n  [dim]Details:[/]\n"
        for k, v in error.context.details.items():
            output += f"    [dim]{k}:[/] {v}\n"
    elif not verbose and error.context.details:
        output += "\n  [dim]For more details, run with --verbose[/]"

    return output.rstrip()


def format_error_json(error: FrameCompareError) -> dict[str, JSONValue]:
    """Format error for JSON output."""
    return {
        "success": False,
        "error": error.context.to_dict(),
    }
