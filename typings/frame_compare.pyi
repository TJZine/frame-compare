from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from click.core import Group
from src.datatypes import TMDBConfig
from src.frame_compare import cli_runtime as cli_runtime
from src.frame_compare import config_writer as config_writer
from src.frame_compare import core as core
from src.frame_compare import presets as presets
from src.frame_compare import preflight as preflight
from src.frame_compare import tmdb_workflow as tmdb_workflow
from src.frame_compare import vspreview as vspreview
from src.frame_compare import vs as vs_core
from src.frame_compare.core import CLIAppError
from src.frame_compare.doctor import DoctorCheck as DoctorCheck
from src.frame_compare.preflight import (
    collect_path_diagnostics,
    prepare_preflight,
    resolve_subdir,
    resolve_workspace_root,
)
from src.frame_compare.runner import RunRequest as RunRequest
from src.frame_compare.runner import RunResult as RunResult
from src.frame_compare.tmdb_workflow import TMDBLookupResult as TMDBLookupResult
from src.frame_compare.wizard import (
    prompt_audio_alignment_option,
    prompt_input_directory,
    prompt_renderer_preference,
    prompt_slowpics_options,
    prompt_workspace_root,
    resolve_wizard_paths,
    run_wizard_prompts,
)


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
