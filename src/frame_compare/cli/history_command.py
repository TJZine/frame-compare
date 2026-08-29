"""Read-only history command implementation."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import typer

from frame_compare.config.loader import load_config
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import FrameCompareError
from frame_compare.orchestration.preflight import (
    resolve_paths,
    resolve_selected_config_path,
)
from frame_compare.services.errors import HistoryOpenError
from frame_compare.services.run_result_record import (
    HistoryEntry,
    list_history,
    resolve_history_report,
)

from .cli_helpers import HandleErrorFn


def _resolve_history_roots(root: Path, config_path: Path) -> tuple[Path, Path]:
    resolved_root = root.resolve()
    selected_config = resolve_selected_config_path(config_path, resolved_root)
    config: ConfigSchema = load_config(selected_config)
    workspace = resolve_paths(config, resolved_root)
    return resolved_root, workspace.generated_root


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


def handle_history_list(
    root: Path,
    config_path: Path,
    *,
    json_output: bool,
    handle_error: HandleErrorFn,
    no_color: bool,
) -> None:
    """Resolve config and print contained run history."""
    try:
        _, generated_root = _resolve_history_roots(root, config_path)
        entries = list_history(generated_root)
        if json_output:
            typer.echo(
                json.dumps(
                    {"runs": [history_entry_json(entry) for entry in entries]},
                    separators=(",", ":"),
                )
            )
        else:
            for entry in entries:
                time = _timestamp(entry.completed_at or entry.started_at) or "unknown"
                report = "yes" if entry.report_available else "no"
                typer.echo(f"{entry.name}\t{entry.status}\t{time}\treport={report}")
        for entry in entries:
            if entry.warning is not None:
                typer.echo(f"Warning: {entry.name}: {entry.warning}", err=True)
    except FrameCompareError as error:
        raise typer.Exit(
            code=handle_error(error, no_color=no_color, verbose=False, verbose_hint=None)
        ) from error


def handle_history_open(
    run_name: str,
    root: Path,
    config_path: Path,
    *,
    open_report: Callable[[Path], bool],
    handle_error: HandleErrorFn,
    no_color: bool,
) -> None:
    """Open one exact-name, contained recorded report."""
    try:
        _, generated_root = _resolve_history_roots(root, config_path)
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
        typer.echo(f"Opened report for run '{run_name}'.")
    except FrameCompareError as error:
        raise typer.Exit(
            code=handle_error(error, no_color=no_color, verbose=False, verbose_hint=None)
        ) from error
