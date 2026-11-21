"""Read-only history command implementation."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import typer
from rich.cells import cell_len

from frame_compare.config.loader import load_config
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import FrameCompareError
from frame_compare.orchestration.preflight import resolve_paths
from frame_compare.orchestration.run_inputs import select_run_config_path
from frame_compare.services.errors import HistoryOpenError
from frame_compare.services.run_result_record import (
    HistoryEntry,
    list_history,
    resolve_history_report,
)
from frame_compare.utils.terminal_theme import glyphs_for_stream

from .cli_helpers import HandleErrorFn


def _resolve_history_generated_root(root: Path, config_path: Path | None) -> Path:
    resolved_root, selected_config = select_run_config_path(config_path, root)
    config: ConfigSchema = load_config(selected_config)
    workspace = resolve_paths(config, resolved_root)
    return workspace.generated_root


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def history_entry_json(entry: HistoryEntry) -> dict[str, str | float | bool | None]:
    """Project a history entry into the fixed public JSON allowlist."""
    return {
        "name": entry.name,
        "status": entry.status,
        "started_at": _timestamp(entry.started_at),
        "completed_at": _timestamp(entry.completed_at),
        "duration_seconds": entry.duration_seconds,
        "report_available": entry.report_available,
    }


def _print_history_table(entries: list[HistoryEntry], generated_root: Path) -> None:
    if not entries:
        typer.echo(f"No recorded runs in {generated_root}.")
        return

    include_counts = any(entry.record is not None for entry in entries)
    headers = ["Name", "When"]
    if include_counts:
        headers.extend(("Sources", "Frames"))
    headers.extend(("Status", "Report"))
    rows = [headers]
    for entry in entries:
        timestamp = entry.completed_at or entry.started_at
        when = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S") if timestamp else "unknown"
        row = [entry.name, when]
        record = entry.record
        if include_counts:
            counts = (
                ("", "")
                if record is None
                else (str(record.clip_count), str(record.selected_frame_count))
            )
            row.extend(counts)
        status = (
            "interrupted"
            if record is not None and record.was_interrupted
            else entry.status.replace("_", " ")
        )
        row.extend((status, "yes" if entry.report_available else "no"))
        rows.append(row)

    widths = [max(map(cell_len, column)) for column in zip(*rows, strict=True)]
    for row in rows:
        cells: list[str] = []
        for index, (value, width) in enumerate(zip(row, widths, strict=True)):
            padding = " " * (width - cell_len(value))
            cells.append(padding + value if include_counts and index in (2, 3) else value + padding)
        typer.echo("  ".join(cells).rstrip())


def handle_history_list(
    root: Path,
    config_path: Path | None,
    *,
    json_output: bool,
    handle_error: HandleErrorFn,
    no_color: bool,
) -> None:
    """Resolve config and print run history."""
    try:
        generated_root = _resolve_history_generated_root(root, config_path)
        entries = list_history(generated_root)
        if json_output:
            typer.echo(
                json.dumps(
                    {"runs": [history_entry_json(entry) for entry in entries]},
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
        else:
            _print_history_table(entries, generated_root)
        for entry in entries:
            if entry.warning is not None:
                typer.echo(
                    f"{glyphs_for_stream(sys.stderr).warning} Warning: {entry.name}: {entry.warning}",
                    err=True,
                )
    except FrameCompareError as error:
        raise typer.Exit(
            code=handle_error(error, no_color=no_color, verbose=False, verbose_hint=None)
        ) from error


def handle_history_open(
    run_name: str,
    root: Path,
    config_path: Path | None,
    *,
    open_report: Callable[[Path], bool],
    handle_error: HandleErrorFn,
    no_color: bool,
) -> None:
    """Open one exact-name run's recorded report."""
    try:
        generated_root = _resolve_history_generated_root(root, config_path)
        report_path = resolve_history_report(generated_root, run_name)
        try:
            opened = open_report(report_path)
        except Exception as exc:
            raise HistoryOpenError(
                "The report could not be opened in a browser.",
                "Check the default browser and open the report manually.",
            ) from exc
        if not opened:
            raise HistoryOpenError(
                "The report could not be opened in a browser.",
                "Check the default browser and open the report manually.",
            )
        typer.echo(f"{glyphs_for_stream(sys.stdout).ok} Opened report for run '{run_name}'.")
    except FrameCompareError as error:
        raise typer.Exit(
            code=handle_error(error, no_color=no_color, verbose=False, verbose_hint=None)
        ) from error
