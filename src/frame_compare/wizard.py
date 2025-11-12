"""Interactive configuration wizard prompts for workspace setup.

These prompts mirror the configuration areas documented in ``docs/config_audit.md``
([paths], [slowpics], [audio_alignment], and [screenshots]) so the CLI wizard stays
in sync with the vetted configuration surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, cast

import click

from .cli_runtime import CLIAppError
from .preflight import (
    abort_if_site_packages,
    is_writable_path,
    resolve_subdir,
    resolve_workspace_root,
)

__all__ = [
    "run_wizard_prompts",
    "prompt_workspace_root",
    "prompt_input_directory",
    "prompt_slowpics_options",
    "prompt_audio_alignment_option",
    "prompt_renderer_preference",
    "resolve_wizard_paths",
]


def prompt_workspace_root(default_root: Path) -> Path:
    """Interactively prompt for a writable workspace root."""

    current = default_root
    while True:
        response = click.prompt("Workspace root", default=str(current))
        candidate_input = response.strip() or str(current)
        try:
            candidate = resolve_workspace_root(candidate_input)
        except CLIAppError as exc:
            click.echo(f"Error: {exc}")
            continue
        if not is_writable_path(candidate, for_file=False):
            click.echo(f"Workspace root '{candidate}' is not writable; choose another directory.")
            continue
        return candidate


def _show_detected_subdirs(root: Path, relative_dir: str) -> None:
    """Display up to ten detected subdirectories for the given relative input directory."""

    candidate = root / relative_dir
    if not candidate.exists():
        return
    try:
        subdirs = sorted(path.name for path in candidate.iterdir() if path.is_dir())
    except OSError:
        return
    if not subdirs:
        return
    click.echo("Detected input subdirectories:")
    for name in subdirs[:10]:
        click.echo(f"  - {name}")
    if len(subdirs) > 10:
        click.echo("  …")


def prompt_input_directory(root: Path, current_default: str) -> str:
    """Prompt for the media input directory under the workspace root."""

    _show_detected_subdirs(root, current_default)
    while True:
        response = click.prompt(
            "Input directory (relative to workspace)",
            default=current_default,
        )
        value = response.strip() or current_default
        try:
            resolve_subdir(root, value, purpose="[paths].input_dir")
        except CLIAppError as exc:
            click.echo(str(exc))
            continue
        return value


def prompt_slowpics_options(config: Dict[str, Any]) -> None:
    """Interactively configure slow.pics options."""

    click.echo("Slow.pics options:")
    auto_default = bool(config.get("auto_upload", False))
    auto_upload = click.confirm("Enable slow.pics auto-upload?", default=auto_default)
    config["auto_upload"] = auto_upload

    tmdb_default = str(config.get("tmdb_id", ""))
    if click.confirm("Set a TMDB identifier?", default=bool(tmdb_default)):
        tmdb_id = click.prompt(
            "TMDB identifier (e.g. movie/603)",
            default=tmdb_default or "",
            show_default=bool(tmdb_default),
        )
        config["tmdb_id"] = tmdb_id.strip()

    cleanup_default = bool(config.get("delete_screen_dir_after_upload", True))
    cleanup = click.confirm(
        "Delete screenshot directory after upload completes?",
        default=cleanup_default,
    )
    config["delete_screen_dir_after_upload"] = cleanup


def prompt_audio_alignment_option(config: Dict[str, Any]) -> None:
    """Prompt for enabling or disabling audio alignment."""

    message = "Enable audio alignment (requires numpy, librosa, soundfile, and FFmpeg)?"
    default = bool(config.get("enable", False))
    config["enable"] = click.confirm(message, default=default)


def prompt_renderer_preference(config: Dict[str, Any]) -> None:
    """Prompt for VapourSynth vs FFmpeg renderer preference."""

    click.echo("Renderer preference:")
    renderer_default = "ffmpeg" if config.get("use_ffmpeg", False) else "vapoursynth"
    choice = click.prompt(
        "Choose renderer",
        type=click.Choice(["vapoursynth", "ffmpeg"], case_sensitive=False),
        default=renderer_default,
    )
    config["use_ffmpeg"] = choice.lower() == "ffmpeg"


def run_wizard_prompts(root: Path, config: Dict[str, Any]) -> tuple[Path, Dict[str, Any]]:
    """Execute the interactive wizard prompts and return the updated root/config."""

    workspace_root = prompt_workspace_root(root)
    paths_section = cast(Dict[str, Any], config.setdefault("paths", {}))
    default_input = str(paths_section.get("input_dir", "comparison_videos"))
    paths_section["input_dir"] = prompt_input_directory(workspace_root, default_input)
    slowpics_section = cast(Dict[str, Any], config.setdefault("slowpics", {}))
    prompt_slowpics_options(slowpics_section)
    audio_section = cast(Dict[str, Any], config.setdefault("audio_alignment", {}))
    prompt_audio_alignment_option(audio_section)
    screenshots_section = cast(Dict[str, Any], config.setdefault("screenshots", {}))
    prompt_renderer_preference(screenshots_section)
    return workspace_root, config


def resolve_wizard_paths(root_override: str | None, config_override: str | None) -> tuple[Path, Path]:
    """Resolve workspace root and config path for wizard/preset workflows."""

    root = resolve_workspace_root(root_override)
    if config_override:
        config_path = Path(config_override).expanduser()
    else:
        config_dir = resolve_subdir(root, "config", purpose="config directory")
        config_path = config_dir / "config.toml"
    abort_if_site_packages({"workspace": root, "config": config_path})
    if not is_writable_path(root, for_file=False):
        raise click.ClickException(f"Workspace root '{root}' is not writable.")
    if not is_writable_path(config_path, for_file=True):
        raise click.ClickException(
            f"Config path '{config_path}' is not writable; pass --config to select another location."
        )
    return root, config_path


# Backwards-compatibility alias (older modules referenced the underscored name).
_run_wizard_prompts = run_wizard_prompts
_resolve_wizard_paths = resolve_wizard_paths
