"""CLI entry point and orchestration logic for frame comparison runs."""

from __future__ import annotations

import asyncio
import copy
import datetime as _dt
import difflib
import importlib.util
import json
import logging
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tomllib
import uuid
from collections import Counter, defaultdict
from collections.abc import Mapping as MappingABC
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from pathlib import Path
from string import Template
from typing import (
    TYPE_CHECKING,
    Any,
    ContextManager,
    Dict,
    Final,
    Iterable,
    List,
    Literal,
    Mapping,
    MutableMapping,
    NoReturn,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypedDict,
    cast,
)

import click
import httpx
from rich import print
from rich.console import Console  # noqa: F401
from rich.markup import escape
from rich.progress import Progress, ProgressColumn  # noqa: F401
from rich.text import Text

from src import audio_alignment
from src.config_loader import load_config as _load_config
from src.datatypes import (
    AnalysisConfig,
    AppConfig,
    ColorConfig,
    NamingConfig,
    RuntimeConfig,
    TMDBConfig,
)

if TYPE_CHECKING:
    from src.audio_alignment import AlignmentMeasurement, AudioStreamInfo

    class _AsyncHTTPTransport(Protocol):
        def __init__(self, retries: int = ...) -> None: ...
        def close(self) -> None: ...
import src.frame_compare.alignment_preview as _alignment_preview_module
import src.frame_compare.preflight as _preflight_constants
import src.screenshot as _screenshot_module
from src import vs_core
from src.analysis import (
    SelectionWindowSpec,
    compute_selection_window,
    export_selection_metadata,  # noqa: F401
    probe_cached_metrics,  # noqa: F401
    select_frames,  # noqa: F401
    selection_details_to_json,  # noqa: F401
    selection_hash_for_config,  # noqa: F401
    write_selection_cache_file,  # noqa: F401
)
from src.frame_compare.cli_runtime import (
    AudioAlignmentJSON,  # noqa: F401 - re-exported for compatibility
    CLIAppError,
    CliOutputManagerProtocol,
    ClipRecord,  # noqa: F401 - re-exported for compatibility
    JsonTail,
    ReportJSON,  # noqa: F401 - re-exported for compatibility
    SlowpicsJSON,  # noqa: F401 - re-exported for compatibility
    SlowpicsTitleBlock,  # noqa: F401 - re-exported for compatibility
    SlowpicsTitleInputs,  # noqa: F401 - re-exported for compatibility
    TrimClipEntry,  # noqa: F401 - re-exported for compatibility
    TrimsJSON,  # noqa: F401 - re-exported for compatibility
    TrimSummary,  # noqa: F401 - re-exported for compatibility
    ViewerJSON,  # noqa: F401 - re-exported for compatibility
    _AudioAlignmentDisplayData,
    _AudioAlignmentSummary,
    _AudioMeasurementDetail,
    _ClipPlan,
    _coerce_str_mapping,
    _ensure_audio_alignment_block,
    _normalise_vspreview_mode,
    _OverrideValue,
    _plan_label,
)
from src.frame_compare.config_helpers import coerce_config_flag as _coerce_config_flag
from src.frame_compare.preflight import (
    PACKAGED_TEMPLATE_PATH,
    PROJECT_ROOT,
    PreflightResult,
    _abort_if_site_packages,
    _is_writable_path,
    collect_path_diagnostics,
    prepare_preflight,
    resolve_subdir,
    resolve_workspace_root,
)
from src.slowpics import SlowpicsAPIError, build_shortcut_filename, upload_comparison  # noqa: F401
from src.tmdb import (
    TMDBAmbiguityError,  # noqa: F401
    TMDBCandidate,
    TMDBResolution,
    TMDBResolutionError,
    parse_manual_id,
    resolve_tmdb,  # noqa: F401
)
from src.utils import parse_filename_metadata
from src.vs_core import ClipInitError, ClipProcessError  # noqa: F401

logger = logging.getLogger(__name__)

CONFIG_ENV_VAR: Final[str] = _preflight_constants.CONFIG_ENV_VAR
NO_WIZARD_ENV_VAR: Final[str] = _preflight_constants.NO_WIZARD_ENV_VAR
ROOT_ENV_VAR: Final[str] = _preflight_constants.ROOT_ENV_VAR
ROOT_SENTINELS: Final[tuple[str, ...]] = _preflight_constants.ROOT_SENTINELS

ScreenshotError = _screenshot_module.ScreenshotError
generate_screenshots = _screenshot_module.generate_screenshots
_fresh_app_config = _preflight_constants._fresh_app_config
_PathPreflightResult = PreflightResult
_prepare_preflight = prepare_preflight
_collect_path_diagnostics = collect_path_diagnostics
_confirm_alignment_with_screenshots = _alignment_preview_module._confirm_alignment_with_screenshots
load_config = _load_config

PRESETS_DIR: Final[Path] = (PROJECT_ROOT / "presets").resolve()

_DEFAULT_CONFIG_HELP: Final[str] = (
    "Optional explicit path to config.toml. When omitted, Frame Compare looks for "
    "ROOT/config/config.toml (see --root/FRAME_COMPARE_ROOT)."
)

_VSPREVIEW_WINDOWS_INSTALL: Final[str] = (
    "uv add frame-compare --extra preview  # fallback: uv add vspreview PySide6"
)
_VSPREVIEW_POSIX_INSTALL: Final[str] = (
    "uv add frame-compare --extra preview  # fallback: uv add vspreview PySide6"
)
_VSPREVIEW_MANUAL_COMMAND_TEMPLATE: Final[str] = "{python} -m vspreview {script}"


def _format_vspreview_manual_command(script_path: Path) -> str:
    """Build a manual VSPreview command using the active Python interpreter."""

    python_exe = sys.executable or "python"
    script_arg = str(script_path)
    if os.name == "nt":
        if " " in python_exe and not python_exe.startswith('"'):
            python_exe = f'"{python_exe}"'
        if " " in script_arg and not script_arg.startswith('"'):
            script_arg = f'"{script_arg}"'
    else:
        python_exe = shlex.quote(python_exe)
        script_arg = shlex.quote(script_arg)
    return _VSPREVIEW_MANUAL_COMMAND_TEMPLATE.format(
        python=python_exe, script=script_arg
    )


def _read_template_text() -> str:
    """Return the config template text, preserving existing comments."""

    text = PACKAGED_TEMPLATE_PATH.read_text(encoding="utf-8")
    return text


def _load_template_config() -> Dict[str, Any]:
    """Load the template configuration into a nested dictionary."""

    text = _read_template_text()
    return tomllib.loads(text.lstrip("\ufeff"))


def _deep_merge(dest: Dict[str, Any], src: Mapping[str, Any]) -> None:
    """Recursively merge ``src`` into ``dest`` in-place."""

    for key, value in src.items():
        if isinstance(value, Mapping) and isinstance(dest.get(key), MappingABC):
            existing = dest[key]
            if not isinstance(existing, dict):
                dest[key] = copy.deepcopy(value)
            else:
                _deep_merge(existing, value)  # type: ignore[arg-type]
        elif isinstance(value, Mapping) and key not in dest:
            dest[key] = copy.deepcopy(value)
        else:
            dest[key] = copy.deepcopy(value)


def _diff_config(base: Mapping[str, Any], modified: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a nested mapping of values that differ between ``base`` and ``modified``."""

    diff: Dict[str, Any] = {}
    for key, value in modified.items():
        base_value = base.get(key)
        if isinstance(value, Mapping) and isinstance(base_value, Mapping):
            nested = _diff_config(base_value, value)
            if nested:
                diff[key] = nested
        else:
            if key not in base or base_value != value:
                diff[key] = value
    return diff


def _format_toml_value(value: Any) -> str:
    """Format a Python value as TOML literal."""

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("Non-finite float cannot be serialized to TOML")
            return format(value, "g")
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    if value is None:
        return '""'  # Represent None as empty string literal.
    raise ValueError(f"Unsupported TOML value type: {type(value)!r}")


def _flatten_overrides(overrides: Mapping[str, Any]) -> Dict[Tuple[str, ...], Dict[str, Any]]:
    """Flatten nested override mapping to section tuples -> key/value pairs."""

    flattened: Dict[Tuple[str, ...], Dict[str, Any]] = {}

    def _walk(mapping: Mapping[str, Any], prefix: Tuple[str, ...]) -> None:
        for key, value in mapping.items():
            if isinstance(value, Mapping):
                _walk(value, prefix + (key,))
            else:
                flattened.setdefault(prefix, {})[key] = value

    _walk(overrides, ())
    return flattened


def _apply_overrides_to_template(template_text: str, overrides: Mapping[str, Any]) -> str:
    """Return template text with overrides applied without discarding comments."""

    if not overrides:
        return template_text

    lines = template_text.splitlines()
    section_ranges: Dict[Tuple[str, ...], Tuple[int, int]] = {}
    current_section: Tuple[str, ...] = ()
    section_start = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            if current_section not in section_ranges:
                section_ranges[current_section] = (section_start, index)
            section_name = stripped[1:-1]
            current_section = tuple(part.strip() for part in section_name.split(".")) if section_name else ()
            section_start = index + 1
    if current_section not in section_ranges:
        section_ranges[current_section] = (section_start, len(lines))

    flattened = _flatten_overrides(overrides)
    applied: set[Tuple[Tuple[str, ...], str]] = set()
    current_section = ()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            section_name = stripped[1:-1]
            current_section = tuple(part.strip() for part in section_name.split(".")) if section_name else ()
            continue
        if "=" not in line or stripped.startswith("#"):
            continue
        key, _, _ = stripped.partition("=")
        key = key.strip()
        overrides_for_section = flattened.get(current_section)
        if overrides_for_section and key in overrides_for_section:
            formatted = _format_toml_value(overrides_for_section[key])
            prefix = line[: line.index(key)]
            lines[idx] = f"{prefix}{key} = {formatted}"
            applied.add((current_section, key))

    for section, key_values in flattened.items():
        for key, value in key_values.items():
            identifier = (section, key)
            if identifier in applied:
                continue
            start, end = section_ranges.get(section, (len(lines), len(lines)))
            formatted = _format_toml_value(value)
            insert_line = f"{key} = {formatted}"
            lines.insert(end, insert_line)
            # Update stored ranges for following insertions.
            section_ranges = {
                sect: (s, e + 1 if e >= end else e) for sect, (s, e) in section_ranges.items()
            }
            applied.add(identifier)

    return "\n".join(lines) + ("\n" if template_text.endswith("\n") else "")


def _write_config_file(path: Path, content: str) -> None:
    """Atomically write ``content`` to ``path`` with UTF-8 encoding."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(path.parent),
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _present_diff(original: str, updated: str) -> None:
    """Print a unified diff between ``original`` and ``updated`` strings."""

    diff = list(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile="template",
            tofile="generated",
            lineterm="",
        )
    )
    if diff:
        for line in diff:
            print(line)
    else:
        print("No differences from the template.")


def _list_preset_paths() -> Dict[str, Path]:
    """Return available preset names mapped to their file paths."""

    if not PRESETS_DIR.exists():
        return {}
    presets: Dict[str, Path] = {}
    for path in PRESETS_DIR.glob("*.toml"):
        if path.is_file():
            presets[path.stem] = path
    return presets


def _load_preset_data(name: str) -> Dict[str, Any]:
    """Load a preset TOML fragment by name."""

    presets = _list_preset_paths()
    try:
        preset_path = presets[name]
    except KeyError as exc:
        raise click.ClickException(f"Unknown preset '{name}'. Use 'preset list' to inspect options.") from exc
    try:
        text = preset_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Failed to read preset '{name}': {exc}") from exc
    try:
        data = tomllib.loads(text.lstrip("\ufeff"))
    except tomllib.TOMLDecodeError as exc:
        raise click.ClickException(f"Preset '{name}' is invalid TOML: {exc}") from exc
    return cast(Dict[str, Any], data)


PRESET_DESCRIPTIONS: Final[Dict[str, str]] = {
    "quick-compare": "Minimal runtime defaults with FFmpeg renderer and slow.pics disabled.",
    "hdr-vs-sdr": "Tonemap-first workflow with stricter verification thresholds.",
    "batch-qc": "Expanded sampling with slow.pics uploads enabled for review batches.",
}


DoctorStatus = Literal["pass", "fail", "warn"]


class DoctorCheck(TypedDict):
    """Structured result for dependency doctor checks."""

    id: str
    label: str
    status: DoctorStatus
    message: str


_DOCTOR_STATUS_ICONS: Final[Dict[DoctorStatus, str]] = {
    "pass": "✅",
    "fail": "❌",
    "warn": "⚠️",
}


def _resolve_wizard_paths(root_override: str | None, config_override: str | None) -> tuple[Path, Path]:
    """Resolve workspace root and config path for wizard/preset workflows."""

    root = resolve_workspace_root(root_override)
    config_path = Path(config_override).expanduser() if config_override else root / "config" / "config.toml"
    _abort_if_site_packages({"workspace": root, "config": config_path})
    if not _is_writable_path(root, for_file=False):
        raise click.ClickException(f"Workspace root '{root}' is not writable.")
    if not _is_writable_path(config_path, for_file=True):
        raise click.ClickException(
            f"Config path '{config_path}' is not writable; pass --config to select another location."
        )
    return root, config_path


def _render_config_text(
    template_text: str,
    template_config: Mapping[str, Any],
    final_config: Mapping[str, Any],
) -> str:
    """Generate TOML text for ``final_config`` using the original template layout."""

    overrides = _diff_config(template_config, final_config)
    return _apply_overrides_to_template(template_text, overrides)


def _prompt_workspace_root(default_root: Path) -> Path:
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
        if not _is_writable_path(candidate, for_file=False):
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


def _prompt_input_directory(root: Path, current_default: str) -> str:
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


def _prompt_slowpics_options(config: Dict[str, Any]) -> None:
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


def _prompt_audio_alignment_option(config: Dict[str, Any]) -> None:
    """Prompt for enabling or disabling audio alignment."""

    message = "Enable audio alignment (requires numpy, librosa, soundfile, and FFmpeg)?"
    default = bool(config.get("enable", False))
    config["enable"] = click.confirm(message, default=default)


def _prompt_renderer_preference(config: Dict[str, Any]) -> None:
    """Prompt for VapourSynth vs FFmpeg renderer preference."""

    click.echo("Renderer preference:")
    renderer_default = "ffmpeg" if config.get("use_ffmpeg", False) else "vapoursynth"
    choice = click.prompt(
        "Choose renderer",
        type=click.Choice(["vapoursynth", "ffmpeg"], case_sensitive=False),
        default=renderer_default,
    )
    config["use_ffmpeg"] = choice.lower() == "ffmpeg"


def _run_wizard_prompts(root: Path, config: Dict[str, Any]) -> tuple[Path, Dict[str, Any]]:
    """Execute the interactive wizard prompts and return the updated root/config."""

    workspace_root = _prompt_workspace_root(root)
    paths_section = cast(Dict[str, Any], config.setdefault("paths", {}))
    default_input = str(paths_section.get("input_dir", "comparison_videos"))
    paths_section["input_dir"] = _prompt_input_directory(workspace_root, default_input)
    slowpics_section = cast(Dict[str, Any], config.setdefault("slowpics", {}))
    _prompt_slowpics_options(slowpics_section)
    audio_section = cast(Dict[str, Any], config.setdefault("audio_alignment", {}))
    _prompt_audio_alignment_option(audio_section)
    screenshots_section = cast(Dict[str, Any], config.setdefault("screenshots", {}))
    _prompt_renderer_preference(screenshots_section)
    return workspace_root, config


def _get_config_value(mapping: Mapping[str, Any], path: Sequence[str], default: Any = None) -> Any:
    """Return a nested configuration value from *mapping* using ``path`` segments."""

    current: Any = mapping
    for segment in path:
        if isinstance(current, Mapping) and segment in current:
            current = current[segment]
        else:
            return default
    return current


def _collect_doctor_checks(
    root: Path,
    config_path: Path,
    config_mapping: Mapping[str, Any],
    *,
    root_issue: Optional[str] = None,
    config_issue: Optional[str] = None,
) -> tuple[list[DoctorCheck], list[str]]:
    """Generate doctor check results and auxiliary notes."""

    notes: list[str] = []
    if root_issue:
        notes.append(root_issue)
    if config_issue:
        notes.append(config_issue)

    use_ffmpeg = bool(_get_config_value(config_mapping, ("screenshots", "use_ffmpeg"), False))
    audio_enabled = bool(_get_config_value(config_mapping, ("audio_alignment", "enable"), False))
    vspreview_enabled = bool(_get_config_value(config_mapping, ("audio_alignment", "use_vspreview"), False))
    auto_upload = bool(_get_config_value(config_mapping, ("slowpics", "auto_upload"), False))

    vapoursynth_spec = importlib.util.find_spec("vapoursynth")
    vapoursynth_available = vapoursynth_spec is not None

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    checks: list[DoctorCheck] = []

    config_writable = _is_writable_path(config_path, for_file=True)
    config_label = "Config path writable"
    if root_issue:
        config_status: DoctorStatus = "fail"
        config_message = root_issue
    elif config_issue:
        config_status = "warn"
        config_message = config_issue
    elif config_writable:
        config_status = "pass"
        config_message = f"{config_path} is writable."
    else:
        config_status = "fail"
        config_message = (
            f"{config_path} is not writable. Choose another --root/--config or adjust permissions."
        )
    checks.append({
        "id": "config",
        "label": config_label,
        "status": config_status,
        "message": config_message,
    })

    if vapoursynth_available:
        vap_message = "VapourSynth module available."
        vap_status: DoctorStatus = "pass"
    else:
        if use_ffmpeg:
            vap_status = "warn"
            vap_message = "VapourSynth not found; screenshots are configured for FFmpeg fallback."
        else:
            vap_status = "fail"
            vap_message = "VapourSynth not found. Install VapourSynth or set [screenshots].use_ffmpeg=true."
    checks.append({
        "id": "vapoursynth",
        "label": "VapourSynth import",
        "status": vap_status,
        "message": vap_message,
    })

    ffmpeg_missing = [name for name, present in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)) if not present]
    if not ffmpeg_missing:
        ffmpeg_status: DoctorStatus = "pass"
        ffmpeg_message = "ffmpeg/ffprobe available."
    else:
        if use_ffmpeg:
            ffmpeg_status = "fail"
        elif vapoursynth_available:
            ffmpeg_status = "warn"
        else:
            ffmpeg_status = "fail"
        missing_str = ", ".join(ffmpeg_missing)
        ffmpeg_message = (
            f"Missing {missing_str}. Install FFmpeg or adjust renderer settings."
        )
    checks.append({
        "id": "ffmpeg",
        "label": "FFmpeg binaries",
        "status": ffmpeg_status,
        "message": ffmpeg_message,
    })

    audio_modules = {"librosa": importlib.util.find_spec("librosa"), "soundfile": importlib.util.find_spec("soundfile")}
    missing_audio = [name for name, spec in audio_modules.items() if spec is None]
    if not missing_audio:
        audio_status: DoctorStatus = "pass"
        audio_message = "Optional audio dependencies available."
    else:
        install_hint = "Install with 'uv pip install frame-compare[audio]'."
        if audio_enabled:
            audio_status = "fail"
            audio_message = f"Missing {', '.join(missing_audio)}. {install_hint}"
        else:
            audio_status = "warn"
            audio_message = f"Missing {', '.join(missing_audio)} (audio alignment disabled). {install_hint}"
    checks.append({
        "id": "audio",
        "label": "Audio alignment deps",
        "status": audio_status,
        "message": audio_message,
    })

    vspreview_detected = bool(shutil.which("vspreview") or importlib.util.find_spec("vspreview"))
    pyside_available = importlib.util.find_spec("PySide6") is not None
    if vspreview_detected and pyside_available:
        vs_status: DoctorStatus = "pass"
        vs_message = "VSPreview tooling available."
    else:
        if vspreview_enabled:
            vs_status = "fail"
            vs_message = "VSPreview extras missing. Install the 'preview' extras group."
        else:
            vs_status = "warn"
            vs_message = "VSPreview extras not detected (feature disabled)."
    checks.append({
        "id": "vspreview",
        "label": "VSPreview extras",
        "status": vs_status,
        "message": vs_message,
    })

    if auto_upload:
        slowpics_status: DoctorStatus = "warn"
        slowpics_message = (
            "[slowpics].auto_upload is enabled. Allow network access to https://slow.pics/ or disable auto_upload."
        )
    else:
        slowpics_status = "pass"
        slowpics_message = "Slow.pics auto-upload disabled."
    checks.append({
        "id": "slowpics",
        "label": "slow.pics network",
        "status": slowpics_status,
        "message": slowpics_message,
    })

    pyperclip_spec = importlib.util.find_spec("pyperclip")
    if auto_upload and pyperclip_spec is None:
        clip_status: DoctorStatus = "warn"
        clip_message = "Clipboard helper missing. Install 'pyperclip' or ignore to skip clipboard copying."
    else:
        clip_status = "pass"
        if auto_upload:
            clip_message = "pyperclip available for clipboard copy."
        else:
            clip_message = "Clipboard helper optional when slow.pics auto-upload is disabled."
    checks.append({
        "id": "pyperclip",
        "label": "Clipboard helper",
        "status": clip_status,
        "message": clip_message,
    })

    return checks, notes


def _emit_doctor_results(
    checks: Sequence[DoctorCheck],
    notes: Sequence[str],
    *,
    json_mode: bool,
    workspace_root: Path,
    config_path: Path,
) -> None:
    """Render doctor results either as text table or JSON payload."""

    if json_mode:
        payload = {
            "workspace_root": str(workspace_root),
            "config_path": str(config_path),
            "checks": list(checks),
            "notes": list(notes),
        }
        click.echo(json.dumps(payload, indent=2))
        return

    if checks:
        width = max(len(check["label"]) for check in checks)
    else:
        width = 0
    for check in checks:
        icon = _DOCTOR_STATUS_ICONS.get(check["status"], "•")
        label = check["label"].ljust(width)
        click.echo(f"{icon} {label} — {check['message']}")
    if notes:
        click.echo("Notes:")
        for note in notes:
            click.echo(f"  - {note}")


def _parse_metadata(files: Sequence[Path], naming_cfg: NamingConfig) -> List[Dict[str, str]]:
    """Extract naming metadata for each clip using configured heuristics."""
    metadata: List[Dict[str, str]] = []
    for file in files:
        info = parse_filename_metadata(
            file.name,
            prefer_guessit=naming_cfg.prefer_guessit,
            always_full_filename=naming_cfg.always_full_filename,
        )
        metadata.append(info)
    _dedupe_labels(metadata, files, naming_cfg.always_full_filename)
    return metadata


_VERSION_PATTERN = re.compile(r"(?:^|[^0-9A-Za-z])(?P<tag>v\d{1,3})(?!\d)", re.IGNORECASE)


def _extract_version_suffix(file_path: Path) -> str | None:
    """Return a version suffix (for example ``v2``) from *file_path* stem."""
    match = _VERSION_PATTERN.search(file_path.stem)
    if not match:
        return None
    tag = match.group("tag")
    return tag.upper() if tag else None


def _dedupe_labels(
    metadata: Sequence[Dict[str, str]],
    files: Sequence[Path],
    prefer_full_name: bool,
) -> None:
    """Guarantee unique labels by appending version hints when required."""
    counts = Counter((meta.get("label") or "") for meta in metadata)
    duplicate_groups: dict[str, list[int]] = defaultdict(list)
    for idx, meta in enumerate(metadata):
        label = meta.get("label") or ""
        if not label:
            meta["label"] = files[idx].name
            continue
        if counts[label] > 1:
            duplicate_groups[label].append(idx)

    if prefer_full_name:
        for indices in duplicate_groups.values():
            for idx in indices:
                metadata[idx]["label"] = files[idx].name
        return

    for label, indices in duplicate_groups.items():
        for idx in indices:
            version = _extract_version_suffix(files[idx])
            if version:
                metadata[idx]["label"] = f"{label} {version}".strip()

        temp_counts = Counter(metadata[idx].get("label") or "" for idx in indices)
        for idx in indices:
            resolved = metadata[idx].get("label") or label
            if temp_counts[resolved] <= 1:
                continue
            order = indices.index(idx) + 1
            metadata[idx]["label"] = f"{resolved} #{order}"

    for idx, meta in enumerate(metadata):
        if not (meta.get("label") or "").strip():
            meta["label"] = files[idx].name


def _parse_audio_track_overrides(entries: Iterable[str]) -> Dict[str, int]:
    """Parse override entries like "release=2" into a lowercase mapping."""
    mapping: Dict[str, int] = {}
    for entry in entries:
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        key = key.strip().lower()
        if not key:
            continue
        try:
            mapping[key] = int(value.strip())
        except ValueError:
            continue
    return mapping


def _first_non_empty(metadata: Sequence[Mapping[str, str]], key: str) -> str:
    """Return the first truthy value for *key* within *metadata*."""
    for meta in metadata:
        value = meta.get(key)
        if value:
            return str(value)
    return ""


def _parse_year_hint(value: str) -> Optional[int]:
    """Parse a year hint string into an integer between 1900 and 2100."""
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    if 1900 <= year <= 2100:
        return year
    return None


@dataclass
class TMDBLookupResult:
    """Outcome of the TMDB workflow (resolution, manual overrides, or failure)."""

    resolution: TMDBResolution | None
    manual_override: tuple[str, str] | None
    error_message: Optional[str]
    ambiguous: bool


def _should_retry_tmdb_error(message: str) -> bool:
    """Return True when *message* indicates a transient TMDB/HTTP failure."""

    lowered = message.lower()
    transient_markers = (
        "request failed",
        "timeout",
        "temporarily",
        "connection",
        "503",
        "502",
        "504",
        "429",
    )
    return any(marker in lowered for marker in transient_markers)


def _resolve_tmdb_blocking(
    *,
    file_name: str,
    tmdb_cfg: TMDBConfig,
    year_hint: Optional[int],
    imdb_id: Optional[str],
    tvdb_id: Optional[str],
    attempts: int = 3,
    transport_retries: int = 2,
) -> TMDBResolution | None:
    """Resolve TMDB metadata even when the caller already owns an event loop."""

    max_attempts = max(1, attempts)
    backoff = 0.75
    for attempt in range(max_attempts):
        transport_cls = getattr(httpx, "AsyncHTTPTransport", None)
        if transport_cls is None:
            raise RuntimeError("httpx.AsyncHTTPTransport is unavailable in this environment")
        transport = transport_cls(retries=max(0, transport_retries))

        async def _make_coro():
            return await resolve_tmdb(
                file_name,
                config=tmdb_cfg,
                year=year_hint,
                imdb_id=imdb_id,
                tvdb_id=tvdb_id,
                unattended=tmdb_cfg.unattended,
                category_preference=tmdb_cfg.category_preference,
                http_transport=transport,
            )

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(_make_coro())

            result_holder: list[TMDBResolution | None] = []
            error_holder: list[BaseException] = []

            def _worker() -> None:
                try:
                    result_holder.append(asyncio.run(_make_coro()))
                except BaseException as exc:  # pragma: no cover - bubbled up when joined
                    error_holder.append(exc)

            thread = threading.Thread(target=_worker, daemon=True)
            thread.start()
            thread.join()
            if error_holder:
                raise error_holder[0]
            return result_holder[0] if result_holder else None
        except TMDBResolutionError as exc:
            message = str(exc)
            if attempt + 1 >= max_attempts or not _should_retry_tmdb_error(message):
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
        finally:
            close_fn = getattr(transport, "close", None)
            if callable(close_fn):
                close_fn()
    return None


def resolve_tmdb_workflow(
    *,
    files: Sequence[Path],
    metadata: Sequence[Mapping[str, str]],
    tmdb_cfg: TMDBConfig,
    year_hint_raw: Optional[str] = None,
) -> TMDBLookupResult:
    """
    Resolve TMDB metadata for the current comparison set, prompting when needed.
    """

    if not files or not tmdb_cfg.api_key.strip():
        return TMDBLookupResult(
            resolution=None,
            manual_override=None,
            error_message=None,
            ambiguous=False,
        )

    base_file = files[0]
    imdb_hint_raw = _first_non_empty(metadata, "imdb_id")
    imdb_hint = imdb_hint_raw.lower() if imdb_hint_raw else None
    tvdb_hint = _first_non_empty(metadata, "tvdb_id") or None
    effective_year_hint = year_hint_raw or _first_non_empty(metadata, "year")
    year_hint = _parse_year_hint(effective_year_hint)

    resolution: TMDBResolution | None = None
    manual_tmdb: tuple[str, str] | None = None
    error_message: Optional[str] = None
    ambiguous = False

    try:
        resolution = _resolve_tmdb_blocking(
            file_name=base_file.name,
            tmdb_cfg=tmdb_cfg,
            year_hint=year_hint,
            imdb_id=imdb_hint,
            tvdb_id=tvdb_hint,
        )
    except TMDBAmbiguityError as exc:
        ambiguous = True
        if tmdb_cfg.unattended:
            error_message = (
                "TMDB returned multiple matches but unattended mode prevented prompts."
            )
        else:
            manual_tmdb = _prompt_manual_tmdb(exc.candidates)
    except TMDBResolutionError as exc:
        error_message = str(exc)
    else:
        if resolution is not None and tmdb_cfg.confirm_matches and not tmdb_cfg.unattended:
            accepted, override = _prompt_tmdb_confirmation(resolution)
            if override:
                manual_tmdb = override
                resolution = None
            elif not accepted:
                resolution = None

    return TMDBLookupResult(
        resolution=resolution,
        manual_override=manual_tmdb,
        error_message=error_message,
        ambiguous=ambiguous,
    )


def _prompt_manual_tmdb(candidates: Sequence[TMDBCandidate]) -> tuple[str, str] | None:
    """Prompt the user to choose a TMDB candidate when multiple matches exist."""
    print("[yellow]TMDB search returned multiple plausible matches:[/yellow]")
    for cand in candidates:
        year = cand.year or "????"
        print(
            f"  • [cyan]{cand.category.lower()}/{cand.tmdb_id}[/cyan] "
            f"{cand.title or '(unknown title)'} ({year}) score={cand.score:0.3f}"
        )
    while True:
        response = click.prompt(
            "Enter TMDB id (movie/##### or tv/#####) or leave blank to skip",
            default="",
            show_default=False,
        ).strip()
        if not response:
            return None
        try:
            return parse_manual_id(response)
        except TMDBResolutionError as exc:
            print(f"[red]Invalid TMDB identifier:[/red] {exc}")


def _prompt_tmdb_confirmation(
    resolution: TMDBResolution,
) -> tuple[bool, tuple[str, str] | None]:
    """Ask the user to confirm the TMDB result or supply a manual override."""
    title = resolution.title or resolution.original_title or "(unknown title)"
    year = resolution.year or "????"
    category = resolution.category.lower()
    link = f"https://www.themoviedb.org/{category}/{resolution.tmdb_id}"
    print(
        "[cyan]TMDB match found:[/cyan] "
        f"{title} ({year}) -> [underline]{link}[/underline]"
    )
    while True:
        response = click.prompt(
            "Confirm TMDB match? [Y/n or enter movie/#####]",
            default="y",
            show_default=False,
        ).strip()
        if not response or response.lower() in {"y", "yes"}:
            return True, None
        if response.lower() in {"n", "no"}:
            return False, None
        try:
            manual = parse_manual_id(response)
        except TMDBResolutionError as exc:
            print(f"[red]Invalid TMDB identifier:[/red] {exc}")
        else:
            return True, manual


def _render_collection_name(template_text: str, context: Mapping[str, str]) -> str:
    """Render the configured TMDB collection template with *context* values."""
    if "${" not in template_text:
        return template_text
    try:
        template = Template(template_text)
        return template.safe_substitute(context)
    except Exception:
        return template_text


def _estimate_analysis_time(file: Path, cache_dir: Path | None) -> float:
    """Estimate time to read two small windows of frames via VapourSynth.

    Mirrors the legacy heuristic: read ~15 frames around 1/3 and 2/3 into the clip,
    average the elapsed time. Returns +inf on failure so slower/unreadable clips are avoided.
    """
    try:
        clip = vs_core.init_clip(str(file), cache_dir=str(cache_dir) if cache_dir else None)
    except Exception:
        return float("inf")

    try:
        total = getattr(clip, "num_frames", 0)
        if not isinstance(total, int) or total <= 1:
            return float("inf")
        read_len = 15
        # safeguard when the clip is very short
        while (total // 3) + 1 < read_len and read_len > 1:
            read_len -= 1

        stats = clip.std.PlaneStats()

        def _read_window(base: int) -> float:
            start = max(0, min(base, max(0, total - 1)))
            t0 = time.perf_counter()
            for j in range(read_len):
                idx = min(start + j, max(0, total - 1))
                frame = stats.get_frame(idx)
                del frame
            return time.perf_counter() - t0

        t1 = _read_window(total // 3)
        t2 = _read_window((2 * total) // 3)
        return (t1 + t2) / 2.0
    except Exception:
        return float("inf")


def _pick_analyze_file(
    files: Sequence[Path],
    metadata: Sequence[Mapping[str, str]],
    target: str | None,
    *,
    cache_dir: Path | None = None,
) -> Path:
    """Resolve the clip to analyse, honouring user targets and heuristics."""
    if not files:
        raise ValueError("No files to analyze")
    target = (target or "").strip()
    if not target:
        # Legacy parity: default to the file with the smallest estimated read time.
        print("[cyan]Determining which file to analyze...[/cyan]")
        times = [(_estimate_analysis_time(file, cache_dir), idx) for idx, file in enumerate(files)]
        times.sort(key=lambda x: x[0])
        fastest_idx = times[0][1] if times else 0
        return files[fastest_idx]

    target_lower = target.lower()

    # Allow numeric index selection
    if target.isdigit():
        idx = int(target)
        if 0 <= idx < len(files):
            return files[idx]

    for idx, file in enumerate(files):
        if file.name.lower() == target_lower or file.stem.lower() == target_lower:
            return file
        meta = metadata[idx]
        for key in ("label", "release_group", "anime_title", "file_name"):
            value = str(meta.get(key) or "")
            if value and value.lower() == target_lower:
                return file
        if target_lower == str(idx):
            return file

    return files[0]


def _normalise_override_mapping(raw: Mapping[str, _OverrideValue]) -> Dict[str, _OverrideValue]:
    """Lowercase override keys and drop empty entries."""
    normalised: Dict[str, _OverrideValue] = {}
    for key, value in raw.items():
        key_str = str(key).strip().lower()
        if key_str:
            normalised[key_str] = value
    return normalised


def _match_override(
    index: int,
    file: Path,
    metadata: Mapping[str, str],
    mapping: Mapping[str, _OverrideValue],
) -> Optional[_OverrideValue]:
    """Return the override value matching *index*, file names, or metadata labels."""
    candidates = [
        str(index),
        file.name,
        file.stem,
        metadata.get("release_group", ""),
        metadata.get("file_name", ""),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        value = mapping.get(candidate.lower())
        if value is not None:
            return value
    return None


def _build_plans(files: Sequence[Path], metadata: Sequence[Dict[str, str]], cfg: AppConfig) -> List[_ClipPlan]:
    """Construct clip plans with per-file trim/FPS overrides applied."""
    trim_map = _normalise_override_mapping(cfg.overrides.trim)
    trim_end_map = _normalise_override_mapping(cfg.overrides.trim_end)
    fps_map = _normalise_override_mapping(cfg.overrides.change_fps)

    plans: List[_ClipPlan] = []
    for idx, file in enumerate(files):
        meta = dict(metadata[idx])
        plan = _ClipPlan(path=file, metadata=meta)

        trim_val = _match_override(idx, file, meta, trim_map)
        if trim_val is not None:
            plan.trim_start = int(trim_val)
            plan.has_trim_start_override = True

        trim_end_val = _match_override(idx, file, meta, trim_end_map)
        if trim_end_val is not None:
            plan.trim_end = int(trim_end_val)
            plan.has_trim_end_override = True

        fps_val = _match_override(idx, file, meta, fps_map)
        if isinstance(fps_val, str):
            if fps_val.lower() == "set":
                plan.use_as_reference = True
        elif isinstance(fps_val, list):
            if len(fps_val) == 2:
                plan.fps_override = (int(fps_val[0]), int(fps_val[1]))
        elif fps_val is not None:
            raise ValueError("Unsupported change_fps override type")

        plans.append(plan)

    return plans


def _extract_clip_fps(clip: object) -> Tuple[int, int]:
    """Return (fps_num, fps_den) from *clip*, defaulting to 24000/1001 when missing."""
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    if isinstance(num, int) and isinstance(den, int) and den:
        return (num, den)
    return (24000, 1001)


def _format_seconds(value: float) -> str:
    """
    Format a time value in seconds as an HH:MM:SS.s string with one decimal place.

    Negative input is treated as zero. The seconds component is rounded to one decimal place and may carry into minutes (and similarly minutes into hours) when rounding produces overflow.

    Parameters:
        value (float): Time in seconds.

    Returns:
        str: Formatted time as "HH:MM:SS.s" with two-digit hours and minutes and one decimal place for seconds.
    """
    total = max(0.0, float(value))
    hours = int(total // 3600)
    minutes = int((total - hours * 3600) // 60)
    seconds = total - hours * 3600 - minutes * 60
    seconds = round(seconds, 1)
    if seconds >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        hours += 1
    return f"{hours:02d}:{minutes:02d}:{seconds:04.1f}"


def _fps_to_float(value: Tuple[int, int] | None) -> float:
    """
    Convert an FPS expressed as a (numerator, denominator) tuple into a floating-point frames-per-second value.

    Parameters:
        value ((int, int) | None): A two-integer tuple representing FPS as (numerator, denominator). May be None.

    Returns:
        float: The FPS as a float. Returns 0.0 if `value` is None, the denominator is zero, or the tuple is invalid.
    """
    if not value:
        return 0.0
    num, den = value
    if not den:
        return 0.0
    return float(num) / float(den)


def _fold_sequence(
    values: Sequence[object],
    *,
    head: int,
    tail: int,
    joiner: str,
    enabled: bool,
) -> str:
    """
    Produce a compact string representation of a sequence by optionally folding the middle elements with an ellipsis.

    Parameters:
        values (Sequence[object]): Items to render; each item is stringified.
        head (int): Number of items to keep from the start when folding is enabled.
        tail (int): Number of items to keep from the end when folding is enabled.
        joiner (str): Separator used to join items.
        enabled (bool): If True and the sequence is longer than head + tail, replace the omitted middle with "…".

    Returns:
        str: The joined string containing all items when folding is disabled or not needed, or a string containing the head items, a single "…" token, and the tail items when folding is applied.
    """
    items = [str(item) for item in values]
    if not enabled or len(items) <= head + tail:
        return joiner.join(items)
    head_items = items[: max(0, head)]
    tail_items = items[-max(0, tail) :]
    if not head_items:
        return joiner.join(tail_items)
    if not tail_items:
        return joiner.join(head_items)
    return joiner.join([*head_items, "…", *tail_items])


def _evaluate_rule_condition(condition: Optional[str], *, flags: Mapping[str, Any]) -> bool:
    """
    Evaluate a simple rule condition string against a mapping of flags.

    The condition may be None/empty (treated as satisfied), a flag name (satisfied if the flag is truthy), or a negated flag name prefixed with `!`. Known tokens `verbose` and `upload_enabled` are supported like any other flag name.

    Parameters:
        condition (Optional[str]): The rule expression to evaluate (e.g. "verbose", "!upload_enabled") or None/empty to always satisfy.
        flags (Mapping[str, Any]): Mapping of flag names to values; values are interpreted by their truthiness.

    Returns:
        True if the condition is satisfied given `flags`, False otherwise.
    """
    if not condition:
        return True
    expr = condition.strip()
    if not expr:
        return True
    if expr == "!verbose":
        return not bool(flags.get("verbose"))
    if expr == "verbose":
        return bool(flags.get("verbose"))
    if expr == "upload_enabled":
        return bool(flags.get("upload_enabled"))
    if expr == "!upload_enabled":
        return not bool(flags.get("upload_enabled"))
    return bool(flags.get(expr))


def _build_legacy_summary_lines(values: Mapping[str, Any], *, emit_json_tail: bool) -> List[str]:
    """
    Generate legacy human-readable summary lines from the collected layout values.

    Parameters:
        values (Mapping[str, Any]): Mapping containing layout sections (for example:
            "clips", "window", "analysis", "audio_alignment", "render",
            "tonemap", "cache"). The function reads specific keys from those
            sections to synthesize compact summary lines.

    Returns:
        List[str]: A list of non-empty summary lines suitable for the legacy
        textual summary display.
    """

    def _maybe_number(value: Any) -> float | None:
        """Convert numeric-like input to float, returning ``None`` on failure."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_number(value: Any, fmt: str, fallback: str) -> str:
        """Format numeric values with ``fmt``; fall back to the provided string."""
        number = _maybe_number(value)
        if number is None:
            return fallback
        return format(number, fmt)

    def _string(value: Any, fallback: str = "n/a") -> str:
        """Return lowercase booleans, fallback for ``None``, else ``str(value)``."""
        if value is None:
            return fallback
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _bool_text(value: Any) -> str:
        """
        Format a value as lowercase boolean text.

        Returns:
            `'true'` if the value evaluates to True, `'false'` otherwise.
        """
        return "true" if bool(value) else "false"

    clips = _coerce_str_mapping(values.get("clips"))
    window = _coerce_str_mapping(values.get("window"))
    analysis = _coerce_str_mapping(values.get("analysis"))
    counts = _coerce_str_mapping(analysis.get("counts")) if analysis else {}
    audio = _coerce_str_mapping(values.get("audio_alignment"))
    render = _coerce_str_mapping(values.get("render"))
    tonemap = _coerce_str_mapping(values.get("tonemap"))
    cache = _coerce_str_mapping(values.get("cache"))

    lines: List[str] = []

    clip_count = _string(clips.get("count"), "0")
    lead_text = _format_number(window.get("ignore_lead_seconds"), ".2f", "0.00")
    trail_text = _format_number(window.get("ignore_trail_seconds"), ".2f", "0.00")
    step_text = _string(analysis.get("step"), "0")
    downscale_text = _string(analysis.get("downscale_height"), "0")
    lines.append(
        f"Clips: {clip_count}  Window: lead={lead_text}s trail={trail_text}s  step={step_text} downscale={downscale_text}px"
    )

    offsets_text = _format_number(audio.get("offsets_sec"), "+.3f", "+0.000")
    offsets_file = _string(audio.get("offsets_filename"), "n/a")
    lines.append(
        f"Align: audio={_bool_text(audio.get('enabled'))}  offsets={offsets_text}s  file={offsets_file}"
    )

    lines.append(
        "Plan: "
        f"Dark={_string(counts.get('dark'), '0')} "
        f"Bright={_string(counts.get('bright'), '0')} "
        f"Motion={_string(counts.get('motion'), '0')} "
        f"Random={_string(counts.get('random'), '0')} "
        f"User={_string(counts.get('user'), '0')}  "
        f"sep={_format_number(analysis.get('screen_separation_sec'), '.1f', '0.0')}s"
    )

    lines.append(
        "Canvas: "
        f"single_res={_string(render.get('single_res'), '0')} "
        f"upscale={_bool_text(render.get('upscale'))} "
        f"crop=mod{_string(render.get('mod_crop'), '0')} "
        f"pad={_bool_text(render.get('center_pad'))}"
    )

    tonemap_curve = _string(tonemap.get("tone_curve"), "n/a")
    tonemap_target = _format_number(tonemap.get("target_nits"), ".0f", "0")
    tonemap_dst_min = _format_number(tonemap.get("dst_min_nits"), ".2f", "0.00")
    tonemap_knee = _format_number(tonemap.get("knee_offset"), ".2f", "0.00")
    tonemap_preset_label = _string(tonemap.get("dpd_preset"), "n/a")
    tonemap_cutoff = _format_number(tonemap.get("dpd_black_cutoff"), ".3f", "0.000")
    tonemap_gamma = _format_number(tonemap.get("post_gamma"), ".2f", "1.00")
    gamma_flag = "*" if bool(tonemap.get("post_gamma_enabled")) else ""
    dpd_enabled = bool(
        tonemap.get("dpd")
        if "dpd" in tonemap
        else tonemap.get("dynamic_peak_detection")
    )
    preset_suffix = f" ({tonemap_preset_label})" if dpd_enabled and tonemap_preset_label.lower() != "n/a" else ""
    lines.append(
        "Tonemap: "
        f"{tonemap_curve}@{tonemap_target}nits "
        f"dst_min={tonemap_dst_min} knee={tonemap_knee} "
        f"dpd={_bool_text(dpd_enabled)}"
        f"{preset_suffix} black_cutoff={tonemap_cutoff}  "
        f"gamma={tonemap_gamma}{gamma_flag}  "
        f"verify≤{_format_number(tonemap.get('verify_luma_threshold'), '.2f', '0.00')}"
    )

    lines.append(
        f"Output: {_string(render.get('out_dir'), 'n/a')}  compression={_string(render.get('compression'), 'n/a')}"
    )

    lines.append(f"Cache: {_string(cache.get('file'), 'n/a')}  {_string(cache.get('status'), 'unknown')}")

    frame_count = _string(analysis.get("output_frame_count"), "0")
    preview = _string(analysis.get("output_frames_preview"), "")
    preview_display = f"[{preview}]" if preview else "[]"
    if emit_json_tail:
        lines.append(
            f"Output frames: {frame_count}  e.g., {preview_display}  (full list in JSON)"
        )
    else:
        full_list = _string(analysis.get("output_frames_full"), "[]")
        lines.append(f"Output frames ({frame_count}): {full_list}")

    return [line for line in lines if line]


def _format_clock(seconds: Optional[float]) -> str:
    """Format seconds as H:MM:SS (or MM:SS) with a placeholder for invalid input."""
    if seconds is None or not math.isfinite(seconds):
        return "--:--"
    total = max(0, int(seconds + 0.5))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _init_clips(
    plans: Sequence[_ClipPlan],
    runtime_cfg: RuntimeConfig,
    cache_dir: Path | None,
    *,
    reporter: CliOutputManagerProtocol | None = None,
) -> None:
    """Initialise VapourSynth clips for each plan and capture source metadata."""
    vs_core.set_ram_limit(runtime_cfg.ram_limit_mb)

    def _indexing_note(filename: str) -> None:
        label = escape(filename)
        if reporter is not None:
            reporter.console.print(f"[dim][CACHE] Indexing {label}…[/]")
        else:
            print(f"[CACHE] Indexing {filename}…")

    cache_dir_str = str(cache_dir) if cache_dir is not None else None

    reference_index = next((idx for idx, plan in enumerate(plans) if plan.use_as_reference), None)
    reference_fps: Optional[Tuple[int, int]] = None

    if reference_index is not None:
        plan = plans[reference_index]
        clip = vs_core.init_clip(
            str(plan.path),
            trim_start=plan.trim_start,
            trim_end=plan.trim_end,
            cache_dir=cache_dir_str,
            indexing_notifier=_indexing_note,
        )
        plan.clip = clip
        plan.effective_fps = _extract_clip_fps(clip)
        plan.source_fps = plan.effective_fps
        plan.source_num_frames = int(getattr(clip, "num_frames", 0) or 0)
        plan.source_width = int(getattr(clip, "width", 0) or 0)
        plan.source_height = int(getattr(clip, "height", 0) or 0)
        reference_fps = plan.effective_fps

    for idx, plan in enumerate(plans):
        if idx == reference_index and plan.clip is not None:
            continue
        fps_override = plan.fps_override
        if fps_override is None and reference_fps is not None and idx != reference_index:
            fps_override = reference_fps

        clip = vs_core.init_clip(
            str(plan.path),
            trim_start=plan.trim_start,
            trim_end=plan.trim_end,
            fps_map=fps_override,
            cache_dir=cache_dir_str,
            indexing_notifier=_indexing_note,
        )
        plan.clip = clip
        plan.applied_fps = fps_override
        plan.effective_fps = _extract_clip_fps(clip)
        plan.source_fps = plan.effective_fps
        plan.source_num_frames = int(getattr(clip, "num_frames", 0) or 0)
        plan.source_width = int(getattr(clip, "width", 0) or 0)
        plan.source_height = int(getattr(clip, "height", 0) or 0)


def _resolve_selection_windows(
    plans: Sequence[_ClipPlan],
    analysis_cfg: AnalysisConfig,
) -> tuple[List[SelectionWindowSpec], tuple[int, int], bool]:
    specs: List[SelectionWindowSpec] = []
    min_total_frames: Optional[int] = None
    for plan in plans:
        clip = plan.clip
        if clip is None:
            raise CLIAppError("Clip initialisation failed")
        total_frames = int(getattr(clip, "num_frames", 0))
        if min_total_frames is None or total_frames < min_total_frames:
            min_total_frames = total_frames
        fps_num, fps_den = plan.effective_fps or _extract_clip_fps(clip)
        fps_val = fps_num / fps_den if fps_den else 0.0
        try:
            spec = compute_selection_window(
                total_frames,
                fps_val,
                analysis_cfg.ignore_lead_seconds,
                analysis_cfg.ignore_trail_seconds,
                analysis_cfg.min_window_seconds,
            )
        except TypeError as exc:
            detail = (
                f"Invalid analysis window values for {plan.path.name}: "
                f"lead={analysis_cfg.ignore_lead_seconds!r} "
                f"trail={analysis_cfg.ignore_trail_seconds!r} "
                f"min={analysis_cfg.min_window_seconds!r}"
            )
            raise CLIAppError(
                detail,
                rich_message=f"[red]{escape(detail)}[/red]",
            ) from exc
        specs.append(spec)

    if not specs:
        return [], (0, 0), False

    start = max(spec.start_frame for spec in specs)
    end = min(spec.end_frame for spec in specs)
    collapsed = False
    if end <= start:
        collapsed = True
        fallback_end = min_total_frames or 0
        start = 0
        end = fallback_end

    if end <= start:
        raise CLIAppError("No frames remain after applying ignore window")

    return specs, (start, end), collapsed


def _log_selection_windows(
    plans: Sequence[_ClipPlan],
    specs: Sequence[SelectionWindowSpec],
    intersection: tuple[int, int],
    *,
    collapsed: bool,
    analyze_fps: float,
) -> None:
    """Log per-clip selection windows plus the common intersection summary."""
    for plan, spec in zip(plans, specs):
        raw_label = plan.metadata.get("label") or plan.path.name
        label = escape((raw_label or plan.path.name).strip())
        print(
            f"[cyan]{label}[/]: Selecting frames within [start={spec.start_seconds:.2f}s, "
            f"end={spec.end_seconds:.2f}s] (frames [{spec.start_frame}, {spec.end_frame})) — "
            f"lead={spec.applied_lead_seconds:.2f}s, trail={spec.applied_trail_seconds:.2f}s"
        )
        for warning in spec.warnings:
            print(f"[yellow]{label}[/]: {warning}")

    start_frame, end_frame = intersection
    if analyze_fps > 0 and end_frame > start_frame:
        start_seconds = start_frame / analyze_fps
        end_seconds = end_frame / analyze_fps
    else:
        start_seconds = float(start_frame)
        end_seconds = float(end_frame)

    print(
        f"[cyan]Common selection window[/]: frames [{start_frame}, {end_frame}) — "
        f"seconds [{start_seconds:.2f}s, {end_seconds:.2f}s)"
    )

    if collapsed:
        print(
            "[yellow]Ignore lead/trail settings did not overlap across all sources; using fallback range.[/yellow]"
        )


def _resolve_alignment_reference(
    plans: Sequence[_ClipPlan],
    analyze_path: Path,
    reference_hint: str,
) -> _ClipPlan:
    """Choose the audio alignment reference plan using optional hint and fallbacks."""
    if not plans:
        raise CLIAppError("No clips available for alignment")

    hint = (reference_hint or "").strip().lower()
    if hint:
        if hint.isdigit():
            idx = int(hint)
            if 0 <= idx < len(plans):
                return plans[idx]
        for plan in plans:
            candidates = {
                plan.path.name.lower(),
                plan.path.stem.lower(),
                (plan.metadata.get("label") or "").lower(),
            }
            if hint in candidates and hint:
                return plan

    for plan in plans:
        if plan.path == analyze_path:
            return plan
    return plans[0]



def _maybe_apply_audio_alignment(
    plans: Sequence[_ClipPlan],
    cfg: AppConfig,
    analyze_path: Path,
    root: Path,
    audio_track_overrides: Mapping[str, int],
    reporter: CliOutputManagerProtocol | None = None,
) -> tuple[_AudioAlignmentSummary | None, _AudioAlignmentDisplayData | None]:
    """Apply audio alignment when enabled, returning summary and display data."""
    audio_cfg = cfg.audio_alignment
    prompt_reuse_offsets = _coerce_config_flag(audio_cfg.prompt_reuse_offsets)
    offsets_path = resolve_subdir(
        root,
        audio_cfg.offsets_filename,
        purpose="audio_alignment.offsets_filename",
    )
    display_data = _AudioAlignmentDisplayData(
        stream_lines=[],
        estimation_line=None,
        offset_lines=[],
        offsets_file_line=f"Offsets file: {offsets_path}",
        json_reference_stream=None,
        json_target_streams={},
        json_offsets_sec={},
        json_offsets_frames={},
        warnings=[],
        correlations={},
        threshold=float(audio_cfg.correlation_threshold),
    )

    def _warn(message: str) -> None:
        display_data.warnings.append(f"[AUDIO] {message}")

    vspreview_enabled = _coerce_config_flag(audio_cfg.use_vspreview)

    reference_plan: _ClipPlan | None = None
    if plans:
        reference_plan = _resolve_alignment_reference(plans, analyze_path, audio_cfg.reference)

    plan_labels: Dict[Path, str] = {plan.path: _plan_label(plan) for plan in plans}
    name_to_label: Dict[str, str] = {plan.path.name: plan_labels[plan.path] for plan in plans}

    existing_entries_cache: tuple[
        str | None, Dict[str, Dict[str, object]]
    ] | None = None

    def _load_existing_entries() -> tuple[str | None, Dict[str, Dict[str, object]]]:
        nonlocal existing_entries_cache
        if existing_entries_cache is None:
            try:
                reference_name, existing_entries_raw = audio_alignment.load_offsets(
                    offsets_path
                )
            except audio_alignment.AudioAlignmentError as exc:
                raise CLIAppError(
                    f"Failed to read audio offsets file: {exc}",
                    rich_message=f"[red]Failed to read audio offsets file:[/red] {exc}",
                ) from exc
            existing_entries_cache = (
                reference_name,
                cast(Dict[str, Dict[str, object]], existing_entries_raw),
            )
        return existing_entries_cache

    def _reuse_vspreview_manual_offsets_if_available(
        reference: _ClipPlan | None,
    ) -> _AudioAlignmentSummary | None:
        if not (vspreview_enabled and reference and plans):
            return None

        try:
            _, existing_entries = _load_existing_entries()
        except CLIAppError:
            if not audio_cfg.enable:
                return None
            raise

        vspreview_reuse: Dict[str, int] = {}
        allowed_keys = {plan.path.name for plan in plans}
        for key, value in existing_entries.items():
            if not isinstance(value, dict):
                continue
            status_obj = value.get("status")
            note_obj = value.get("note")
            frames_obj = value.get("frames")
            if not isinstance(status_obj, str) or not isinstance(frames_obj, (int, float)):
                continue
            if status_obj.strip().lower() != "manual":
                continue
            note_text = str(note_obj or "").strip().lower()
            if "vspreview" not in note_text:
                continue
            if key in allowed_keys:
                vspreview_reuse[key] = int(frames_obj)

        if not vspreview_reuse:
            return None

        if display_data.manual_trim_lines:
            display_data.manual_trim_lines.clear()
        label_map = {plan.path.name: plan_labels.get(plan.path, plan.path.name) for plan in plans}
        manual_trim_starts: Dict[str, int] = {}
        for plan in plans:
            key = plan.path.name
            if key not in vspreview_reuse:
                continue
            raw_frames_value = int(vspreview_reuse[key])
            applied_frames = max(raw_frames_value, 0)
            plan.trim_start = applied_frames
            plan.has_trim_start_override = (
                plan.has_trim_start_override or raw_frames_value != 0
            )
            manual_trim_starts[key] = raw_frames_value
            label = label_map.get(key, key)
            display_data.manual_trim_lines.append(
                f"VSPreview manual trim reused: {label} → {applied_frames}f"
            )

        filtered_vspreview = {key: value for key, value in vspreview_reuse.items() if key in allowed_keys}

        display_data.offset_lines = ["Audio offsets: VSPreview manual offsets applied"]
        if display_data.manual_trim_lines:
            display_data.offset_lines.extend(display_data.manual_trim_lines)

        display_data.json_offsets_frames = {
            label_map.get(key, key): int(value)
            for key, value in filtered_vspreview.items()
        }
        statuses_map = {key: "manual" for key in filtered_vspreview}
        return _AudioAlignmentSummary(
            offsets_path=offsets_path,
            reference_name=reference.path.name,
            measurements=(),
            applied_frames=dict(filtered_vspreview),
            baseline_shift=0,
            statuses=statuses_map,
            reference_plan=reference,
            final_adjustments=dict(filtered_vspreview),
            swap_details={},
            suggested_frames={},
            suggestion_mode=False,
            manual_trim_starts=manual_trim_starts,
            vspreview_manual_offsets=dict(filtered_vspreview),
        )

    reused_summary = _reuse_vspreview_manual_offsets_if_available(reference_plan)
    if reused_summary is not None:
        if not audio_cfg.enable:
            display_data.warnings.append(
                "[AUDIO] VSPreview manual alignment enabled — audio alignment disabled."
            )
        return reused_summary, display_data

    if not audio_cfg.enable:
        if vspreview_enabled and plans and reference_plan is not None:
            manual_trim_starts = {
                plan.path.name: int(plan.trim_start)
                for plan in plans
                if plan.trim_start > 0
            }
            if manual_trim_starts:
                for plan in plans:
                    trim = manual_trim_starts.get(plan.path.name)
                    if trim:
                        display_data.manual_trim_lines.append(
                            f"Existing manual trim: {plan_labels[plan.path]} → {trim}f"
                        )
            display_data.offset_lines = ["Audio offsets: not computed (manual alignment only)"]
            display_data.offset_lines.extend(display_data.manual_trim_lines)
            display_data.warnings.append(
                "[AUDIO] VSPreview manual alignment enabled — audio alignment disabled."
            )
            summary = _AudioAlignmentSummary(
                offsets_path=offsets_path,
                reference_name=reference_plan.path.name,
                measurements=(),
                applied_frames=dict(manual_trim_starts),
                baseline_shift=0,
                statuses={},
                reference_plan=reference_plan,
                final_adjustments={},
                swap_details={},
                suggested_frames={},
                suggestion_mode=True,
                manual_trim_starts=manual_trim_starts,
            )
            return summary, display_data
        return None, display_data
    if len(plans) < 2:
        _warn("Audio alignment skipped: need at least two clips.")
        return None, display_data

    assert reference_plan is not None
    targets = [plan for plan in plans if plan is not reference_plan]
    if not targets:
        _warn("Audio alignment skipped: no secondary clips to compare.")
        return None, display_data

    measurement_order = [plan.path.name for plan in plans]
    negative_override_notes: Dict[str, str] = {}

    def _maybe_reuse_cached_offsets(
        reference: _ClipPlan,
        candidate_targets: Sequence[_ClipPlan],
    ) -> _AudioAlignmentSummary | None:
        if not prompt_reuse_offsets:
            return None
        if not sys.stdin.isatty():
            return None
        try:
            cached_reference, existing_entries = _load_existing_entries()
        except CLIAppError:
            return None
        if not existing_entries:
            return None
        if cached_reference is not None and cached_reference != reference.path.name:
            return None

        required_names = [plan.path.name for plan in candidate_targets]
        if any(name not in existing_entries for name in required_names):
            return None

        if click.confirm(
            "Recompute audio offsets using current clips?",
            default=True,
            show_default=True,
        ):
            return None

        display_data.estimation_line = (
            f"Audio offsets reused from existing file ({offsets_path.name})."
        )

        plan_map: Dict[str, _ClipPlan] = {plan.path.name: plan for plan in plans}

        def _get_float(value: object) -> float | None:
            if isinstance(value, (int, float)):
                float_value = float(value)
                if math.isnan(float_value):
                    return None
                return float_value
            return None

        def _get_int(value: object) -> int | None:
            if isinstance(value, (int, float)):
                float_value = float(value)
                if math.isnan(float_value):
                    return None
                return int(float_value)
            return None

        reference_entry = existing_entries.get(reference.path.name)
        reference_manual_frames: int | None = None
        reference_manual_seconds: float | None = None
        if isinstance(reference_entry, Mapping):
            status_obj = reference_entry.get("status")
            if isinstance(status_obj, str) and status_obj.strip().lower() == "manual":
                reference_manual_frames = _get_int(reference_entry.get("frames"))
                reference_manual_seconds = _get_float(reference_entry.get("seconds"))
                if (
                    reference_manual_seconds is None
                    and reference_manual_frames is not None
                ):
                    fps_guess = _get_float(reference_entry.get("target_fps")) or _get_float(
                        reference_entry.get("reference_fps")
                    )
                    if fps_guess and fps_guess > 0:
                        reference_manual_seconds = reference_manual_frames / fps_guess

        measurements: list["AlignmentMeasurement"] = []
        swap_details: Dict[str, str] = {}
        negative_offsets: Dict[str, bool] = {}

        def _build_measurement(name: str, entry: Mapping[str, object]) -> "AlignmentMeasurement":
            plan = plan_map[name]
            frames_val = _get_int(entry.get("frames")) if entry else None
            seconds_val = _get_float(entry.get("seconds")) if entry else None
            target_fps = _get_float(entry.get("target_fps")) if entry else None
            reference_fps = _get_float(entry.get("reference_fps")) if entry else None
            status_obj = entry.get("status") if entry else None
            is_manual = isinstance(status_obj, str) and status_obj.strip().lower() == "manual"
            if seconds_val is None and frames_val is not None:
                fps_val = target_fps if target_fps and target_fps > 0 else reference_fps
                if fps_val and fps_val > 0:
                    seconds_val = frames_val / fps_val
            if is_manual and reference_manual_frames is not None:
                if frames_val is not None:
                    frames_val -= reference_manual_frames
                if seconds_val is not None and reference_manual_seconds is not None:
                    seconds_val -= reference_manual_seconds
                elif seconds_val is None and frames_val is not None:
                    fps_val = target_fps if target_fps and target_fps > 0 else reference_fps
                    if fps_val and fps_val > 0:
                        seconds_val = frames_val / fps_val
            correlation_val = _get_float(entry.get("correlation")) if entry else None
            error_obj = entry.get("error") if entry else None
            error_val = str(error_obj).strip() if isinstance(error_obj, str) and error_obj.strip() else None
            measurement = audio_alignment.AlignmentMeasurement(
                file=plan.path,
                offset_seconds=seconds_val if seconds_val is not None else 0.0,
                frames=frames_val,
                correlation=correlation_val if correlation_val is not None else 0.0,
                reference_fps=reference_fps,
                target_fps=target_fps,
                error=error_val,
            )
            note_obj = entry.get("note") if entry else None
            if isinstance(note_obj, str) and note_obj.strip():
                note_text = note_obj.strip()
                swap_details[name] = note_text
                if "opposite clip" in note_text.lower():
                    negative_offsets[name] = True
            return measurement

        for target_plan in candidate_targets:
            entry = existing_entries.get(target_plan.path.name)
            if entry is None:
                return None
            measurements.append(_build_measurement(target_plan.path.name, entry))

        reference_entry = existing_entries.get(reference.path.name)
        if reference_entry is not None:
            measurements.append(_build_measurement(reference.path.name, reference_entry))

        raw_warning_messages: List[str] = []
        for measurement in measurements:
            reasons: List[str] = []
            if measurement.error:
                reasons.append(measurement.error)
            if abs(measurement.offset_seconds) > audio_cfg.max_offset_seconds:
                reasons.append(
                    f"offset {measurement.offset_seconds:.3f}s exceeds limit {audio_cfg.max_offset_seconds:.3f}s"
                )
            if measurement.correlation < audio_cfg.correlation_threshold:
                reasons.append(
                    f"correlation {measurement.correlation:.2f} below threshold {audio_cfg.correlation_threshold:.2f}"
                )
            if measurement.frames is None:
                reasons.append("unable to derive frame offset (missing fps)")

            if reasons:
                measurement.frames = None
                measurement.error = "; ".join(reasons)
                file_key = measurement.file.name
                negative_offsets.pop(file_key, None)
                label = name_to_label.get(file_key, file_key)
                raw_warning_messages.append(f"{label}: {measurement.error}")

        for warning_message in dict.fromkeys(raw_warning_messages):
            _warn(warning_message)

        offset_lines: List[str] = []
        offsets_sec: Dict[str, float] = {}
        offsets_frames: Dict[str, int] = {}

        for measurement in measurements:
            clip_name = measurement.file.name
            if clip_name == reference.path.name and len(measurements) > 1:
                continue
            label = name_to_label.get(clip_name, clip_name)
            if measurement.offset_seconds is not None:
                offsets_sec[label] = float(measurement.offset_seconds)
            if measurement.frames is not None:
                offsets_frames[label] = int(measurement.frames)
            display_data.correlations[label] = float(measurement.correlation)

            if measurement.error:
                offset_lines.append(
                    f"Audio offsets: {label}: manual edit required ({measurement.error})"
                )
                continue

            fps_value = 0.0
            if measurement.target_fps and measurement.target_fps > 0:
                fps_value = float(measurement.target_fps)
            elif measurement.reference_fps and measurement.reference_fps > 0:
                fps_value = float(measurement.reference_fps)

            frames_text = "n/a"
            if measurement.frames is not None:
                frames_text = f"{measurement.frames:+d}f"
            fps_text = f"{fps_value:.3f}" if fps_value > 0 else "0.000"
            suffix = ""
            if clip_name in negative_offsets:
                suffix = " (reference advanced; trimming target)"
            offset_lines.append(
                f"Audio offsets: {label}: {measurement.offset_seconds:+.3f}s ({frames_text} @ {fps_text}){suffix}"
            )
            detail = swap_details.get(clip_name)
            if detail:
                offset_lines.append(f"  note: {detail}")

        if not offset_lines:
            offset_lines.append("Audio offsets: none detected")

        display_data.offset_lines = offset_lines
        display_data.json_offsets_sec = offsets_sec
        display_data.json_offsets_frames = offsets_frames

        suggested_frames: Dict[str, int] = {}
        for measurement in measurements:
            if measurement.frames is not None:
                suggested_frames[measurement.file.name] = int(measurement.frames)

        applied_frames: Dict[str, int] = {}
        statuses: Dict[str, str] = {}
        for name, entry in existing_entries.items():
            if name not in plan_map:
                continue
            frames_val = _get_int(entry.get("frames")) if entry else None
            if frames_val is not None:
                applied_frames[name] = frames_val
            status_obj = entry.get("status") if entry else None
            if isinstance(status_obj, str):
                statuses[name] = status_obj

        final_map: Dict[str, int] = {reference.path.name: 0}
        for name, frames in applied_frames.items():
            final_map[name] = frames

        baseline = min(final_map.values()) if final_map else 0
        baseline_shift = int(-baseline) if baseline < 0 else 0

        final_adjustments: Dict[str, int] = {}
        for plan in plans:
            desired = final_map.get(plan.path.name)
            if desired is None:
                continue
            adjustment = int(desired - baseline)
            if adjustment < 0:
                adjustment = 0
            if adjustment:
                plan.trim_start = max(0, plan.trim_start + adjustment)
                plan.alignment_frames = adjustment
                plan.alignment_status = statuses.get(plan.path.name, "auto")
            else:
                plan.alignment_frames = 0
                if plan.path.name in statuses:
                    plan.alignment_status = statuses.get(plan.path.name, "auto")
                else:
                    plan.alignment_status = ""
            final_adjustments[plan.path.name] = adjustment

        if baseline_shift:
            for plan in plans:
                if plan is reference:
                    plan.alignment_status = "baseline"

        summary = _AudioAlignmentSummary(
            offsets_path=offsets_path,
            reference_name=reference.path.name,
            measurements=measurements,
            applied_frames=applied_frames,
            baseline_shift=baseline_shift,
            statuses=statuses,
            reference_plan=reference,
            final_adjustments=final_adjustments,
            swap_details=swap_details,
            suggested_frames=suggested_frames,
            suggestion_mode=False,
            manual_trim_starts={},
        )
        detail_map = _compose_measurement_details(
            measurements,
            applied_frames_map=applied_frames,
            statuses_map=statuses,
            suggestion_mode_active=False,
            manual_trims={},
            swap_map=swap_details,
            negative_notes=negative_override_notes,
        )
        summary.measured_offsets = detail_map
        _emit_measurement_lines(
            detail_map,
            measurement_order,
            append_manual=bool(display_data.manual_trim_lines),
        )
        return summary

    stream_infos: Dict[Path, List["AudioStreamInfo"]] = {}
    for plan in plans:
        try:
            infos = audio_alignment.probe_audio_streams(plan.path)
        except audio_alignment.AudioAlignmentError as exc:
            logger.warning("ffprobe audio stream probe failed for %s: %s", plan.path.name, exc)
            infos = []
        stream_infos[plan.path] = infos

    forced_streams: set[Path] = set()

    def _match_audio_override(plan: _ClipPlan) -> Optional[int]:
        """Return override index for *plan* when configured, otherwise ``None``."""
        value = _match_override(plans.index(plan), plan.path, plan.metadata, audio_track_overrides)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _pick_default(streams: Sequence["AudioStreamInfo"]) -> int:
        """Return default stream index, falling back to the first entry or zero."""
        if not streams:
            return 0
        for stream in streams:
            if stream.is_default:
                return stream.index
        return streams[0].index

    ref_override = _match_audio_override(reference_plan)
    if ref_override is not None:
        forced_streams.add(reference_plan.path)
    reference_stream_index = ref_override if ref_override is not None else _pick_default(
        stream_infos.get(reference_plan.path, [])
    )

    reference_stream_info = None
    for candidate in stream_infos.get(reference_plan.path, []):
        if candidate.index == reference_stream_index:
            reference_stream_info = candidate
            break

    def _score_candidate(candidate: "AudioStreamInfo") -> float:
        """
        Compute a heuristic quality score for an audio stream candidate relative to the (closure) reference stream.

        Parameters:
            candidate (audio_alignment.AudioStreamInfo): Audio stream metadata to evaluate.

        Returns:
            score (float): Higher values indicate a better match to the reference stream based on language, codec, channels, sample rate, bitrate, and flags (`is_default`, `is_forced`); used for ranking candidate streams.
        """
        base = 0.0
        if reference_stream_info is not None:
            if reference_stream_info.language and candidate.language == reference_stream_info.language:
                base += 100.0
            elif reference_stream_info.language and not candidate.language:
                base += 10.0
            if candidate.codec_name == reference_stream_info.codec_name:
                base += 30.0
            elif candidate.codec_name.split(".")[0] == reference_stream_info.codec_name.split(".")[0]:
                base += 20.0
            if candidate.channels == reference_stream_info.channels:
                base += 10.0
            if reference_stream_info.channel_layout and candidate.channel_layout == reference_stream_info.channel_layout:
                base += 5.0
            if reference_stream_info.sample_rate and candidate.sample_rate == reference_stream_info.sample_rate:
                base += 10.0
            elif reference_stream_info.sample_rate and candidate.sample_rate:
                base -= abs(candidate.sample_rate - reference_stream_info.sample_rate) / 1000.0
            if reference_stream_info.bitrate and candidate.bitrate:
                base -= abs(candidate.bitrate - reference_stream_info.bitrate) / 10000.0
        base += 3.0 if candidate.is_default else 0.0
        base += 1.0 if candidate.is_forced else 0.0
        if candidate.bitrate:
            base += candidate.bitrate / 1e5
        return base

    target_stream_indices: Dict[Path, int] = {}
    for target in targets:
        override_idx = _match_audio_override(target)
        if override_idx is not None:
            target_stream_indices[target.path] = override_idx
            forced_streams.add(target.path)
            continue
        infos = stream_infos.get(target.path, [])
        if not infos:
            target_stream_indices[target.path] = 0
            continue
        best = max(infos, key=_score_candidate)
        target_stream_indices[target.path] = best.index

    def _describe_stream(plan: _ClipPlan, stream_idx: int) -> tuple[str, str]:
        """
        Builds a human-readable label and a concise descriptor for the chosen audio stream of a clip.

        Parameters:
            plan (_ClipPlan): Clip plan whose path and label are used in the returned label.
            stream_idx (int): Index of the audio stream to describe.

        Returns:
            tuple[str, str]: A pair (display_label, descriptor) where `display_label` is formatted as
            "<clip_label>-><codec>/<language>/<layout>" with " (forced)" appended if the stream is marked forced,
            and `descriptor` is the "<codec>/<language>/<layout>" string.
        """
        infos = stream_infos.get(plan.path, [])
        picked = next((info for info in infos if info.index == stream_idx), None)
        codec = (picked.codec_name if picked and picked.codec_name else "unknown").strip() or "unknown"
        language = (picked.language if picked and picked.language else "und").strip() or "und"
        if picked and picked.channel_layout:
            layout = picked.channel_layout.strip()
        elif picked and picked.channels:
            layout = f"{picked.channels}ch"
        else:
            layout = "?"
        descriptor = f"{codec}/{language}/{layout}"
        forced_suffix = " (forced)" if plan.path in forced_streams else ""
        label = plan_labels[plan.path]
        return f"{label}->{descriptor}{forced_suffix}", descriptor

    reference_stream_text, reference_descriptor = _describe_stream(reference_plan, reference_stream_index)
    display_data.json_reference_stream = reference_stream_text
    stream_descriptors: Dict[str, str] = {reference_plan.path.name: reference_descriptor}

    for idx, target in enumerate(targets):
        stream_idx = target_stream_indices.get(target.path, 0)
        target_stream_text, target_descriptor = _describe_stream(target, stream_idx)
        display_data.json_target_streams[plan_labels[target.path]] = target_descriptor
        stream_descriptors[target.path.name] = target_descriptor
        if idx == 0:
            display_data.stream_lines.append(
                f"Audio streams: ref={reference_stream_text}  target={target_stream_text}"
            )
        else:
            display_data.stream_lines.append(f"Audio streams: target={target_stream_text}")

    def _format_measurement_line(detail: _AudioMeasurementDetail) -> str:
        stream_text = detail.stream or "?"
        seconds_text = (
            f"{detail.offset_seconds:+.3f}s"
            if detail.offset_seconds is not None
            else "n/a"
        )
        frames_text = (
            f"{detail.frames:+d}f" if detail.frames is not None else "n/a"
        )
        corr_text = (
            f"{detail.correlation:.2f}"
            if detail.correlation is not None and not math.isnan(detail.correlation)
            else "n/a"
        )
        applied_text = "applied" if detail.applied else "suggested"
        status_bits: List[str] = []
        if detail.status:
            status_bits.append(detail.status)
        status_bits.append(applied_text)
        status_text = "/".join(status_bits)
        return (
            f"Audio offsets: {detail.label}: [{stream_text}] "
            f"{seconds_text} ({frames_text}) corr={corr_text} status={status_text}"
        )

    def _emit_measurement_lines(
        detail_map: Dict[str, _AudioMeasurementDetail],
        order: Sequence[str],
        *,
        append_manual: bool = False,
    ) -> None:
        offsets_sec: Dict[str, float] = {}
        offsets_frames: Dict[str, int] = {}
        offset_lines: List[str] = []
        for name in order:
            detail = detail_map.get(name)
            if detail is None:
                continue
            if (
                name == reference_plan.path.name
                and len(detail_map) > 1
            ):
                continue
            if detail.offset_seconds is not None:
                offsets_sec[detail.label] = float(detail.offset_seconds)
            if detail.frames is not None:
                offsets_frames[detail.label] = int(detail.frames)
            offset_lines.append(_format_measurement_line(detail))
            if detail.note:
                offset_lines.append(f"  note: {detail.note}")
        if not offset_lines:
            offset_lines.append("Audio offsets: none detected")
        if append_manual and display_data.manual_trim_lines:
            offset_lines.extend(display_data.manual_trim_lines)
        display_data.offset_lines = offset_lines
        display_data.json_offsets_sec = offsets_sec
        display_data.json_offsets_frames = offsets_frames
        display_data.measurements = {
            detail.label: detail for detail in detail_map.values()
        }
        display_data.correlations = {
            detail.label: detail.correlation
            for detail in detail_map.values()
            if detail.correlation is not None
        }

    fps_lookup: Dict[str, float] = {}
    for plan in plans:
        fps_tuple = plan.effective_fps or plan.source_fps or plan.fps_override
        fps_lookup[plan.path.name] = _fps_to_float(fps_tuple)

    def _compose_measurement_details(
        measurement_seq: Sequence["AlignmentMeasurement"],
        *,
        applied_frames_map: Mapping[str, int] | None,
        statuses_map: Mapping[str, str] | None,
        suggestion_mode_active: bool,
        manual_trims: Mapping[str, int],
        swap_map: Mapping[str, str],
        negative_notes: Mapping[str, str],
    ) -> Dict[str, _AudioMeasurementDetail]:
        """
        Convert raw measurement objects into detail records used for CLI + JSON reporting.

        Parameters:
            measurement_seq: Measurements returned by the alignment pipeline.
            applied_frames_map: Mapping of clip names to frame adjustments actually applied.
            statuses_map: Mapping of clip names to status labels ("auto", "manual", etc.).
            suggestion_mode_active: True when offsets are suggestions only (VSPreview flow).
            manual_trims: Existing manual trims discovered earlier in the run.
            swap_map: Swap/notes per clip (e.g., "reference advanced" notes).
            negative_notes: Notes produced when negative offsets were redirected.

        Returns:
            Dict[str, _AudioMeasurementDetail]: Mapping keyed by clip filename.
        """

        detail_map: Dict[str, _AudioMeasurementDetail] = {}
        for measurement in measurement_seq:
            clip_name = measurement.file.name
            label = name_to_label.get(clip_name, clip_name)
            descriptor = stream_descriptors.get(clip_name, "")
            seconds_value: Optional[float]
            if measurement.offset_seconds is None:
                seconds_value = None
            else:
                seconds_value = float(measurement.offset_seconds)
            frames_value = int(measurement.frames) if measurement.frames is not None else None
            correlation_value: Optional[float]
            if measurement.correlation is None or math.isnan(measurement.correlation):
                correlation_value = None
            else:
                correlation_value = float(measurement.correlation)
            status_text = ""
            if statuses_map and clip_name in statuses_map:
                status_text = statuses_map[clip_name]
            applied_flag = False
            if not suggestion_mode_active and applied_frames_map and clip_name in applied_frames_map:
                applied_flag = True
            note_parts: List[str] = []
            swap_note = swap_map.get(clip_name)
            if swap_note:
                note_parts.append(swap_note)
            negative_note = negative_notes.get(clip_name)
            if negative_note:
                note_parts.append(negative_note)
            if measurement.error:
                note_parts.append(measurement.error)
                if not status_text:
                    status_text = "error"
                applied_flag = False
            note_value = " ".join(note_parts) if note_parts else None
            detail_map[clip_name] = _AudioMeasurementDetail(
                label=label,
                stream=descriptor,
                offset_seconds=seconds_value,
                frames=frames_value,
                correlation=correlation_value,
                status=status_text,
                applied=applied_flag,
                note=note_value,
            )

        for clip_name, trim_frames in manual_trims.items():
            if clip_name in detail_map:
                continue
            label = name_to_label.get(clip_name, clip_name)
            descriptor = stream_descriptors.get(clip_name, "")
            fps_value = fps_lookup.get(clip_name, 0.0)
            seconds_value = (trim_frames / fps_value) if fps_value else None
            detail_map[clip_name] = _AudioMeasurementDetail(
                label=label,
                stream=descriptor,
                offset_seconds=seconds_value,
                frames=int(trim_frames),
                correlation=None,
                status="manual",
                applied=not suggestion_mode_active,
                note=None,
            )
        return detail_map

    reused_cached = _maybe_reuse_cached_offsets(reference_plan, targets)
    if reused_cached is not None:
        summary = reused_cached
        detail_map: Dict[str, _AudioMeasurementDetail] = {}
        for plan in plans:
            key = plan.path.name
            frames_val = summary.applied_frames.get(key)
            seconds_val: Optional[float]
            fps_val = fps_lookup.get(key, 0.0)
            if frames_val is None or not fps_val:
                seconds_val = None
            else:
                seconds_val = frames_val / fps_val if fps_val else None
            descriptor = stream_descriptors.get(key, "")
            detail_map[key] = _AudioMeasurementDetail(
                label=name_to_label.get(key, key),
                stream=descriptor,
                offset_seconds=seconds_val,
                frames=frames_val,
                correlation=None,
                status=summary.statuses.get(key, "manual"),
                applied=True,
            )
        summary.measured_offsets = detail_map
        display_data.measurements = {
            detail.label: detail for detail in detail_map.values()
        }
        _emit_measurement_lines(
            detail_map,
            measurement_order,
            append_manual=bool(display_data.manual_trim_lines),
        )
        return summary, display_data

    reference_fps_tuple = reference_plan.effective_fps or reference_plan.source_fps
    reference_fps = _fps_to_float(reference_fps_tuple)
    max_offset = float(audio_cfg.max_offset_seconds)
    raw_duration = audio_cfg.duration_seconds if audio_cfg.duration_seconds is not None else None
    duration_seconds = float(raw_duration) if raw_duration is not None else None
    start_seconds = float(audio_cfg.start_seconds or 0.0)
    search_text = f"±{max_offset:.2f}s"
    window_text = f"{duration_seconds:.2f}s" if duration_seconds is not None else "auto"
    start_text = f"{start_seconds:.2f}s"
    display_data.estimation_line = (
        f"Estimating audio offsets … fps={reference_fps:.3f} "
        f"search={search_text} start={start_text} window={window_text}"
    )

    try:
        base_start = float(audio_cfg.start_seconds or 0.0)
        base_duration_param: Optional[float]
        if audio_cfg.duration_seconds is None:
            base_duration_param = None
        else:
            base_duration_param = float(audio_cfg.duration_seconds)
        hop_length = max(1, min(audio_cfg.hop_length, max(1, audio_cfg.sample_rate // 100)))

        measurements: List["AlignmentMeasurement"]
        negative_offsets: Dict[str, bool] = {}

        spinner_context: ContextManager[object]
        status_factory = None
        if reporter is not None and not getattr(reporter, "quiet", False):
            status_factory = getattr(reporter.console, "status", None)
        if callable(status_factory):
            spinner_context = cast(
                ContextManager[object],
                status_factory("[cyan]Estimating audio offsets…[/cyan]", spinner="dots"),
            )
        else:
            spinner_context = nullcontext()
        processed = 0
        start_time = time.perf_counter()
        total_targets = len(targets)

        with spinner_context as status:
            def _advance_audio(count: int) -> None:
                """
                Advance the audio-alignment progress by a given number of processed pairs.

                Parameters:
                    count (int): Number of audio pair measurements to add to the processed total.
                """
                nonlocal processed
                processed += count
                if status is None or total_targets <= 0:
                    return
                status_update = getattr(status, "update", None)
                if callable(status_update):
                    elapsed = time.perf_counter() - start_time
                    rate_val = processed / elapsed if elapsed > 0 else 0.0
                    status_update(
                        f"[cyan]Estimating audio offsets… {processed}/{total_targets} ({rate_val:0.2f} pairs/s)[/cyan]"
                    )

            measurements = audio_alignment.measure_offsets(
                reference_plan.path,
                [plan.path for plan in targets],
                sample_rate=audio_cfg.sample_rate,
                hop_length=hop_length,
                start_seconds=base_start,
                duration_seconds=base_duration_param,
                reference_stream=reference_stream_index,
                target_streams=target_stream_indices,
                progress_callback=_advance_audio,
            )

        frame_bias = int(audio_cfg.frame_offset_bias or 0)
        if frame_bias != 0:
            adjust_toward_zero = frame_bias > 0
            bias_magnitude = abs(frame_bias)

            for measurement in measurements:
                frames_val = measurement.frames
                if frames_val is None or frames_val == 0:
                    continue

                sign = 1 if frames_val > 0 else -1
                magnitude = abs(frames_val)

                if adjust_toward_zero:
                    shift = min(bias_magnitude, magnitude)
                    adjusted_magnitude = max(0, magnitude - shift)
                else:
                    adjusted_magnitude = magnitude + bias_magnitude

                if adjusted_magnitude == magnitude:
                    continue

                new_frames = sign * adjusted_magnitude
                measurement.frames = new_frames

                if measurement.target_fps and measurement.target_fps > 0:
                    measurement.offset_seconds = new_frames / measurement.target_fps
                elif measurement.reference_fps and measurement.reference_fps > 0:
                    measurement.offset_seconds = new_frames / measurement.reference_fps

        negative_override_notes.clear()
        swap_details: Dict[str, str] = {}
        swap_candidates: List["AlignmentMeasurement"] = []
        swap_enabled = len(targets) == 1

        for measurement in measurements:
            if measurement.frames is not None and measurement.frames < 0:
                if swap_enabled:
                    swap_candidates.append(measurement)
                    continue
                measurement.frames = abs(int(measurement.frames))
                file_key = measurement.file.name
                negative_offsets[file_key] = True
                negative_override_notes[file_key] = (
                    "Suggested negative offset applied to the opposite clip for trim-first behaviour."
                )

        if swap_enabled and swap_candidates:
            additional_measurements: List["AlignmentMeasurement"] = []
            reference_name: str = reference_plan.path.name
            existing_keys = {m.file.name for m in measurements}

            for measurement in swap_candidates:
                seconds = float(measurement.offset_seconds)
                seconds_abs = abs(seconds)
                target_name: str = measurement.file.name

                original_frames = None
                if measurement.frames is not None:
                    original_frames = abs(int(measurement.frames))

                reference_frames = None
                if measurement.reference_fps and measurement.reference_fps > 0:
                    reference_frames = int(round(seconds_abs * measurement.reference_fps))

                measurement.frames = 0
                measurement.offset_seconds = 0.0

                def _describe(frames: Optional[int], seconds_val: float) -> str:
                    parts: List[str] = []
                    if frames is not None:
                        parts.append(f"{frames} frame(s)")
                    if not math.isnan(seconds_val):
                        parts.append(f"{seconds_val:.3f}s")
                    return " / ".join(parts) if parts else "0.000s"

                measured_desc = _describe(original_frames, seconds_abs)
                applied_desc = _describe(reference_frames, seconds_abs)
                note = (
                    f"Measured negative offset on {target_name}: {measured_desc}; "
                    f"applied to {reference_name} as +{applied_desc}."
                )
                negative_override_notes[target_name] = note
                negative_override_notes[reference_name] = note
                swap_details[target_name] = note
                swap_details[reference_name] = note

                if reference_name not in existing_keys:
                    additional_measurements.append(
                        audio_alignment.AlignmentMeasurement(
                            file=reference_plan.path,
                            offset_seconds=seconds_abs,
                            frames=reference_frames,
                            correlation=measurement.correlation,
                            reference_fps=measurement.reference_fps,
                            target_fps=measurement.reference_fps,
                        )
                    )
                    existing_keys.add(reference_name)

            measurements.extend(additional_measurements)

        raw_warning_messages: List[str] = []
        for measurement in measurements:
            reasons: List[str] = []
            if measurement.error:
                reasons.append(measurement.error)
            if abs(measurement.offset_seconds) > audio_cfg.max_offset_seconds:
                reasons.append(
                    f"offset {measurement.offset_seconds:.3f}s exceeds limit {audio_cfg.max_offset_seconds:.3f}s"
                )
            if measurement.correlation < audio_cfg.correlation_threshold:
                reasons.append(
                    f"correlation {measurement.correlation:.2f} below threshold {audio_cfg.correlation_threshold:.2f}"
                )
            if measurement.frames is None:
                reasons.append("unable to derive frame offset (missing fps)")

            if reasons:
                measurement.frames = None
                measurement.error = "; ".join(reasons)
                file_key = measurement.file.name
                negative_offsets.pop(file_key, None)
                label = name_to_label.get(file_key, file_key)
                raw_warning_messages.append(f"{label}: {measurement.error}")

        for warning_message in dict.fromkeys(raw_warning_messages):
            _warn(warning_message)

        suggested_frames: Dict[str, int] = {}
        for measurement in measurements:
            if measurement.frames is not None:
                suggested_frames[measurement.file.name] = int(measurement.frames)

        manual_trim_starts: Dict[str, int] = {}
        if vspreview_enabled:
            for plan in plans:
                if plan.has_trim_start_override and plan.trim_start > 0:
                    manual_trim_starts[plan.path.name] = int(plan.trim_start)
                    label = plan_labels.get(plan.path, plan.path.name)
                    display_data.manual_trim_lines.append(
                        f"Existing manual trim: {label} → {plan.trim_start}f"
                    )
            display_data.warnings.append(
                "[AUDIO] VSPreview manual alignment enabled — offsets reported for guidance only."
            )
            summary = _AudioAlignmentSummary(
                offsets_path=offsets_path,
                reference_name=reference_plan.path.name,
                measurements=measurements,
                applied_frames=dict(manual_trim_starts),
                baseline_shift=0,
                statuses={m.file.name: "suggested" for m in measurements},
                reference_plan=reference_plan,
                final_adjustments={},
                swap_details=swap_details,
                suggested_frames=suggested_frames,
                suggestion_mode=True,
                manual_trim_starts=manual_trim_starts,
            )
            detail_map = _compose_measurement_details(
                measurements,
                applied_frames_map=summary.applied_frames,
                statuses_map=summary.statuses,
                suggestion_mode_active=True,
                manual_trims=manual_trim_starts,
                swap_map=swap_details,
                negative_notes=negative_override_notes,
            )
            summary.measured_offsets = detail_map
            _emit_measurement_lines(
                detail_map,
                measurement_order,
                append_manual=bool(display_data.manual_trim_lines),
            )
            return summary, display_data

        applied_frames, statuses = audio_alignment.update_offsets_file(
            offsets_path,
            reference_plan.path.name,
            measurements,
            _load_existing_entries()[1],
            negative_override_notes,
        )

        final_map: Dict[str, int] = {reference_plan.path.name: 0}
        for name, frames in applied_frames.items():
            final_map[name] = frames

        baseline = min(final_map.values()) if final_map else 0
        baseline_shift = int(-baseline) if baseline < 0 else 0

        final_adjustments: Dict[str, int] = {}
        for plan in plans:
            desired = final_map.get(plan.path.name)
            if desired is None:
                continue
            adjustment = int(desired - baseline)
            if adjustment < 0:
                adjustment = 0
            if adjustment:
                plan.trim_start = max(0, plan.trim_start + adjustment)
                plan.alignment_frames = adjustment
                plan.alignment_status = statuses.get(plan.path.name, "auto")
            else:
                plan.alignment_frames = 0
                plan.alignment_status = statuses.get(plan.path.name, "auto") if plan.path.name in statuses else ""
            final_adjustments[plan.path.name] = adjustment

        if baseline_shift:
            for plan in plans:
                if plan is reference_plan:
                    plan.alignment_status = "baseline"

        summary = _AudioAlignmentSummary(
            offsets_path=offsets_path,
            reference_name=reference_plan.path.name,
            measurements=measurements,
            applied_frames=applied_frames,
            baseline_shift=baseline_shift,
            statuses=statuses,
            reference_plan=reference_plan,
            final_adjustments=final_adjustments,
            swap_details=swap_details,
            suggested_frames=suggested_frames,
            suggestion_mode=False,
            manual_trim_starts=manual_trim_starts,
        )
        detail_map = _compose_measurement_details(
            measurements,
            applied_frames_map=applied_frames,
            statuses_map=statuses,
            suggestion_mode_active=False,
            manual_trims=manual_trim_starts,
            swap_map=swap_details,
            negative_notes=negative_override_notes,
        )
        summary.measured_offsets = detail_map
        _emit_measurement_lines(
            detail_map,
            measurement_order,
            append_manual=bool(display_data.manual_trim_lines),
        )
        return summary, display_data
    except audio_alignment.AudioAlignmentError as exc:
        raise CLIAppError(
            f"Audio alignment failed: {exc}",
            rich_message=f"[red]Audio alignment failed:[/red] {exc}",
        ) from exc


def _color_config_literal(color_cfg: ColorConfig) -> str:
    color_dict = asdict(color_cfg)
    items = ",\n    ".join(f"{key}={value!r}" for key, value in color_dict.items())
    return f"ColorConfig(\n    {items}\n)"


def _write_vspreview_script(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary,
    cfg: AppConfig,
    root: Path,
) -> Path:
    reference_plan = summary.reference_plan
    targets = [plan for plan in plans if plan is not reference_plan]
    script_dir = resolve_subdir(root, "vspreview", purpose="vspreview workspace")
    script_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    script_path = script_dir / f"vspreview_{timestamp}_{uuid.uuid4().hex[:8]}.py"
    while script_path.exists():
        logger.warning(
            "VSPreview script %s already exists; generating alternate filename to avoid overwriting",
            script_path.name,
        )
        script_path = script_dir / f"vspreview_{timestamp}_{uuid.uuid4().hex[:8]}.py"
    project_root = PROJECT_ROOT

    search_paths = [
        str(Path(path).expanduser())
        for path in getattr(cfg.runtime, "vapoursynth_python_paths", [])
        if path
    ]
    color_literal = _color_config_literal(cfg.color)

    preview_mode_value = _normalise_vspreview_mode(
        getattr(cfg.audio_alignment, "vspreview_mode", "baseline")
    )
    apply_seeded_offsets = preview_mode_value == "seeded"
    show_overlay = bool(getattr(cfg.audio_alignment, "show_suggested_in_preview", True))
    if summary.measured_offsets:
        measurement_lookup: Dict[str, Optional[float]] = {
            name: detail.offset_seconds for name, detail in summary.measured_offsets.items()
        }
    else:
        measurement_lookup = {
            measurement.file.name: measurement.offset_seconds
            for measurement in summary.measurements
        }

    manual_trims = {}
    if summary.manual_trim_starts:
        manual_trims = {
            _plan_label(plan): summary.manual_trim_starts.get(plan.path.name, 0)
            for plan in plans
        }
    else:
        manual_trims = {_plan_label(plan): int(plan.trim_start) for plan in plans if plan.trim_start > 0}

    reference_label = _plan_label(reference_plan)
    reference_trim_end = reference_plan.trim_end if reference_plan.trim_end is not None else None
    reference_info = textwrap.dedent(
        f"""\
        {{
        'label': {reference_label!r},
        'path': {str(reference_plan.path)!r},
        'trim_start': {int(reference_plan.trim_start)},
        'trim_end': {reference_trim_end!r},
        'fps_override': {tuple(reference_plan.fps_override) if reference_plan.fps_override else None!r},
        }}
        """
    ).strip()

    target_lines: list[str] = []
    offset_lines: list[str] = []
    suggestion_lines: list[str] = []
    if not targets:
        offset_lines.append("    # Add entries like 'Clip Label': 0 once targets are available.")
    for plan in targets:
        label = _plan_label(plan)
        trim_end_value = plan.trim_end if plan.trim_end is not None else None
        fps_override = tuple(plan.fps_override) if plan.fps_override else None
        suggested_frames_value = int(summary.suggested_frames.get(plan.path.name, 0))
        measurement_seconds = measurement_lookup.get(plan.path.name)
        suggested_seconds_value = 0.0
        if measurement_seconds is not None:
            suggested_seconds_value = float(measurement_seconds)
        manual_trim = manual_trims.get(label, int(plan.trim_start))
        manual_note = (
            f"baseline trim {manual_trim}f"
            if manual_trim
            else "no baseline trim"
        )
        target_lines.append(
            textwrap.dedent(
                f"""\
                {label!r}: {{
                    'label': {label!r},
                    'path': {str(plan.path)!r},
                    'trim_start': {int(plan.trim_start)},
                    'trim_end': {trim_end_value!r},
                    'fps_override': {fps_override!r},
                    'manual_trim': {manual_trim},
                    'manual_trim_description': {manual_note!r},
                }},"""
            ).rstrip()
        )
        applied_initial = suggested_frames_value if apply_seeded_offsets else 0
        offset_lines.append(
            f"    {label!r}: {applied_initial},  # Suggested delta {suggested_frames_value:+d}f"
        )
        suggestion_lines.append(
            f"    {label!r}: ({suggested_frames_value}, {suggested_seconds_value!r}),"
        )

    targets_literal = "\n".join(target_lines) if target_lines else ""
    offsets_literal = "\n".join(offset_lines)
    suggestions_literal = "\n".join(suggestion_lines)

    extra_paths = [
        str(project_root),
        str(project_root / "src"),
        str(root),
    ]
    extra_paths_literal = ", ".join(repr(path) for path in extra_paths)
    search_paths_literal = repr(search_paths)

    script = f"""# Auto-generated by Frame Compare to assist with VSPreview alignment.
import sys
from pathlib import Path

try:
    # Prefer UTF-8 on Windows consoles and avoid crashing on encoding errors.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WORKSPACE_ROOT = Path({str(root)!r})
PROJECT_ROOT = Path({str(project_root)!r})
EXTRA_PATHS = [{extra_paths_literal}]
for candidate in EXTRA_PATHS:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import vapoursynth as vs
from src import vs_core
from src.datatypes import ColorConfig

vs_core.configure(
    search_paths={search_paths_literal},
    source_preference={cfg.source.preferred!r},
)

COLOR_CFG = {color_literal}

REFERENCE = {reference_info}

TARGETS = {{
{targets_literal}
}}

OFFSET_MAP = {{
{offsets_literal}
}}

SUGGESTION_MAP = {{
{suggestions_literal}
}}

PREVIEW_MODE = {preview_mode_value!r}
SHOW_SUGGESTED_OVERLAY = {show_overlay!r}

core = vs.core


def safe_print(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("utf-8", "replace").decode("utf-8", "replace"))
        except Exception:
            print("[log message unavailable due to encoding]")


def _load_clip(info):
    clip = vs_core.init_clip(
        str(Path(info['path'])),
        trim_start=int(info.get('trim_start', 0)),
        trim_end=info.get('trim_end'),
        fps_map=tuple(info['fps_override']) if info.get('fps_override') else None,
    )
    processed = vs_core.process_clip_for_screenshot(
        clip,
        info['label'],
        COLOR_CFG,
        enable_overlay=False,
        enable_verification=False,
    ).clip
    return processed


def _apply_offset(reference_clip, target_clip, offset_frames):
    if offset_frames > 0:
        target_clip = target_clip[offset_frames:]
    elif offset_frames < 0:
        reference_clip = reference_clip[abs(offset_frames):]
    return reference_clip, target_clip


def _extract_fps_tuple(clip):
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    if isinstance(num, int) and isinstance(den, int) and den:
        return int(num), int(den)
    return None


def _harmonise_fps(reference_clip, target_clip, label):
    reference_fps = _extract_fps_tuple(reference_clip)
    target_fps = _extract_fps_tuple(target_clip)
    if not reference_fps or not target_fps:
        return reference_clip, target_clip
    if reference_fps == target_fps:
        return reference_clip, target_clip
    try:
        target_clip = target_clip.std.AssumeFPS(num=reference_fps[0], den=reference_fps[1])
        safe_print(
            "Adjusted FPS for target '%s' to match reference (%s/%s -> %s/%s)"
            % (
                label,
                target_fps[0],
                target_fps[1],
                reference_fps[0],
                reference_fps[1],
            )
        )
    except Exception as exc:
        safe_print("Warning: Failed to harmonise FPS for target '%s': %s" % (label, exc))
    return reference_clip, target_clip


def _format_overlay_text(label, suggested_frames, suggested_seconds, applied_frames):
    applied_label = "baseline" if applied_frames == 0 else "seeded"
    applied_value = "0" if applied_frames == 0 else f"{{applied_frames:+d}}"
    seconds_value = f"{{suggested_seconds:.3f}}"
    if seconds_value == "-0.000":
        seconds_value = "0.000"
    suggested_value = f"{{suggested_frames:+d}}"
    return (
        "{{label}}: {{suggested}}f (~{{seconds}}s) • "
        "Preview applied: {{applied}}f ({{status}}) • "
        "(+ trims target / - pads reference)"
    ).format(
        label=label,
        suggested=suggested_value,
        seconds=seconds_value,
        applied=applied_value,
        status=applied_label,
    )


def _maybe_apply_overlay(clip, label, suggested_frames, suggested_seconds, applied_frames):
    if not SHOW_SUGGESTED_OVERLAY:
        return clip
    try:
        message = _format_overlay_text(label, suggested_frames, suggested_seconds, applied_frames)
    except Exception:
        message = "Suggested offset unavailable"
    try:
        return clip.text.Text(message, alignment=7)
    except Exception as exc:
        safe_print("Warning: Failed to draw overlay text for preview: %s" % (exc,))
        return clip


safe_print("Reference clip: %s" % (REFERENCE['label'],))
safe_print("VSPreview mode: %s" % (PREVIEW_MODE,))
if not TARGETS:
    safe_print("No target clips defined; edit TARGETS and OFFSET_MAP to add entries.")

slot = 0
for label, info in TARGETS.items():
    reference_clip = _load_clip(REFERENCE)
    target_clip = _load_clip(info)
    reference_clip, target_clip = _harmonise_fps(reference_clip, target_clip, label)
    offset_frames = int(OFFSET_MAP.get(label, 0))
    suggested_entry = SUGGESTION_MAP.get(label, (0, 0.0))
    suggested_frames = int(suggested_entry[0])
    suggested_seconds = float(suggested_entry[1])
    ref_view, tgt_view = _apply_offset(reference_clip, target_clip, offset_frames)
    ref_view = _maybe_apply_overlay(
        ref_view,
        REFERENCE['label'],
        suggested_frames,
        suggested_seconds,
        offset_frames,
    )
    tgt_view = _maybe_apply_overlay(
        tgt_view,
        label,
        suggested_frames,
        suggested_seconds,
        offset_frames,
    )
    ref_view.set_output(slot)
    tgt_view.set_output(slot + 1)
    applied_label = "baseline" if offset_frames == 0 else "seeded"
    safe_print(
        "Target '%s': baseline trim=%sf (%s), suggested delta=%+df (~%+.3fs), preview applied=%+df (%s mode)"
        % (
            label,
            info.get('manual_trim', 0),
            info.get('manual_trim_description', 'n/a'),
            suggested_frames,
            suggested_seconds,
            offset_frames,
            applied_label,
        )
    )
    slot += 2

safe_print("VSPreview outputs: reference on even slots, target on odd slots (0<->1, 2<->3, ...).")
safe_print("Edit OFFSET_MAP values and press Ctrl+R in VSPreview to reload the script.")
"""
    script_path.write_text(textwrap.dedent(script), encoding="utf-8")
    return script_path


def _prompt_vspreview_offsets(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary,
    reporter: CliOutputManagerProtocol,
    display: _AudioAlignmentDisplayData | None,
) -> dict[str, int] | None:
    reference_plan = summary.reference_plan
    targets = [plan for plan in plans if plan is not reference_plan]
    if not targets:
        return {}

    baseline_map: Dict[str, int] = {
        plan.path.name: summary.manual_trim_starts.get(plan.path.name, int(plan.trim_start))
        for plan in plans
    }

    reference_label = _plan_label(reference_plan)
    reporter.line(
        "Enter VSPreview frame offsets relative to the reported baselines. Positive trims the target; negative advances the reference."
    )
    offsets: Dict[str, int] = {}
    for plan in targets:
        label = _plan_label(plan)
        baseline_value = baseline_map.get(plan.path.name, int(plan.trim_start))
        suggested = summary.suggested_frames.get(plan.path.name)
        prompt_parts = [
            f"VSPreview offset for {label} relative to {reference_label}",
            f"baseline {baseline_value}f",
        ]
        if suggested is not None:
            prompt_parts.append(f"suggested {suggested:+d}f")
        prompt_message = " (".join([prompt_parts[0], ", ".join(prompt_parts[1:])]) + ")"
        try:
            delta = int(
                click.prompt(
                    prompt_message,
                    type=int,
                    default=0,
                    show_default=True,
                )
            )
        except click.exceptions.Abort:
            reporter.warn("VSPreview offset entry aborted; keeping existing trims.")
            return None
        offsets[plan.path.name] = delta
        if display is not None:
            display.manual_trim_lines.append(
                f"Baseline for {label}: {baseline_value}f"
            )
    return offsets


def _apply_vspreview_manual_offsets(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary,
    deltas: Mapping[str, int],
    reporter: CliOutputManagerProtocol,
    json_tail: JsonTail,
    display: _AudioAlignmentDisplayData | None,
) -> None:
    reference_plan = summary.reference_plan
    reference_name = reference_plan.path.name
    targets = [plan for plan in plans if plan is not reference_plan]

    baseline_map: Dict[str, int] = {
        plan.path.name: summary.manual_trim_starts.get(plan.path.name, int(plan.trim_start))
        for plan in plans
    }
    if reference_name not in baseline_map:
        baseline_map[reference_name] = int(reference_plan.trim_start)

    manual_trim_starts: Dict[str, int] = {}
    delta_map: Dict[str, int] = {}
    manual_lines: List[str] = []

    desired_map: Dict[str, int] = {}
    target_adjustments: List[Tuple[_ClipPlan, int, int]] = []

    for plan in targets:
        key = plan.path.name
        baseline_value = baseline_map.get(key, int(plan.trim_start))
        delta_value = int(deltas.get(key, 0))
        desired_value = baseline_value + delta_value
        desired_map[key] = desired_value
        target_adjustments.append((plan, baseline_value, delta_value))

    reference_baseline = baseline_map.get(reference_name, int(reference_plan.trim_start))
    reference_delta_input = int(deltas.get(reference_name, 0))
    desired_map[reference_name] = reference_baseline + reference_delta_input

    baseline_min = min(baseline_map.values()) if baseline_map else 0
    desired_min = min(desired_map.values()) if desired_map else 0
    baseline_floor = baseline_min if baseline_min < 0 else 0
    desired_floor = desired_min if desired_min < 0 else 0
    shift = 0
    if desired_floor < baseline_floor:
        shift = baseline_floor - desired_floor

    for plan, baseline_value, delta_value in target_adjustments:
        key = plan.path.name
        desired_value = desired_map[key]
        updated = desired_value + shift
        updated_int = int(updated)
        safe_updated = max(0, updated_int)
        plan.trim_start = safe_updated
        plan.has_trim_start_override = (
            plan.has_trim_start_override or safe_updated != 0
        )
        manual_trim_starts[key] = updated_int
        applied_delta = updated_int - baseline_value
        delta_map[key] = applied_delta
        line = (
            f"VSPreview manual offset applied: {_plan_label(plan)} baseline {baseline_value}f "
            f"{delta_value:+d}f → {int(updated)}f"
        )
        manual_lines.append(line)
        reporter.line(line)

    adjusted_reference = desired_map[reference_name] + shift
    adjusted_reference_int = int(adjusted_reference)
    safe_adjusted_reference = max(0, adjusted_reference_int)
    reference_plan.trim_start = safe_adjusted_reference
    reference_plan.has_trim_start_override = (
        reference_plan.has_trim_start_override
        or safe_adjusted_reference != int(reference_baseline)
    )
    manual_trim_starts[reference_name] = adjusted_reference_int
    reference_delta = adjusted_reference_int - reference_baseline
    delta_map[reference_name] = reference_delta
    if reference_delta != 0:
        ref_line = (
            f"VSPreview reference adjustment: {_plan_label(reference_plan)} baseline {reference_baseline}f → {int(adjusted_reference)}f"
        )
        manual_lines.append(ref_line)
        reporter.line(ref_line)

    if display is not None:
        if display.manual_trim_lines is None:
            display.manual_trim_lines = []
        display.manual_trim_lines.extend(manual_lines)
        display.offset_lines = ["Audio offsets: VSPreview manual offsets applied"]
        display.offset_lines.extend(display.manual_trim_lines)

    fps_lookup: Dict[str, Tuple[int, int] | None] = {}
    for plan in plans:
        fps_lookup[plan.path.name] = (
            plan.effective_fps or plan.source_fps or plan.fps_override
        )

    measurement_order = [plan.path.name for plan in plans]
    plan_lookup: Dict[str, _ClipPlan] = {plan.path.name: plan for plan in plans}

    measurements: List["AlignmentMeasurement"] = []
    existing_override_map: Dict[str, Dict[str, object]] = {}
    notes_map: Dict[str, str] = {}
    for plan in plans:
        key = plan.path.name
        frames_value = int(manual_trim_starts.get(key, int(plan.trim_start)))
        fps_tuple = fps_lookup.get(key)
        fps_float = _fps_to_float(fps_tuple) if fps_tuple else 0.0
        seconds_value = float(frames_value) / fps_float if fps_float else 0.0
        measurements.append(
            audio_alignment.AlignmentMeasurement(
                file=plan.path,
                offset_seconds=seconds_value,
                frames=frames_value,
                correlation=1.0,
                reference_fps=fps_float or None,
                target_fps=fps_float or None,
            )
        )
        existing_override_map[key] = {"frames": frames_value, "status": "manual"}
        notes_map[key] = "VSPreview"

    applied_frames, statuses = audio_alignment.update_offsets_file(
        summary.offsets_path,
        reference_plan.path.name,
        tuple(measurements),
        existing_override_map,
        notes_map,
    )

    summary.applied_frames = dict(applied_frames)
    summary.statuses = dict(statuses)
    summary.final_adjustments = dict(manual_trim_starts)
    summary.manual_trim_starts = dict(manual_trim_starts)
    summary.suggestion_mode = False
    summary.vspreview_manual_offsets = dict(manual_trim_starts)
    summary.vspreview_manual_deltas = dict(delta_map)
    summary.measurements = tuple(measurements)

    existing_details = summary.measured_offsets if isinstance(summary.measured_offsets, dict) else {}
    detail_map: Dict[str, _AudioMeasurementDetail] = {}
    for measurement in measurements:
        clip_name = measurement.file.name
        prev_detail = existing_details.get(clip_name) if isinstance(existing_details, dict) else None
        plan = plan_lookup.get(clip_name)
        label = (
            prev_detail.label
            if prev_detail
            else (_plan_label(plan) if plan is not None else clip_name)
        )
        descriptor = prev_detail.stream if prev_detail else ""
        seconds_value = float(measurement.offset_seconds) if measurement.offset_seconds is not None else None
        frames_value = int(measurement.frames) if measurement.frames is not None else None
        correlation_value = (
            float(measurement.correlation) if measurement.correlation is not None else None
        )
        status_text = summary.statuses.get(clip_name, "manual")
        note_text = notes_map.get(clip_name)
        detail_map[clip_name] = _AudioMeasurementDetail(
            label=label,
            stream=descriptor,
            offset_seconds=seconds_value,
            frames=frames_value,
            correlation=correlation_value,
            status=status_text,
            applied=True,
            note=note_text,
        )
    summary.measured_offsets = detail_map

    audio_block = json_tail.setdefault("audio_alignment", {})
    audio_block["suggestion_mode"] = False
    audio_block["manual_trim_starts"] = dict(manual_trim_starts)
    audio_block["vspreview_manual_offsets"] = dict(manual_trim_starts)
    audio_block["vspreview_manual_deltas"] = dict(delta_map)
    audio_block["vspreview_reference_trim"] = int(
        manual_trim_starts.get(reference_name, int(reference_plan.trim_start))
    )

    if display is not None:
        offsets_sec: Dict[str, float] = {}
        offsets_frames: Dict[str, int] = {}
        offset_lines: List[str] = []
        for clip_name in measurement_order:
            detail = detail_map.get(clip_name)
            if detail is None:
                continue
            if clip_name == reference_name and len(detail_map) > 1:
                continue
            stream_text = detail.stream or "?"
            seconds_text = (
                f"{detail.offset_seconds:+.3f}s"
                if detail.offset_seconds is not None
                else "n/a"
            )
            frames_text = f"{detail.frames:+d}f" if detail.frames is not None else "n/a"
            corr_text = (
                f"{detail.correlation:.2f}"
                if detail.correlation is not None and not math.isnan(detail.correlation)
                else "n/a"
            )
            status_text = detail.status or "manual"
            offset_lines.append(
                f"Audio offsets: {detail.label}: [{stream_text}] {seconds_text} ({frames_text}) "
                f"corr={corr_text} status={status_text}"
            )
            if detail.note:
                offset_lines.append(f"  note: {detail.note}")
            if detail.offset_seconds is not None:
                offsets_sec[detail.label] = float(detail.offset_seconds)
            if detail.frames is not None:
                offsets_frames[detail.label] = int(detail.frames)
        if not offset_lines:
            offset_lines.append("Audio offsets: VSPreview manual offsets applied")
        else:
            offset_lines.insert(0, "Audio offsets: VSPreview manual offsets applied")
        if display.manual_trim_lines:
            offset_lines.extend(display.manual_trim_lines)
        display.offset_lines = offset_lines
        display.json_offsets_sec = offsets_sec
        display.json_offsets_frames = offsets_frames
        display.measurements = {
            detail.label: detail for detail in detail_map.values()
        }
        display.correlations = {
            detail.label: detail.correlation
            for detail in detail_map.values()
            if detail.correlation is not None
        }

    reporter.line("VSPreview offsets saved to offsets file with manual status.")


def _resolve_vspreview_command(script_path: Path) -> tuple[list[str] | None, str | None]:
    """Return the VSPreview launch command or a reason string when unavailable."""

    executable = shutil.which("vspreview")
    if executable:
        return [executable, str(script_path)], None
    module_spec = importlib.util.find_spec("vspreview")
    if module_spec is None:
        return None, "vspreview-missing"
    backend_spec = importlib.util.find_spec("PySide6") or importlib.util.find_spec("PyQt5")
    if backend_spec is None:
        return None, "vspreview-missing"
    return [sys.executable, "-m", "vspreview", str(script_path)], None


def _activate_vspreview_missing_panel(
    reporter: CliOutputManagerProtocol,
    manual_command: str,
    *,
    reason: str,
) -> None:
    """Update layout state and render the VSPreview missing-dependency panel."""

    vspreview_block = _coerce_str_mapping(reporter.values.get("vspreview"))
    missing_block_obj = vspreview_block.get("missing")
    missing_block: dict[str, object]
    if isinstance(missing_block_obj, MappingABC):
        missing_block = _coerce_str_mapping(missing_block_obj)
    else:
        missing_block = {
            "windows_install": _VSPREVIEW_WINDOWS_INSTALL,
            "posix_install": _VSPREVIEW_POSIX_INSTALL,
        }
    if "windows_install" not in missing_block:
        missing_block["windows_install"] = _VSPREVIEW_WINDOWS_INSTALL
    if "posix_install" not in missing_block:
        missing_block["posix_install"] = _VSPREVIEW_POSIX_INSTALL
    missing_block["command"] = manual_command
    missing_block["reason"] = reason
    missing_block["active"] = True
    vspreview_block["missing"] = missing_block
    vspreview_block["script_command"] = manual_command
    reporter.update_values({"vspreview": vspreview_block})
    reporter.render_sections(["vspreview_missing"])


def _report_vspreview_missing(
    reporter: CliOutputManagerProtocol,
    json_tail: JsonTail,
    manual_command: str,
    *,
    reason: str,
) -> None:
    """Record missing VSPreview dependencies in layout output and JSON tail."""

    _activate_vspreview_missing_panel(reporter, manual_command, reason=reason)
    width_lines = [
        "VSPreview dependency missing. Install with:",
        f"  Windows: {_VSPREVIEW_WINDOWS_INSTALL}",
        f"  Linux/macOS: {_VSPREVIEW_POSIX_INSTALL}",
        f"Then run: {manual_command}",
    ]
    for line in width_lines:
        reporter.console.print(Text(line, no_wrap=True))
    reporter.warn(
        "VSPreview dependencies missing. Install with "
        f"'{_VSPREVIEW_WINDOWS_INSTALL}' (Windows) or "
        f"'{_VSPREVIEW_POSIX_INSTALL}' (Linux/macOS), then run "
        f"'{manual_command}'."
    )
    json_tail["vspreview_offer"] = {"vspreview_offered": False, "reason": reason}


def _launch_vspreview(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary | None,
    display: _AudioAlignmentDisplayData | None,
    cfg: AppConfig,
    root: Path,
    reporter: CliOutputManagerProtocol,
    json_tail: JsonTail,
) -> None:
    audio_block = _ensure_audio_alignment_block(json_tail)
    if "vspreview_script" not in audio_block:
        audio_block["vspreview_script"] = None
    if "vspreview_invoked" not in audio_block:
        audio_block["vspreview_invoked"] = False
    if "vspreview_exit_code" not in audio_block:
        audio_block["vspreview_exit_code"] = None

    if summary is None:
        reporter.warn("VSPreview skipped: no alignment summary available.")
        return

    if len(plans) < 2:
        reporter.warn("VSPreview skipped: need at least two clips to compare.")
        return

    script_path = _write_vspreview_script(plans, summary, cfg, root)
    audio_block["vspreview_script"] = str(script_path)
    reporter.console.print(
        f"[cyan]VSPreview script ready:[/cyan] {script_path}\n"
        "Edit the OFFSET_MAP values inside the script and reload VSPreview (Ctrl+R) after changes."
    )

    manual_command = _format_vspreview_manual_command(script_path)
    vspreview_block = _coerce_str_mapping(reporter.values.get("vspreview"))
    vspreview_block["script_path"] = str(script_path)
    vspreview_block["script_command"] = manual_command
    missing_block_obj = vspreview_block.get("missing")
    missing_block: dict[str, object]
    if isinstance(missing_block_obj, MappingABC):
        missing_block = _coerce_str_mapping(missing_block_obj)
    else:
        missing_block = {
            "windows_install": _VSPREVIEW_WINDOWS_INSTALL,
            "posix_install": _VSPREVIEW_POSIX_INSTALL,
        }
    missing_block["active"] = False
    if "windows_install" not in missing_block:
        missing_block["windows_install"] = _VSPREVIEW_WINDOWS_INSTALL
    if "posix_install" not in missing_block:
        missing_block["posix_install"] = _VSPREVIEW_POSIX_INSTALL
    missing_block["command"] = manual_command
    if "reason" not in missing_block:
        missing_block["reason"] = ""
    vspreview_block["missing"] = missing_block
    reporter.update_values({"vspreview": vspreview_block})

    if not sys.stdin.isatty():
        reporter.warn(
            "VSPreview launch skipped (non-interactive session). Open the script manually if needed."
        )
        return

    env = dict(os.environ)
    search_paths = getattr(cfg.runtime, "vapoursynth_python_paths", [])
    if search_paths:
        env["VAPOURSYNTH_PYTHONPATH"] = os.pathsep.join(str(Path(path).expanduser()) for path in search_paths if path)

    command, missing_reason = _resolve_vspreview_command(script_path)
    if command is None:
        _report_vspreview_missing(
            reporter,
            json_tail,
            manual_command,
            reason=missing_reason or "vspreview-missing",
        )
        return

    verbose_requested = bool(reporter.flags.get("verbose")) or bool(
        reporter.flags.get("debug")
    )

    try:
        if verbose_requested:
            result = subprocess.run(command, env=env, check=False)
        else:
            result = subprocess.run(
                command,
                env=env,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
    except FileNotFoundError:
        _report_vspreview_missing(
            reporter,
            json_tail,
            manual_command,
            reason="vspreview-missing",
        )
        return
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        logger.warning(
            "VSPreview launch failed: %s",
            exc,
            exc_info=True,
        )
        reporter.warn(f"VSPreview launch failed: {exc}")
        return
    audio_block["vspreview_invoked"] = True
    audio_block["vspreview_exit_code"] = int(result.returncode)
    captured_stdout = getattr(result, "stdout", None)
    captured_stderr = getattr(result, "stderr", None)
    if not verbose_requested:
        for stream_value, label in ((captured_stdout, "stdout"), (captured_stderr, "stderr")):
            if isinstance(stream_value, str) and stream_value.strip():
                logger.debug("VSPreview %s (suppressed): %s", label, stream_value.strip())
    if result.returncode != 0:
        reporter.warn(
            f"VSPreview exited with code {result.returncode}."
            + (" Re-run with --verbose to inspect VSPreview output." if not verbose_requested else "")
        )
        return

    offsets = _prompt_vspreview_offsets(plans, summary, reporter, display)
    if offsets is None:
        return
    _apply_vspreview_manual_offsets(plans, summary, offsets, reporter, json_tail, display)

def _validate_tonemap_overrides(overrides: MutableMapping[str, Any]) -> None:
    """Validate CLI-provided tonemap overrides and raise ClickException on invalid values."""

    if not overrides:
        return

    def _bad(message: str) -> NoReturn:
        raise click.ClickException(message)

    parsed_floats: dict[str, float] = {}

    def _get_float(key: str, error_message: str) -> float:
        if key in parsed_floats:
            return parsed_floats[key]
        try:
            value = float(overrides[key])
        except (TypeError, ValueError):
            _bad(error_message)
        if not math.isfinite(value):
            _bad(error_message)
        parsed_floats[key] = value
        return value

    if "knee_offset" in overrides:
        knee_value = _get_float(
            "knee_offset",
            "--tm-knee must be a finite number in [0.0, 1.0]",
        )
        if knee_value < 0.0 or knee_value > 1.0:
            _bad("--tm-knee must be between 0.0 and 1.0")
    if "dst_min_nits" in overrides:
        dst_value = _get_float(
            "dst_min_nits",
            "--tm-dst-min must be a finite, non-negative number",
        )
        if dst_value < 0.0:
            _bad("--tm-dst-min must be >= 0.0")
    if "target_nits" in overrides:
        target_value = _get_float(
            "target_nits",
            "--tm-target must be a finite, positive number",
        )
        if target_value <= 0.0:
            _bad("--tm-target must be > 0")
    if "post_gamma" in overrides:
        gamma_value = _get_float(
            "post_gamma",
            "--tm-gamma must be a finite number between 0.9 and 1.1",
        )
        if gamma_value < 0.9 or gamma_value > 1.1:
            _bad("--tm-gamma must be between 0.9 and 1.1")
    if "dpd_preset" in overrides:
        dpd_value = str(overrides["dpd_preset"]).strip().lower()
        if dpd_value not in {"off", "fast", "balanced", "high_quality"}:
            _bad("--tm-dpd-preset must be one of: off, fast, balanced, high_quality")
    if "dpd_black_cutoff" in overrides:
        cutoff = _get_float(
            "dpd_black_cutoff",
            "--tm-dpd-black-cutoff must be a finite number in [0.0, 0.05]",
        )
        if cutoff < 0.0 or cutoff > 0.05:
            _bad("--tm-dpd-black-cutoff must be between 0.0 and 0.05")
    if "smoothing_period" in overrides:
        smoothing = _get_float(
            "smoothing_period",
            "--tm-smoothing must be a finite, non-negative number",
        )
        if smoothing < 0.0:
            _bad("--tm-smoothing must be >= 0")
    if "scene_threshold_low" in overrides:
        low_value = _get_float(
            "scene_threshold_low",
            "--tm-scene-low must be a finite, non-negative number",
        )
        if low_value < 0.0:
            _bad("--tm-scene-low must be >= 0")
    if "scene_threshold_high" in overrides:
        high_value = _get_float(
            "scene_threshold_high",
            "--tm-scene-high must be a finite, non-negative number",
        )
        if high_value < 0.0:
            _bad("--tm-scene-high must be >= 0")
    if "scene_threshold_low" in overrides and "scene_threshold_high" in overrides:
        high_value = parsed_floats["scene_threshold_high"]
        low_value = parsed_floats["scene_threshold_low"]
        if high_value < low_value:
            _bad("--tm-scene-high must be >= --tm-scene-low")
    if "percentile" in overrides:
        percentile = _get_float(
            "percentile",
            "--tm-percentile must be a finite number between 0 and 100",
        )
        if percentile < 0.0 or percentile > 100.0:
            _bad("--tm-percentile must be between 0 and 100")
    if "contrast_recovery" in overrides:
        contrast = _get_float(
            "contrast_recovery",
            "--tm-contrast must be a finite, non-negative number",
        )
        if contrast < 0.0:
            _bad("--tm-contrast must be >= 0")
    if "metadata" in overrides:
        meta_value = overrides["metadata"]
        if isinstance(meta_value, str):
            lowered = meta_value.strip().lower()
            if lowered in {"auto", ""}:
                overrides["metadata"] = "auto"
            elif lowered in {"none", "hdr10", "hdr10+", "hdr10plus", "luminance"}:
                overrides["metadata"] = lowered
            else:
                try:
                    meta_int = int(lowered)
                except ValueError:
                    _bad("--tm-metadata must be auto, none, hdr10, hdr10+, luminance, or 0-4")
                else:
                    if meta_int < 0 or meta_int > 4:
                        _bad("--tm-metadata integer must be between 0 and 4")
                    overrides["metadata"] = meta_int
        else:
            try:
                meta_int = int(meta_value)
            except (TypeError, ValueError):
                _bad("--tm-metadata must be auto, none, hdr10, hdr10+, luminance, or 0-4")
            else:
                if meta_int < 0 or meta_int > 4:
                    _bad("--tm-metadata integer must be between 0 and 4")
    if "use_dovi" in overrides:
        if overrides["use_dovi"] not in {None, True, False}:
            _bad("--tm-use-dovi/--tm-no-dovi must be specified without a value")
    for boolean_key in ("visualize_lut", "show_clipping"):
        if boolean_key in overrides and not isinstance(overrides[boolean_key], bool):
            _bad(f"--tm-{boolean_key.replace('_', '-')} must be used without a value")
