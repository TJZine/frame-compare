from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import click as click
import shutil as shutil
import subprocess as subprocess
import sys as sys
from click.core import Group
from rich.console import Console as Console
from src import vs_core as vs_core
from src.frame_compare import cli_runtime as cli_runtime
from src.frame_compare import core as core
from src.frame_compare.cli_runtime import (
    AudioAlignmentJSON,
    JsonTail,
    _AudioAlignmentDisplayData,
    _AudioAlignmentSummary,
    _ClipPlan,
)
from src.frame_compare.core import (
    CLIAppError,
    PROJECT_ROOT,
    ScreenshotError,
    _apply_vspreview_manual_offsets,
    _collect_path_diagnostics,
    _fresh_app_config,
    _launch_vspreview,
    _maybe_apply_audio_alignment,
    _prepare_preflight,
    _write_vspreview_script,
    _validate_tonemap_overrides,
    _dt,
)
from src.frame_compare.media import _discover_media
from src.frame_compare.alignment_preview import _confirm_alignment_with_screenshots
from src.frame_compare.runner import RunRequest as RunRequest
from src.frame_compare.runner import RunResult as RunResult

_VSPREVIEW_WINDOWS_INSTALL: str


def _format_vspreview_manual_command(script_path: Path) -> str: ...


def run_cli(
    config_path: Optional[str],
    input_dir: Optional[str] = ...,
    *,
    root_override: Optional[str] = ...,
    audio_track_overrides: Optional[Iterable[str]] = ...,
    quiet: bool = ...,
    verbose: bool = ...,
    no_color: bool = ...,
    report_enable_override: Optional[bool] = ...,
    skip_wizard: bool = ...,
    debug_color: bool = ...,
    tonemap_overrides: Optional[Mapping[str, Any]] = ...,
) -> RunResult: ...


main: Group
