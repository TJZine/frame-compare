"""Compatibility exports for the public ``frame_compare`` shim.

This module centralizes legacy CLI-facing attributes that callers and tests
still import from :mod:`frame_compare`. Keeping them here lets the top-level
shim stay thin while preserving the existing public surface.
"""
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import Mapping

from rich.console import Console as _Console

import src.frame_compare.cli_entry as _cli_entry
import src.frame_compare.cli_runtime as _cli_runtime
import src.frame_compare.cli_utils as _cli_utils
import src.frame_compare.config_writer as config_writer
import src.frame_compare.core as _core
import src.frame_compare.doctor as doctor_module
import src.frame_compare.preflight as _preflight
import src.frame_compare.presets as presets_lib
import src.frame_compare.tmdb_workflow as tmdb_workflow
import src.frame_compare.vspreview as _vspreview
import src.frame_compare.wizard as _wizard
from src.config_loader import ConfigError, load_config
from src.frame_compare import vs as _vs_core
from src.frame_compare.render.errors import ScreenshotError

# Legacy compatibility surface: enumerate the few core helpers we still expose.
COMPAT_EXPORTS: Mapping[str, object] = {
    "_cli_override_value": _cli_utils._cli_override_value,
    "_cli_flag_value": _cli_utils._cli_flag_value,
    "cli_runtime": _cli_runtime,
    "core": _core,
    "config_writer": config_writer,
    "presets": presets_lib,
    "preflight": _preflight,
    "tmdb_workflow": tmdb_workflow,
    "vspreview": _vspreview,
    "vs_core": _vs_core,
    "collect_doctor_checks": doctor_module.collect_checks,
    "emit_doctor_results": doctor_module.emit_results,
    "DoctorCheck": doctor_module.DoctorCheck,
    "Console": _Console,
    "CliOutputManager": _cli_runtime.CliOutputManager,
    "NullCliOutputManager": _cli_runtime.NullCliOutputManager,
    "collect_path_diagnostics": _preflight.collect_path_diagnostics,
    "prepare_preflight": _preflight.prepare_preflight,
    "resolve_workspace_root": _preflight.resolve_workspace_root,
    "resolve_subdir": _preflight.resolve_subdir,
    "run_wizard_prompts": _wizard.run_wizard_prompts,
    "resolve_wizard_paths": _wizard.resolve_wizard_paths,
    "prompt_workspace_root": _wizard.prompt_workspace_root,
    "prompt_input_directory": _wizard.prompt_input_directory,
    "prompt_slowpics_options": _wizard.prompt_slowpics_options,
    "prompt_audio_alignment_option": _wizard.prompt_audio_alignment_option,
    "prompt_renderer_preference": _wizard.prompt_renderer_preference,
    "load_config": load_config,
    "_execute_wizard_session": _cli_entry._execute_wizard_session,
    "ConfigError": ConfigError,
    "render_collection_name": tmdb_workflow.render_collection_name,
    "resolve_tmdb_workflow": tmdb_workflow.resolve_workflow,
    "TMDBLookupResult": tmdb_workflow.TMDBLookupResult,
    "ScreenshotError": ScreenshotError,
}


def apply_compat_exports(target: dict[str, object]) -> None:
    """Populate the provided namespace with legacy compatibility exports."""

    target.update(COMPAT_EXPORTS)


__all__ = ["COMPAT_EXPORTS", "apply_compat_exports"]
