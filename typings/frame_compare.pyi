from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

import click as click
import shutil as shutil
import subprocess as subprocess
import sys as sys
from click.core import Group
from rich.console import Console as Console
from src import vs_core as vs_core
from src.datatypes import TMDBConfig
from src.frame_compare import cli_runtime as cli_runtime
from src.frame_compare import core as core
from src.frame_compare import config_writer as config_writer
from src.frame_compare import doctor as doctor
from src.frame_compare import presets as presets
from src.frame_compare import vspreview as vspreview
from src.frame_compare.tmdb_workflow import TMDBLookupResult as TMDBLookupResult
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
    PreflightResult,
    collect_path_diagnostics,
    prepare_preflight,
    resolve_workspace_root,
    apply_audio_alignment,
    format_alignment_output,
    _collect_path_diagnostics,
    _fresh_app_config,
    _maybe_apply_audio_alignment,  # legacy alias for apply_audio_alignment
    _prepare_preflight,
    _validate_tonemap_overrides,
    _dt,
)
from src.frame_compare.doctor import DoctorCheck as DoctorCheck
from src.frame_compare.vspreview import (
    VSPREVIEW_POSIX_INSTALL as _VSPREVIEW_POSIX_INSTALL,
    VSPREVIEW_WINDOWS_INSTALL as _VSPREVIEW_WINDOWS_INSTALL,
    apply_manual_offsets as _apply_vspreview_manual_offsets,
    format_manual_command as _format_vspreview_manual_command,
    launch as _launch_vspreview,
    write_script as _write_vspreview_script,
)
from src.frame_compare.preflight import resolve_subdir
from src.frame_compare.media import _discover_media
from src.frame_compare.alignment_preview import _confirm_alignment_with_screenshots
from src.frame_compare.runner import RunRequest as RunRequest
from src.frame_compare.runner import RunResult as RunResult
from src.tmdb import TMDBResolution

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


def collect_doctor_checks(
    workspace_root: Path,
    config_path: Path,
    config_mapping: Mapping[str, Any],
    *,
    root_issue: Optional[str] = ...,
    config_issue: Optional[str] = ...,
) -> tuple[list[DoctorCheck], list[str]]: ...


def emit_doctor_results(
    checks: list[DoctorCheck],
    notes: list[str],
    *,
    json_mode: bool,
    workspace_root: Path,
    config_path: Path,
) -> None: ...


main: Group


def resolve_tmdb_workflow(
    *,
    files: Sequence[Path],
    metadata: Sequence[Mapping[str, str]],
    tmdb_cfg: TMDBConfig,
    year_hint_raw: Optional[str] = ...,
) -> TMDBLookupResult: ...


def render_collection_name(template_text: str, context: Mapping[str, Any]) -> str: ...
