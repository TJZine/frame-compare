"""Shared runner extracted from frame_compare.run_cli."""

from __future__ import annotations

import copy
import importlib
import logging
import math
import threading
import time
import traceback
from collections import Counter
from collections.abc import Mapping as MappingABC
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, cast

from rich.console import Console
from rich.markup import escape

import src.frame_compare.alignment_runner as alignment_runner
import src.frame_compare.cache as cache_utils
import src.frame_compare.core as core
import src.frame_compare.media as media_utils
import src.frame_compare.metadata as metadata_utils
import src.frame_compare.planner as planner_utils
import src.frame_compare.preflight as preflight_utils
import src.frame_compare.report as html_report
import src.frame_compare.runtime_utils as runtime_utils
import src.frame_compare.selection as selection_utils
import src.frame_compare.tmdb_workflow as tmdb_workflow
import src.frame_compare.vspreview as vspreview_utils
from src.datatypes import AppConfig
from src.frame_compare import vs as vs_core
from src.frame_compare.alignment_helpers import derive_frame_hint
from src.frame_compare.analysis import (
    CacheLoadResult,
    SelectionDetail,
    export_selection_metadata,
    probe_cached_metrics,
    select_frames,
    selection_details_to_json,
    selection_hash_for_config,
    write_selection_cache_file,
)
from src.frame_compare.slowpics import (
    SlowpicsAPIError,
    build_shortcut_filename,
    upload_comparison,
)
from src.frame_compare.vs import ClipInitError, ClipProcessError
from src.screenshot import ScreenshotError, generate_screenshots
from src.tmdb import TMDBResolution

from .cli_runtime import (
    CLIAppError,
    CliOutputManager,
    CliOutputManagerProtocol,
    ClipPlan,
    ClipRecord,
    JsonTail,
    NullCliOutputManager,
    ReportJSON,
    SlowpicsTitleInputs,
    TrimClipEntry,
    TrimSummary,
    coerce_str_mapping,
    ensure_slowpics_block,
)
from .layout_utils import (
    color_text as _color_text,
)
from .layout_utils import (
    format_kv as _format_kv,
)
from .layout_utils import (
    normalise_vspreview_mode as _normalise_vspreview_mode,
)
from .layout_utils import (
    plan_label as _plan_label,
)
from .layout_utils import (
    sanitize_console_text as _sanitize_console_text,
)

ReporterFactory = Callable[['RunRequest', Path, Console], CliOutputManagerProtocol]


@dataclass
class RunResult:
    files: List[Path]
    frames: List[int]
    out_dir: Path
    out_dir_created: bool
    out_dir_created_path: Optional[Path]
    root: Path
    config: AppConfig
    image_paths: List[str]
    slowpics_url: Optional[str] = None
    json_tail: JsonTail | None = None
    report_path: Optional[Path] = None


@dataclass
class RunRequest:
    config_path: str | None
    input_dir: str | None = None
    root_override: str | None = None
    audio_track_overrides: Iterable[str] | None = None
    quiet: bool = False
    verbose: bool = False
    no_color: bool = False
    report_enable_override: Optional[bool] = None
    skip_wizard: bool = False
    debug_color: bool = False
    tonemap_overrides: Optional[Dict[str, Any]] = None
    impl_module: ModuleType | None = None
    console: Console | None = None
    reporter: CliOutputManagerProtocol | None = None
    reporter_factory: ReporterFactory | None = None


logger = logging.getLogger('frame_compare')


def _apply_cli_tonemap_overrides(color_cfg: Any, overrides: Mapping[str, Any]) -> None:
    if color_cfg is None or not overrides:
        return
    provided_raw = getattr(color_cfg, "_provided_keys", None)
    provided: set[str]
    if isinstance(provided_raw, set):
        provided = set(cast(set[Any], provided_raw))
    else:
        provided = set()
    updated: set[str] = set()

    def _assign(field: str, converter: Callable[[Any], Any]) -> None:
        if field in overrides:
            setattr(color_cfg, field, converter(overrides[field]))
            updated.add(field)

    _assign("preset", lambda value: str(value))
    _assign("tone_curve", lambda value: str(value))
    _assign("target_nits", lambda value: float(value))
    _assign("dst_min_nits", lambda value: float(value))
    _assign("knee_offset", lambda value: float(value))
    _assign("dpd_preset", lambda value: str(value))
    _assign("dpd_black_cutoff", lambda value: float(value))
    _assign("post_gamma", lambda value: float(value))
    _assign("post_gamma_enable", lambda value: bool(value))
    _assign("smoothing_period", lambda value: float(value))
    _assign("scene_threshold_low", lambda value: float(value))
    _assign("scene_threshold_high", lambda value: float(value))
    _assign("percentile", lambda value: float(value))
    _assign("contrast_recovery", lambda value: float(value))
    if "metadata" in overrides:
        color_cfg.metadata = overrides["metadata"]
        updated.add("metadata")
    if "use_dovi" in overrides:
        color_cfg.use_dovi = overrides["use_dovi"]
        updated.add("use_dovi")
    _assign("visualize_lut", lambda value: bool(value))
    _assign("show_clipping", lambda value: bool(value))

    if updated:
        provided.update(updated)
        try:
            setattr(color_cfg, "_provided_keys", provided)
        except Exception:
            pass


def run(request: RunRequest) -> RunResult:
    """
    Orchestrate the CLI workflow.

    Parameters:
        config_path (str | None): Optional explicit config path (CLI or env).
        input_dir (str | None): Optional override for [paths].input_dir inside the workspace root.
        root_override (str | None): Optional workspace root override supplied via --root.
        audio_track_overrides (Iterable[str] | None): Optional sequence of "filename=track" pairs to override audio track selection.
        quiet (bool): Suppress nonessential output when True.
        verbose (bool): Enable additional diagnostic output when True.
        no_color (bool): Disable colored output when True.
        report_enable_override (Optional[bool]): Optional override for HTML report generation toggle.
        tonemap_overrides (Optional[Dict[str, Any]]): Optional overrides for tone-mapping parameters supplied via CLI.

    Returns:
        RunResult: Aggregated result including processed files, selected frames, output directory, resolved root directory, configuration used, generated image paths, optional slow.pics URL, and a JSON-tail dictionary with detailed metadata and diagnostics.

    Raises:
        CLIAppError: For configuration loading failures, missing/invalid input directory, clip initialization failures, frame selection or screenshot generation errors, slow.pics upload failures, or other user-facing errors encountered during the run.
    """
    config_path = request.config_path
    input_dir = request.input_dir
    root_override = request.root_override
    audio_track_overrides = request.audio_track_overrides
    quiet = request.quiet
    verbose = request.verbose
    no_color = request.no_color
    report_enable_override = request.report_enable_override
    skip_wizard = request.skip_wizard
    debug_color = request.debug_color
    tonemap_overrides = request.tonemap_overrides
    impl = request.impl_module or importlib.import_module("frame_compare")
    module_file = Path(getattr(impl, '__file__', Path(__file__)))

    preflight = preflight_utils.prepare_preflight(
        cli_root=root_override,
        config_override=config_path,
        input_override=input_dir,
        ensure_config=True,
        create_dirs=True,
        create_media_dir=input_dir is None,
        allow_auto_wizard=True,
        skip_auto_wizard=skip_wizard,
    )
    cfg = preflight.config
    if tonemap_overrides:
        core.validate_tonemap_overrides(tonemap_overrides)
        _apply_cli_tonemap_overrides(getattr(cfg, "color", None), tonemap_overrides)
    if debug_color:
        try:
            setattr(cfg.color, "debug_color", True)
        except AttributeError:
            pass
    report_enabled = (
        bool(report_enable_override)
        if report_enable_override is not None
        else bool(getattr(cfg.report, "enable", False))
    )
    workspace_root = preflight.workspace_root
    root = preflight.media_root
    config_location = preflight.config_path

    if not root.exists():
        raise CLIAppError(
            f"Input directory not found: {root}",
            rich_message=f"[red]Input directory not found:[/red] {root}",
        )

    out_dir = preflight_utils.resolve_subdir(
        root,
        cfg.screenshots.directory_name,
        purpose="screenshots.directory_name",
    )
    out_dir_preexisting = out_dir.exists()
    created_out_dir = False
    created_out_dir_path: Optional[Path] = None
    if not out_dir_preexisting:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CLIAppError(
                f"Unable to create screenshots directory '{out_dir}': {exc}",
                rich_message=(
                    "[red]Unable to create screenshots directory.[/red] "
                    f"Adjust [screenshots].directory_name or choose a writable --root. ({exc})"
                ),
            ) from exc
        created_out_dir = True
        try:
            created_out_dir_path = out_dir.resolve()
        except OSError:
            created_out_dir_path = out_dir
    analysis_cache_path = preflight_utils.resolve_subdir(
        root,
        cfg.analysis.frame_data_filename,
        purpose="analysis.frame_data_filename",
    )
    offsets_path = preflight_utils.resolve_subdir(
        root,
        cfg.audio_alignment.offsets_filename,
        purpose="audio_alignment.offsets_filename",
    )
    preflight_utils.abort_if_site_packages(
        {
            "config": config_location,
            "workspace_root": workspace_root,
            "root": root,
            "screenshots": out_dir,
            "analysis_cache": analysis_cache_path,
            "audio_offsets": offsets_path,
        }
    )

    vspreview_mode_value = _normalise_vspreview_mode(
        getattr(cfg.audio_alignment, "vspreview_mode", "baseline")
    )

    layout_path = module_file.with_name("cli_layout.v1.json")
    console_cls = getattr(impl, 'Console', Console)
    reporter_console: Console | None = request.console
    reporter: CliOutputManagerProtocol | None = request.reporter

    if reporter is None:
        if reporter_console is None:
            reporter_console = console_cls(no_color=no_color, highlight=False)
        assert reporter_console is not None
        if request.reporter_factory is not None:
            reporter = request.reporter_factory(request, layout_path, reporter_console)
        else:
            reporter_cls = getattr(impl, 'CliOutputManager', CliOutputManager)
            null_cls = getattr(impl, 'NullCliOutputManager', NullCliOutputManager)
            if quiet:
                reporter = null_cls(
                    quiet=True,
                    verbose=verbose,
                    no_color=no_color,
                    layout_path=layout_path,
                    console=reporter_console,
                )
            else:
                reporter = reporter_cls(
                    quiet=quiet,
                    verbose=verbose,
                    no_color=no_color,
                    layout_path=layout_path,
                    console=reporter_console,
                )
    assert reporter is not None  # Narrow for type checkers
    emit_json_tail_flag = True
    progress_style = "fill"

    if hasattr(cfg, "cli"):
        cli_cfg = cfg.cli
        emit_json_tail_flag = bool(getattr(cli_cfg, "emit_json_tail", True))
        if hasattr(cli_cfg, "progress"):
            style_value = getattr(cli_cfg.progress, "style", "fill")
            progress_style = str(style_value).strip().lower()
            if progress_style not in {"fill", "dot"}:
                logger.warning(
                    "Invalid progress style '%s', falling back to 'fill'", style_value
                )
                progress_style = "fill"
    reporter.set_flag("progress_style", progress_style)
    reporter.set_flag("emit_json_tail", emit_json_tail_flag)
    collected_warnings: List[str] = []
    if bool(getattr(cfg.slowpics, "auto_upload", False)):
        auto_upload_warning = (
            "slow.pics auto-upload is enabled; confirm you trust the destination or disable "
            "[slowpics].auto_upload to keep screenshots local."
        )
        reporter.warn(auto_upload_warning)
        logger.warning(auto_upload_warning)
        collected_warnings.append(auto_upload_warning)
    for note in preflight.warnings:
        reporter.warn(note)
        collected_warnings.append(note)
    json_tail: JsonTail = {
        "clips": [],
        "trims": {"per_clip": {}},
        "window": {},
        "alignment": {"manual_start_s": 0.0, "manual_end_s": "unchanged"},
        "audio_alignment": {
            "enabled": bool(cfg.audio_alignment.enable),
            "reference_stream": None,
            "target_stream": {},
            "offsets_sec": {},
            "offsets_frames": {},
            "preview_paths": [],
            "confirmed": None,
            "offsets_filename": str(offsets_path),
            "manual_trim_summary": [],
            "suggestion_mode": False,
            "suggested_frames": {},
            "manual_trim_starts": {},
            "use_vspreview": bool(cfg.audio_alignment.use_vspreview),
            "vspreview_script": None,
            "vspreview_invoked": False,
            "vspreview_exit_code": None,
            "vspreview_manual_offsets": {},
            "vspreview_manual_deltas": {},
            "vspreview_reference_trim": None,
        },
        "analysis": {"output_frame_count": 0, "scanned": 0},
        "render": {},
        "tonemap": {},
        "overlay": {},
        "verify": {
            "count": 0,
            "threshold": float(cfg.color.verify_luma_threshold),
            "delta": {
                "max": None,
                "average": None,
                "frame": None,
                "file": None,
                "auto_selected": None,
            },
            "entries": [],
        },
        "cache": {},
        "workspace": {
            "root": str(workspace_root),
            "media_root": str(root),
            "config_path": str(config_location),
            "legacy_config": bool(preflight.legacy_config),
        },
        "slowpics": {
            "enabled": bool(cfg.slowpics.auto_upload),
            "title": {
                "inputs": {
                    "resolved_base": None,
                    "collection_name": None,
                    "collection_suffix": getattr(cfg.slowpics, "collection_suffix", ""),
                },
                "final": None,
            },
            "url": None,
            "shortcut_path": None,
            "shortcut_written": False,
            "shortcut_error": None,
            "deleted_screens_dir": False,
            "is_public": bool(cfg.slowpics.is_public),
            "is_hentai": bool(cfg.slowpics.is_hentai),
            "remove_after_days": int(cfg.slowpics.remove_after_days),
        },
        "report": {
            "enabled": bool(getattr(cfg.report, "enable", False)),
            "path": None,
            "output_dir": cfg.report.output_dir,
            "open_after_generate": bool(getattr(cfg.report, "open_after_generate", True)),
            "mode": cfg.report.default_mode,
        },
        "viewer": {
            "mode": "none",
            "mode_display": "None",
            "destination": None,
            "destination_label": "",
        },
        "warnings": [],
        "vspreview_mode": vspreview_mode_value,
        "suggested_frames": None,
        "suggested_seconds": 0.0,
        "vspreview_offer": None,
    }

    audio_track_override_map = metadata_utils.parse_audio_track_overrides(audio_track_overrides or [])

    vspreview_mode_display = (
        "baseline (0f applied to both clips)"
        if vspreview_mode_value == "baseline"
        else "seeded (suggested offsets applied before preview)"
    )

    layout_data: Dict[str, Any] = {
        "clips": {
            "count": 0,
            "items": [],
            "ref": {},
            "tgt": {},
        },
        "vspreview": {
            "mode": vspreview_mode_value,
            "mode_display": vspreview_mode_display,
            "suggested_frames": None,
            "suggested_seconds": 0.0,
            "script_path": None,
            "script_command": "",
            "missing": {
                "active": False,
                "windows_install": vspreview_utils.VSPREVIEW_WINDOWS_INSTALL,
                "posix_install": vspreview_utils.VSPREVIEW_POSIX_INSTALL,
                "command": "",
                "reason": "",
            },
            "clips": {
                "ref": {"label": ""},
                "tgt": {"label": ""},
            },
        },
        "trims": {},
        "window": json_tail["window"],
        "alignment": json_tail["alignment"],
        "audio_alignment": json_tail["audio_alignment"],
        "analysis": json_tail["analysis"],
        "render": json_tail.get("render", {}),
        "tonemap": json_tail.get("tonemap", {}),
        "overlay": json_tail.get("overlay", {}),
        "verify": json_tail.get("verify", {}),
        "cache": json_tail["cache"],
        "slowpics": json_tail["slowpics"],
        "report": json_tail["report"],
        "tmdb": {
            "category": None,
            "id": None,
            "title": None,
            "year": None,
            "lang": None,
        },
        "overrides": {
            "change_fps": "change_fps" if cfg.overrides.change_fps else "none",
        },
        "viewer": json_tail["viewer"],
        "warnings": [],
    }

    reporter.update_values(layout_data)
    reporter.set_flag("upload_enabled", bool(cfg.slowpics.auto_upload))
    reporter.set_flag("tmdb_resolved", False)

    vs_core.configure(
        search_paths=cfg.runtime.vapoursynth_python_paths,
        source_preference=cfg.source.preferred,
    )

    try:
        files = media_utils.discover_media(root)
    except OSError as exc:
        raise CLIAppError(
            f"Failed to list input directory: {exc}",
            rich_message=f"[red]Failed to list input directory:[/red] {exc}",
        ) from exc

    if len(files) < 2:
        raise CLIAppError(
            "Need at least two video files to compare.",
            rich_message="[red]Need at least two video files to compare.[/red]",
        )

    metadata = metadata_utils.parse_metadata(files, cfg.naming)
    year_hint_raw = metadata_utils.first_non_empty(metadata, "year")
    metadata_title = metadata_utils.first_non_empty(metadata, "title") or metadata_utils.first_non_empty(metadata, "anime_title")
    tmdb_resolution: TMDBResolution | None = None
    manual_tmdb: tuple[str, str] | None = None
    tmdb_category: Optional[str] = None
    tmdb_id_value: Optional[str] = None
    tmdb_language: Optional[str] = None
    tmdb_error_message: Optional[str] = None
    tmdb_ambiguous = False
    tmdb_api_key_present = bool(cfg.tmdb.api_key.strip())
    tmdb_notes: List[str] = []
    slowpics_tmdb_disclosure_line: Optional[str] = None
    slowpics_verbose_tmdb_tag: Optional[str] = None

    def _record_tmdb_note(raw_message: str) -> None:
        """Capture TMDB warnings with console-safe text."""

        safe_message = _sanitize_console_text(raw_message)
        tmdb_notes.append(safe_message)
        collected_warnings.append(safe_message)

    if tmdb_api_key_present:
        lookup = tmdb_workflow.resolve_workflow(
            files=files,
            metadata=metadata,
            tmdb_cfg=cfg.tmdb,
            year_hint_raw=year_hint_raw,
        )
        tmdb_resolution = lookup.resolution
        manual_tmdb = lookup.manual_override
        tmdb_error_message = lookup.error_message
        tmdb_ambiguous = lookup.ambiguous

    if tmdb_resolution is not None:
        tmdb_category = tmdb_resolution.category
        tmdb_id_value = tmdb_resolution.tmdb_id
        tmdb_language = tmdb_resolution.original_language

    if manual_tmdb:
        tmdb_category, tmdb_id_value = manual_tmdb
        tmdb_language = None
        tmdb_resolution = None
        logger.info("TMDB manual override selected: %s/%s", tmdb_category, tmdb_id_value)

    if tmdb_error_message and tmdb_api_key_present:
        logger.warning("TMDB lookup failed for %s: %s", files[0].name, tmdb_error_message)

    tmdb_context: Dict[str, str] = {
        "Title": metadata_title or ((metadata[0].get("label") or "") if metadata else ""),
        "OriginalTitle": "",
        "Year": year_hint_raw or "",
        "TMDBId": tmdb_id_value or "",
        "TMDBCategory": tmdb_category or "",
        "OriginalLanguage": tmdb_language or "",
        "Filename": files[0].stem,
        "FileName": files[0].name,
        "Label": (metadata[0].get("label") or files[0].name) if metadata else files[0].name,
    }

    if tmdb_resolution is not None:
        if tmdb_resolution.title:
            tmdb_context["Title"] = tmdb_resolution.title
        if tmdb_resolution.original_title:
            tmdb_context["OriginalTitle"] = tmdb_resolution.original_title
        if tmdb_resolution.year is not None:
            tmdb_context["Year"] = str(tmdb_resolution.year)
        if tmdb_resolution.original_language:
            tmdb_context["OriginalLanguage"] = tmdb_resolution.original_language
        tmdb_category = tmdb_category or tmdb_resolution.category
        tmdb_id_value = tmdb_id_value or tmdb_resolution.tmdb_id

    if tmdb_id_value and not (cfg.slowpics.tmdb_id or "").strip():
        cfg.slowpics.tmdb_id = str(tmdb_id_value)
    if tmdb_category and not (getattr(cfg.slowpics, "tmdb_category", "") or "").strip():
        cfg.slowpics.tmdb_category = tmdb_category

    suffix_literal = getattr(cfg.slowpics, "collection_suffix", "") or ""
    suffix = suffix_literal.strip()
    template_raw = cfg.slowpics.collection_name or ""
    collection_template = template_raw.strip()

    resolved_title_value = (tmdb_context.get("Title") or "").strip()
    resolved_year_value = (tmdb_context.get("Year") or "").strip()
    resolved_base_title: Optional[str] = None
    if resolved_title_value:
        resolved_base_title = resolved_title_value
        if resolved_year_value:
            resolved_base_title = f"{resolved_title_value} ({resolved_year_value})"

    # slow.pics title policy: an explicit collection_name template is treated as the exact
    # destination title, while the suffix is only appended when we fall back to the resolved
    # base title (ResolvedTitle + optional Year). This mirrors the README contract.
    if collection_template:
        rendered_collection = tmdb_workflow.render_collection_name(collection_template, tmdb_context).strip()
        final_collection_name = rendered_collection or "Frame Comparison"
    else:
        derived_title = resolved_title_value or metadata_title or files[0].stem
        derived_year = resolved_year_value
        base_collection = (derived_title or "").strip()
        if base_collection and derived_year:
            base_collection = f"{base_collection} ({derived_year})"
        final_collection_name = base_collection or "Frame Comparison"
        if suffix:
            final_collection_name = f"{final_collection_name} {suffix}" if final_collection_name else suffix

    cfg.slowpics.collection_name = final_collection_name
    slowpics_final_title = final_collection_name
    slowpics_resolved_base = resolved_base_title
    slowpics_title_inputs: SlowpicsTitleInputs = {
        "resolved_base": slowpics_resolved_base,
        "collection_name": cfg.slowpics.collection_name,
        "collection_suffix": suffix_literal,
    }
    slowpics_inputs_json = json_tail["slowpics"]["title"]["inputs"]
    slowpics_inputs_json["resolved_base"] = slowpics_title_inputs["resolved_base"]
    slowpics_inputs_json["collection_name"] = slowpics_title_inputs["collection_name"]
    slowpics_inputs_json["collection_suffix"] = slowpics_title_inputs["collection_suffix"]
    json_tail["slowpics"]["title"]["final"] = slowpics_final_title
    slowpics_layout_view = layout_data.get("slowpics", {})
    slowpics_layout_view["collection_name"] = slowpics_final_title
    slowpics_layout_view["auto_upload"] = bool(cfg.slowpics.auto_upload)
    slowpics_layout_view.setdefault(
        "status",
        "pending" if cfg.slowpics.auto_upload else "disabled",
    )
    layout_data["slowpics"] = slowpics_layout_view
    reporter.update_values(layout_data)

    if tmdb_resolution is not None:
        match_title = tmdb_resolution.title or tmdb_context.get("Title") or files[0].stem
        year_display = tmdb_context.get("Year") or ""
        lang_text = tmdb_resolution.original_language or "und"
        tmdb_identifier = f"{tmdb_resolution.category}/{tmdb_resolution.tmdb_id}"
        safe_match_title = _sanitize_console_text(match_title)
        safe_year_display = _sanitize_console_text(year_display)
        safe_lang_text = _sanitize_console_text(lang_text)
        title_segment = _color_text(
            escape(f'"{safe_match_title} ({safe_year_display})"'),
            "bright_white",
        )
        lang_segment = _format_kv("lang", safe_lang_text, label_style="dim cyan", value_style="blue")
        reporter.verbose_line(
            "  ".join(
                [
                    _format_kv("TMDB", tmdb_identifier, label_style="cyan", value_style="bright_white"),
                    title_segment,
                    lang_segment,
                ]
            )
        )
        heuristic = (tmdb_resolution.candidate.reason or "match").replace("_", " ").replace("-", " ")
        source = "filename" if tmdb_resolution.candidate.used_filename_search else "external id"
        reporter.verbose_line(
            f"TMDB match heuristics: source={source} heuristic={heuristic.strip()}"
        )
        if slowpics_resolved_base:
            base_display = slowpics_resolved_base
        elif match_title and year_display:
            base_display = f"{match_title} ({year_display})"
        else:
            base_display = match_title or "(n/a)"
        safe_base_display = _sanitize_console_text(base_display)
        slowpics_tmdb_disclosure_line = (
            f'slow.pics title inputs: base="{escape(safe_base_display)}"  '
            f'collection_suffix="{escape(str(suffix_literal))}"'
        )
        if tmdb_category and tmdb_id_value:
            slowpics_verbose_tmdb_tag = f"TMDB={tmdb_category}_{tmdb_id_value}"
        layout_data["tmdb"].update(
            {
                "category": tmdb_resolution.category,
                "id": tmdb_resolution.tmdb_id,
                "title": match_title,
                "year": year_display,
                "lang": lang_text,
            }
        )
        reporter.set_flag("tmdb_resolved", True)
    elif manual_tmdb:
        display_title = tmdb_context.get("Title") or files[0].stem
        category_display = tmdb_category or cfg.slowpics.tmdb_category or ""
        id_display = tmdb_id_value or cfg.slowpics.tmdb_id or ""
        lang_text = tmdb_language or tmdb_context.get("OriginalLanguage") or "und"
        identifier = f"{category_display}/{id_display}".strip("/")
        safe_display_title = _sanitize_console_text(display_title)
        safe_year_component = _sanitize_console_text(tmdb_context.get("Year") or "")
        title_segment = _color_text(
            escape(f'"{safe_display_title} ({safe_year_component})"'),
            "bright_white",
        )
        safe_lang_text = _sanitize_console_text(lang_text)
        lang_segment = _format_kv("lang", safe_lang_text, label_style="dim cyan", value_style="blue")
        reporter.verbose_line(
            "  ".join(
                [
                    _format_kv("TMDB", identifier, label_style="cyan", value_style="bright_white"),
                    title_segment,
                    lang_segment,
                ]
            )
        )
        if slowpics_resolved_base:
            base_display = slowpics_resolved_base
        else:
            year_component = tmdb_context.get("Year") or ""
            if display_title and year_component:
                base_display = f"{display_title} ({year_component})"
            else:
                base_display = display_title or "(n/a)"
        safe_base_display = _sanitize_console_text(base_display)
        slowpics_tmdb_disclosure_line = (
            f'slow.pics title inputs: base="{escape(safe_base_display)}"  '
            f'collection_suffix="{escape(str(suffix_literal))}"'
        )
        if category_display and id_display:
            slowpics_verbose_tmdb_tag = f"TMDB={category_display}_{id_display}"
        layout_data["tmdb"].update(
            {
                "category": category_display,
                "id": id_display,
                "title": display_title,
                "year": tmdb_context.get("Year") or "",
                "lang": lang_text,
            }
        )
        reporter.set_flag("tmdb_resolved", True)
    elif tmdb_api_key_present:
        if tmdb_error_message:
            _record_tmdb_note(f"TMDB lookup failed: {tmdb_error_message}")
        elif tmdb_ambiguous:
            _record_tmdb_note(
                f"TMDB ambiguous results for {files[0].name}; continuing without metadata."
            )
        else:
            _record_tmdb_note(f"TMDB could not find a confident match for {files[0].name}.")
    elif not (cfg.slowpics.tmdb_id or "").strip():
        _record_tmdb_note(
            "TMDB disabled: set [tmdb].api_key in config.toml to enable automatic matching."
        )

    plans = planner_utils.build_plans(files, metadata, cfg)
    analyze_path = core.pick_analyze_file(files, metadata, cfg.analysis.analyze_clip, cache_dir=root)

    try:
        selection_utils.probe_clip_metadata(plans, cfg.runtime, root, reporter=reporter)
    except ClipInitError as exc:
        raise CLIAppError(
            f"Failed to open clip: {exc}",
            rich_message=f"[red]Failed to open clip:[/red] {exc}",
        ) from exc

    alignment_summary, alignment_display = alignment_runner.apply_audio_alignment(
        plans,
        cfg,
        analyze_path,
        root,
        audio_track_override_map,
        reporter=reporter,
    )
    alignment_runner.format_alignment_output(
        plans,
        alignment_summary,
        alignment_display,
        cfg=cfg,
        root=root,
        reporter=reporter,
        json_tail=json_tail,
        vspreview_mode=vspreview_mode_value,
        collected_warnings=collected_warnings,
    )

    if (
        alignment_summary is not None
        and alignment_display is not None
        and cfg.audio_alignment.enable
        and not alignment_summary.suggestion_mode
    ):
        core.confirm_alignment_with_screenshots(
            plans,
            alignment_summary,
            cfg,
            root,
            reporter,
            alignment_display,
        )

    try:
        selection_utils.init_clips(plans, cfg.runtime, root, reporter=reporter)
    except ClipInitError as exc:
        raise CLIAppError(
            f"Failed to open clip: {exc}", rich_message=f"[red]Failed to open clip:[/red] {exc}"
        ) from exc

    clips = [plan.clip for plan in plans]
    if any(clip is None for clip in clips):
        raise CLIAppError("Clip initialisation failed")
    stored_props_seq = [
        dict(plan.source_frame_props) if plan.source_frame_props is not None else None
        for plan in plans
    ]

    clip_records: List[ClipRecord] = []
    trim_details: List[TrimSummary] = []
    for plan in plans:
        label = (plan.metadata.get("label") or plan.path.name).strip()
        frames_total = int(plan.source_num_frames or getattr(plan.clip, "num_frames", 0) or 0)
        width = int(plan.source_width or getattr(plan.clip, "width", 0) or 0)
        height = int(plan.source_height or getattr(plan.clip, "height", 0) or 0)
        fps_tuple = plan.effective_fps or plan.source_fps or (24000, 1001)
        fps_float = runtime_utils.fps_to_float(fps_tuple)
        duration_seconds = frames_total / fps_float if fps_float > 0 else 0.0
        clip_records.append(
            {
                "label": label,
                "width": width,
                "height": height,
                "fps": fps_float,
                "frames": frames_total,
                "duration": duration_seconds,
                "duration_tc": runtime_utils.format_seconds(duration_seconds),
                "path": str(plan.path),
            }
        )
        json_tail["clips"].append(
            {
                "label": label,
                "width": width,
                "height": height,
                "fps": fps_float,
                "frames": frames_total,
                "duration_s": duration_seconds,
                "duration_tc": runtime_utils.format_seconds(duration_seconds),
                "path": str(plan.path),
            }
        )

        lead_frames = max(0, int(plan.trim_start))
        lead_seconds = lead_frames / fps_float if fps_float > 0 else 0.0
        trail_frames = 0
        if plan.trim_end is not None and plan.trim_end != 0:
            if plan.trim_end < 0:
                trail_frames = abs(int(plan.trim_end))
            else:
                trail_frames = 0
        trail_seconds = trail_frames / fps_float if fps_float > 0 else 0.0
        trim_details.append(
            {
                "label": label,
                "lead_frames": lead_frames,
                "lead_seconds": lead_seconds,
                "trail_frames": trail_frames,
                "trail_seconds": trail_seconds,
            }
        )
        clip_trim: TrimClipEntry = {
            "lead_f": lead_frames,
            "trail_f": trail_frames,
            "lead_s": lead_seconds,
            "trail_s": trail_seconds,
        }
        json_tail["trims"]["per_clip"][label] = clip_trim

    analyze_index = [plan.path for plan in plans].index(analyze_path)
    analyze_clip = plans[analyze_index].clip
    if analyze_clip is None:
        raise CLIAppError("Missing clip for analysis")

    selection_specs, frame_window, windows_collapsed = selection_utils.resolve_selection_windows(
        plans, cfg.analysis
    )
    analyze_fps_num, analyze_fps_den = plans[analyze_index].effective_fps or selection_utils.extract_clip_fps(
        analyze_clip
    )
    analyze_fps = analyze_fps_num / analyze_fps_den if analyze_fps_den else 0.0
    manual_start_frame, manual_end_frame = frame_window
    analyze_total_frames = clip_records[analyze_index]["frames"]
    manual_start_seconds_value = manual_start_frame / analyze_fps if analyze_fps > 0 else float(manual_start_frame)
    manual_end_seconds_value = manual_end_frame / analyze_fps if analyze_fps > 0 else float(manual_end_frame)
    manual_end_changed = manual_end_frame < analyze_total_frames
    json_tail["alignment"] = {
        "manual_start_s": manual_start_seconds_value,
        "manual_end_s": manual_end_seconds_value if manual_end_changed else None,
    }
    layout_data["alignment"] = json_tail["alignment"]

    json_tail["window"] = {
        "ignore_lead_seconds": float(cfg.analysis.ignore_lead_seconds),
        "ignore_trail_seconds": float(cfg.analysis.ignore_trail_seconds),
        "min_window_seconds": float(cfg.analysis.min_window_seconds),
    }
    layout_data["window"] = json_tail["window"]

    for plan, spec in zip(plans, selection_specs):
        if not spec.warnings:
            continue
        label = plan.metadata.get("label") or plan.path.name
        for warning in spec.warnings:
            message = f"Window warning for {label}: {warning}"
            collected_warnings.append(message)
    if windows_collapsed:
        message = "Ignore lead/trail settings did not overlap across all sources; using fallback range."
        collected_warnings.append(message)

    cache_info = cache_utils.build_cache_info(root, plans, cfg, analyze_index)

    cache_filename = cfg.analysis.frame_data_filename
    cache_status = "disabled"
    cache_reason = None
    cache_progress_message: Optional[str] = None
    cache_probe: CacheLoadResult | None = None

    if not cfg.analysis.save_frames_data:
        cache_status = "disabled"
        cache_reason = "save_frames_data=false"
    elif cache_info is None:
        cache_status = "disabled"
        cache_reason = "no_cache_info"
    else:
        cache_path = cache_info.path
        if cache_path.exists():
            probe_result = probe_cached_metrics(cache_info, cfg.analysis)
            cache_probe = probe_result
            if probe_result.status == "reused":
                cache_status = "reused"
                cache_progress_message = (
                    f"Loading cached frame metrics from {cache_path.name}…"
                )
                reporter.line(
                    f"[green]Reused cached frame metrics from {escape(cache_path.name)}[/]"
                )
            else:
                cache_status = "recomputed"
                reason_code = probe_result.reason or probe_result.status or "unknown"
                cache_reason = reason_code
                human_reason = reason_code.replace("_", " ").strip() or "unknown"
                reporter.line(
                    f"[yellow]Frame metrics cache {probe_result.status} "
                    f"({escape(human_reason)}); recomputing…[/]"
                )
                cache_progress_message = f"Recomputing frame metrics ({human_reason})…"
        else:
            cache_status = "recomputed"
            cache_reason = "missing"
            cache_probe = CacheLoadResult(metrics=None, status="missing", reason="missing")
            reporter.line("[yellow]Frame metrics cache missing; recomputing…[/]")
            cache_progress_message = "Recomputing frame metrics (missing)…"

    json_tail["cache"] = {
        "file": cache_filename,
        "status": cache_status,
    }
    if cache_reason:
        json_tail["cache"]["reason"] = cache_reason
    layout_data["cache"] = json_tail["cache"]

    step_size = max(1, int(cfg.analysis.step))
    total_frames = getattr(analyze_clip, 'num_frames', 0)
    sample_count = 0
    if isinstance(total_frames, int) and total_frames > 0:
        sample_count = (total_frames + step_size - 1) // step_size

    analyze_label_raw = plans[analyze_index].metadata.get('label') or analyze_path.name

    cache_ready = cache_probe is not None and cache_probe.status == "reused"
    if cache_ready and cache_info is not None:
        reporter.verbose_line(f"Using cached frame metrics: {cache_info.path.name}")
    elif cache_status == "recomputed" and cache_info is not None:
        reporter.verbose_line(f"Frame metrics cache will be refreshed: {cache_info.path.name}")
    overrides_text = "change_fps" if cfg.overrides.change_fps else "none"
    layout_data["overrides"]["change_fps"] = overrides_text

    analysis_method = "absdiff" if cfg.analysis.motion_use_absdiff else "edge"
    thresholds_cfg = cfg.analysis.thresholds
    threshold_mode_value = str(getattr(thresholds_cfg.mode, "value", thresholds_cfg.mode))
    threshold_mode_lower = threshold_mode_value.lower()
    threshold_payload: Dict[str, float | str] = {"mode": threshold_mode_value}
    if threshold_mode_lower == "quantile":
        threshold_payload.update(
            {
                "dark_quantile": float(thresholds_cfg.dark_quantile),
                "bright_quantile": float(thresholds_cfg.bright_quantile),
            }
        )
    else:
        threshold_payload.update(
            {
                "dark_luma_min": float(thresholds_cfg.dark_luma_min),
                "dark_luma_max": float(thresholds_cfg.dark_luma_max),
                "bright_luma_min": float(thresholds_cfg.bright_luma_min),
                "bright_luma_max": float(thresholds_cfg.bright_luma_max),
            }
        )

    json_tail["analysis"] = {
        "step": int(cfg.analysis.step),
        "downscale_height": int(cfg.analysis.downscale_height),
        "motion_method": analysis_method,
        "motion_scenecut_quantile": float(cfg.analysis.motion_scenecut_quantile),
        "motion_diff_radius": int(cfg.analysis.motion_diff_radius),
        "output_frame_count": 0,
        "counts": {
            "dark": int(cfg.analysis.frame_count_dark),
            "bright": int(cfg.analysis.frame_count_bright),
            "motion": int(cfg.analysis.frame_count_motion),
            "random": int(cfg.analysis.random_frames),
            "user": len(cfg.analysis.user_frames),
        },
        "screen_separation_sec": float(cfg.analysis.screen_separation_sec),
        "random_seed": int(cfg.analysis.random_seed),
        "thresholds": threshold_payload,
    }

    json_tail["analysis"]["cache_reused"] = bool(cache_ready)
    if cache_progress_message:
        json_tail["analysis"]["cache_progress_message"] = cache_progress_message

    layout_data["analysis"] = dict(json_tail["analysis"])
    layout_data["clips"]["count"] = len(clip_records)
    layout_data["clips"]["items"] = clip_records
    layout_data["clips"]["ref"] = clip_records[0] if clip_records else {}
    layout_data["clips"]["tgt"] = clip_records[1] if len(clip_records) > 1 else {}

    reference_label = ""
    if alignment_summary is not None:
        reference_label = _plan_label(alignment_summary.reference_plan)
    elif clip_records:
        reference_label = clip_records[0]["label"]

    vspreview_target_plan: ClipPlan | None = None
    vspreview_suggested_frames_value: int | None = None
    vspreview_suggested_seconds_value = 0.0
    if alignment_summary is not None:
        for plan in plans:
            if plan is alignment_summary.reference_plan:
                continue
            vspreview_target_plan = plan
            clip_key = plan.path.name
            vspreview_suggested_frames_value = derive_frame_hint(alignment_summary, clip_key)
            detail = alignment_summary.measured_offsets.get(clip_key)
            if detail and detail.offset_seconds is not None:
                vspreview_suggested_seconds_value = float(detail.offset_seconds)
            else:
                measurement_lookup = {
                    measurement.file.name: measurement
                    for measurement in alignment_summary.measurements
                }
                measurement = measurement_lookup.get(clip_key)
                if measurement and measurement.offset_seconds is not None:
                    vspreview_suggested_seconds_value = float(measurement.offset_seconds)
            break

    target_label = ""
    if vspreview_target_plan is not None:
        target_label = _plan_label(vspreview_target_plan)
    elif len(clip_records) > 1:
        target_label = clip_records[1]["label"]

    vspreview_block = coerce_str_mapping(layout_data.get("vspreview"))
    clips_block = coerce_str_mapping(vspreview_block.get("clips"))
    clips_block["ref"] = {"label": reference_label}
    clips_block["tgt"] = {"label": target_label}
    vspreview_block["clips"] = clips_block
    vspreview_block["mode"] = vspreview_mode_value
    vspreview_block["mode_display"] = vspreview_mode_display
    vspreview_block["suggested_frames"] = vspreview_suggested_frames_value
    vspreview_block["suggested_seconds"] = vspreview_suggested_seconds_value
    existing_vspreview_obj = reporter.values.get("vspreview")
    if isinstance(existing_vspreview_obj, MappingABC):
        existing_vspreview = coerce_str_mapping(cast(Mapping[str, object], existing_vspreview_obj))
        missing_existing_block = coerce_str_mapping(existing_vspreview.get("missing"))
        if missing_existing_block:
            missing_layout_block = coerce_str_mapping(vspreview_block.get("missing"))
            merged_missing_block = missing_layout_block.copy()
            merged_missing_block.update(missing_existing_block)
            vspreview_block["missing"] = merged_missing_block
        script_path_value = existing_vspreview.get("script_path")
        if isinstance(script_path_value, str) and script_path_value:
            vspreview_block["script_path"] = script_path_value
        script_command_value = existing_vspreview.get("script_command")
        if isinstance(script_command_value, str) and script_command_value:
            vspreview_block["script_command"] = script_command_value
        for key, value in existing_vspreview.items():
            if key in {"clips", "missing", "script_path", "script_command"}:
                continue
            if key not in vspreview_block:
                vspreview_block[key] = value
    layout_data["vspreview"] = vspreview_block

    trims_per_clip = json_tail["trims"]["per_clip"]
    trim_lookup: dict[str, TrimSummary] = {detail["label"]: detail for detail in trim_details}

    def _trim_entry(label: str) -> TrimClipEntry:
        """
        Build a normalized trim entry for a clip label containing frame and second offsets.

        Parameters:
            label (str): Clip label used to look up trim and detailed timing information.

        Returns:
            dict: Mapping with keys:
                - "lead_f": number of leading frames trimmed (int, default 0)
                - "trail_f": number of trailing frames trimmed (int, default 0)
                - "lead_s": leading trim in seconds (float, default 0.0)
                - "trail_s": trailing trim in seconds (float, default 0.0)
        """
        trim = trims_per_clip.get(label)
        detail = trim_lookup.get(label)
        return {
            "lead_f": trim["lead_f"] if trim else 0,
            "trail_f": trim["trail_f"] if trim else 0,
            "lead_s": detail["lead_seconds"] if detail else 0.0,
            "trail_s": detail["trail_seconds"] if detail else 0.0,
        }

    layout_data["trims"] = {}
    if clip_records:
        layout_data["trims"]["ref"] = _trim_entry(clip_records[0]["label"])
    if len(clip_records) > 1:
        layout_data["trims"]["tgt"] = _trim_entry(clip_records[1]["label"])

    reporter.update_values(layout_data)
    reporter.render_sections(["vspreview_missing", "vspreview_info", "at_a_glance", "discover", "prepare"])
    reporter.render_sections(["audio_align"])
    reporter.render_sections(["analyze"])
    if tmdb_notes:
        for note in tmdb_notes:
            reporter.verbose_line(note)
    if slowpics_tmdb_disclosure_line:
        reporter.verbose_line(slowpics_tmdb_disclosure_line)

    if alignment_display is not None:
        json_tail["audio_alignment"]["preview_paths"] = alignment_display.preview_paths
        confirmation_value = alignment_display.confirmation
        if confirmation_value is None and alignment_summary is not None:
            confirmation_value = "auto"
        json_tail["audio_alignment"]["confirmed"] = confirmation_value
    audio_alignment_view = copy.deepcopy(json_tail["audio_alignment"])
    audio_alignment_layout = cast(dict[str, object], audio_alignment_view)
    offsets_sec_map_obj = coerce_str_mapping(audio_alignment_layout.get("offsets_sec"))
    offsets_frames_map_obj = coerce_str_mapping(audio_alignment_layout.get("offsets_frames"))
    if alignment_display is not None:
        correlations_map: dict[str, float] = dict(alignment_display.correlations)
    else:
        correlations_map = {}
    primary_label: str | None = None
    if offsets_sec_map_obj:
        primary_label = sorted(offsets_sec_map_obj.keys())[0]
    offsets_sec_value_obj = offsets_sec_map_obj.get(primary_label) if primary_label else None
    offsets_sec_value = (
        float(offsets_sec_value_obj)
        if isinstance(offsets_sec_value_obj, (int, float))
        else 0.0
    )
    offsets_frames_value_obj = offsets_frames_map_obj.get(primary_label) if primary_label else None
    offsets_frames_value = (
        int(offsets_frames_value_obj)
        if isinstance(offsets_frames_value_obj, (int, float))
        else 0
    )
    corr_value_obj = correlations_map.get(primary_label) if primary_label else None
    corr_value = (
        float(corr_value_obj)
        if isinstance(corr_value_obj, (int, float))
        else 0.0
    )
    if math.isnan(corr_value):
        corr_value = 0.0
    threshold_value = float(getattr(alignment_display, "threshold", cfg.audio_alignment.correlation_threshold))
    audio_alignment_layout.update(
        {
            "offsets_sec": offsets_sec_value,
            "offsets_frames": offsets_frames_value,
            "corr": corr_value,
            "threshold": threshold_value,
        }
    )
    audio_alignment_layout["measurements"] = json_tail["audio_alignment"].get("measurements", {})
    layout_data["audio_alignment"] = audio_alignment_layout

    using_frame_total = isinstance(total_frames, int) and total_frames > 0
    progress_total = int(total_frames) if using_frame_total else int(sample_count)

    def _run_selection(
        progress_callback: Callable[[int], None] | None = None,
    ) -> tuple[list[int], dict[int, str], Dict[int, SelectionDetail]]:
        try:
            result = select_frames(
                analyze_clip,
                cfg.analysis,
                [plan.path.name for plan in plans],
                analyze_path.name,
                cache_info=cache_info,
                progress=progress_callback,
                frame_window=frame_window,
                return_metadata=True,
                color_cfg=cfg.color,
                cache_probe=cache_probe,
            )
        except TypeError as exc:
            if "return_metadata" not in str(exc):
                raise
            result = select_frames(
                analyze_clip,
                cfg.analysis,
                [plan.path.name for plan in plans],
                analyze_path.name,
                cache_info=cache_info,
                progress=progress_callback,
                frame_window=frame_window,
                color_cfg=cfg.color,
                cache_probe=cache_probe,
            )
        if isinstance(result, tuple):
            if len(result) == 3:
                return result
            if len(result) == 2:
                frames_only, categories = cast(
                    tuple[list[int], dict[int, str]], result
                )
                return frames_only, categories, {}
            frames_iter = cast(Iterable[int], result)
            frames_only = list(frames_iter)
            return frames_only, {frame: "Auto" for frame in frames_only}, {}
        frames_only = list(result)
        return frames_only, {frame: "Auto" for frame in frames_only}, {}

    selection_details: Dict[int, SelectionDetail] = {}

    try:
        if sample_count > 0 and not cache_ready:
            start_time = time.perf_counter()
            samples_done = 0
            reporter.update_progress_state(
                "analyze_bar",
                fps="0.00 fps",
                eta_tc="--:--",
                elapsed_tc="00:00",
            )
            with reporter.create_progress("analyze_bar", transient=False) as analysis_progress:
                task_id = analysis_progress.add_task(
                    analyze_label_raw,
                    total=max(1, progress_total),
                )

                def _advance_samples(count: int) -> None:
                    """Advance sample counter, update stats, and refresh progress displays."""
                    nonlocal samples_done
                    samples_done += count
                    if progress_total <= 0:
                        return
                    elapsed = max(time.perf_counter() - start_time, 1e-6)
                    frames_processed = samples_done * step_size
                    completed = (
                        min(progress_total, frames_processed)
                        if using_frame_total
                        else min(progress_total, samples_done)
                    )
                    fps_val = frames_processed / elapsed
                    remaining = max(progress_total - completed, 0)
                    eta_seconds = (remaining / fps_val) if fps_val > 0 else None
                    reporter.update_progress_state(
                        "analyze_bar",
                        fps=f"{fps_val:7.2f} fps",
                        eta_tc=runtime_utils.format_clock(eta_seconds),
                        elapsed_tc=runtime_utils.format_clock(elapsed),
                    )
                    analysis_progress.update(task_id, completed=completed)

                frames, frame_categories, selection_details = _run_selection(_advance_samples)
                final_completed = progress_total if progress_total > 0 else analysis_progress.tasks[task_id].completed
                analysis_progress.update(task_id, completed=final_completed)
        else:
            frames, frame_categories, selection_details = _run_selection()

    except Exception as exc:
        tb = traceback.format_exc()
        reporter.console.print("[red]Frame selection trace:[/red]")
        reporter.console.print(tb)
        logger.error("Frame selection trace:\\n%s", tb)
        raise CLIAppError(
            f"Frame selection failed: {exc}",
            rich_message=f"[red]Frame selection failed:[/red] {exc}",
        ) from exc

    if not frames:
        raise CLIAppError(
            "No frames were selected; cannot continue.",
            rich_message="[red]No frames were selected; cannot continue.[/red]",
        )

    selection_hash_value = selection_hash_for_config(cfg.analysis)
    clip_paths = [plan.path for plan in plans]
    selection_sidecar_dir = cache_info.path.parent if cache_info is not None else root
    selection_sidecar_path = selection_sidecar_dir / "generated.selection.v1.json"
    selection_overlay_details = {
        frame: {
            "label": detail.label,
            "timecode": detail.timecode,
            "source": detail.source,
            "score": detail.score,
            "notes": detail.notes,
        }
        for frame, detail in selection_details.items()
    }
    if cache_info is None or not cfg.analysis.save_frames_data:
        export_selection_metadata(
            selection_sidecar_path,
            analyzed_file=analyze_path.name,
            clip_paths=clip_paths,
            cfg=cfg.analysis,
            selection_hash=selection_hash_value,
            selection_frames=frames,
            selection_details=selection_details,
        )
    if not cfg.analysis.save_frames_data:
        compframes_path = preflight_utils.resolve_subdir(
            root,
            cfg.analysis.frame_data_filename,
            purpose="analysis.frame_data_filename",
        )
        write_selection_cache_file(
            compframes_path,
            analyzed_file=analyze_path.name,
            clip_paths=clip_paths,
            cfg=cfg.analysis,
            selection_hash=selection_hash_value,
            selection_frames=frames,
            selection_details=selection_details,
            selection_categories=frame_categories,
        )
    kept_count = len(frames)
    scanned_count = progress_total if progress_total > 0 else max(sample_count, kept_count)
    selection_counts = Counter(detail.label or "Auto" for detail in selection_details.values())
    json_tail["analysis"]["selection_counts"] = dict(selection_counts)
    json_tail["analysis"]["selection_hash"] = selection_hash_value
    json_tail["analysis"]["selection_sidecar"] = str(selection_sidecar_path)
    json_tail["analysis"]["selection_details"] = selection_details_to_json(
        selection_details
    )
    cache_summary_label = "reused" if cache_status == "reused" else ("new" if cache_status == "recomputed" else cache_status)
    json_tail["analysis"]["kept"] = kept_count
    json_tail["analysis"]["scanned"] = scanned_count
    layout_data["analysis"]["kept"] = kept_count
    layout_data["analysis"]["scanned"] = scanned_count
    layout_data["analysis"]["cache_summary_label"] = cache_summary_label
    layout_data["analysis"]["selection_counts"] = dict(selection_counts)
    layout_data["analysis"]["selection_hash"] = selection_hash_value
    layout_data["analysis"]["selection_sidecar"] = str(selection_sidecar_path)
    layout_data["analysis"]["selection_details"] = json_tail["analysis"]["selection_details"]
    reporter.update_values(layout_data)

    preview_rule: dict[str, Any] = {}
    layout_obj = getattr(reporter, "layout", None)
    folding_rules_obj = getattr(layout_obj, "folding", None)
    if isinstance(folding_rules_obj, Mapping):
        folding_rules_map = cast(Mapping[str, object], folding_rules_obj)
        frames_preview_obj = folding_rules_map.get("frames_preview")
        if isinstance(frames_preview_obj, Mapping):
            preview_rule = dict(cast(Mapping[str, Any], frames_preview_obj))
    head_raw: Any = preview_rule["head"] if "head" in preview_rule else None
    tail_raw: Any = preview_rule["tail"] if "tail" in preview_rule else None
    when_raw: Any = preview_rule["when"] if "when" in preview_rule else None
    head = int(head_raw) if isinstance(head_raw, (int, float)) else 4
    tail = int(tail_raw) if isinstance(tail_raw, (int, float)) else 4
    joiner = str(preview_rule["joiner"] if "joiner" in preview_rule else ", ")
    when_text = str(when_raw) if isinstance(when_raw, str) and when_raw else None
    fold_enabled = runtime_utils.evaluate_rule_condition(when_text, flags=reporter.flags)
    preview_text = runtime_utils.fold_sequence(frames, head=head, tail=tail, joiner=joiner, enabled=fold_enabled)

    json_tail["analysis"]["output_frame_count"] = kept_count
    json_tail["analysis"]["output_frames"] = list(frames)
    json_tail["analysis"]["output_frames_preview"] = preview_text
    layout_data["analysis"]["output_frame_count"] = kept_count
    layout_data["analysis"]["output_frames_preview"] = preview_text
    if not emit_json_tail_flag:
        full_list_text = ", ".join(str(frame) for frame in frames)
        layout_data["analysis"]["output_frames_full"] = (
            f"[{full_list_text}]" if full_list_text else "[]"
        )
    reporter.update_values(layout_data)

    total_screens = len(frames) * len(plans)

    writer_name = "ffmpeg" if cfg.screenshots.use_ffmpeg else "vs"
    overlay_mode_value = getattr(cfg.color, "overlay_mode", "minimal")

    json_tail["render"] = {
        "writer": writer_name,
        "out_dir": str(out_dir),
        "add_frame_info": bool(cfg.screenshots.add_frame_info),
        "single_res": int(cfg.screenshots.single_res),
        "upscale": bool(cfg.screenshots.upscale),
        "mod_crop": int(cfg.screenshots.mod_crop),
        "letterbox_pillarbox_aware": bool(cfg.screenshots.letterbox_pillarbox_aware),
        "auto_letterbox_mode": str(getattr(cfg.screenshots, "auto_letterbox_crop", "off")),
        "pad_to_canvas": cfg.screenshots.pad_to_canvas,
        "center_pad": bool(cfg.screenshots.center_pad),
        "letterbox_px_tolerance": int(cfg.screenshots.letterbox_px_tolerance),
        "compression": int(cfg.screenshots.compression_level),
        "ffmpeg_timeout_seconds": float(cfg.screenshots.ffmpeg_timeout_seconds),
    }
    layout_data["render"] = json_tail["render"]
    effective_tonemap = vs_core.resolve_effective_tonemap(cfg.color)
    json_tail["tonemap"] = {
        "preset": effective_tonemap.get("preset", cfg.color.preset),
        "tone_curve": effective_tonemap.get("tone_curve", cfg.color.tone_curve),
        "dynamic_peak_detection": bool(effective_tonemap.get("dynamic_peak_detection", cfg.color.dynamic_peak_detection)),
        "dpd": bool(effective_tonemap.get("dynamic_peak_detection", cfg.color.dynamic_peak_detection)),
        "target_nits": float(effective_tonemap.get("target_nits", cfg.color.target_nits)),
        "dst_min_nits": float(effective_tonemap.get("dst_min_nits", cfg.color.dst_min_nits)),
        "knee_offset": float(effective_tonemap.get("knee_offset", getattr(cfg.color, "knee_offset", 0.5))),
        "dpd_preset": effective_tonemap.get("dpd_preset", getattr(cfg.color, "dpd_preset", "")),
        "dpd_black_cutoff": float(effective_tonemap.get("dpd_black_cutoff", getattr(cfg.color, "dpd_black_cutoff", 0.0))),
        "verify_luma_threshold": float(cfg.color.verify_luma_threshold),
        "overlay_enabled": bool(cfg.color.overlay_enabled),
        "overlay_mode": overlay_mode_value,
        "post_gamma": float(getattr(cfg.color, "post_gamma", 1.0)),
        "post_gamma_enabled": bool(getattr(cfg.color, "post_gamma_enable", False)),
        "smoothing_period": float(effective_tonemap.get("smoothing_period", getattr(cfg.color, "smoothing_period", 45.0))),
        "scene_threshold_low": float(effective_tonemap.get("scene_threshold_low", getattr(cfg.color, "scene_threshold_low", 0.8))),
        "scene_threshold_high": float(effective_tonemap.get("scene_threshold_high", getattr(cfg.color, "scene_threshold_high", 2.4))),
        "percentile": float(effective_tonemap.get("percentile", getattr(cfg.color, "percentile", 99.995))),
        "contrast_recovery": float(effective_tonemap.get("contrast_recovery", getattr(cfg.color, "contrast_recovery", 0.3))),
        "metadata": effective_tonemap.get("metadata", getattr(cfg.color, "metadata", "auto")),
        "use_dovi": effective_tonemap.get("use_dovi", getattr(cfg.color, "use_dovi", None)),
        "visualize_lut": bool(effective_tonemap.get("visualize_lut", getattr(cfg.color, "visualize_lut", False))),
        "show_clipping": bool(effective_tonemap.get("show_clipping", getattr(cfg.color, "show_clipping", False))),
    }
    metadata_code = json_tail["tonemap"]["metadata"]
    metadata_label_map = {
        0: "auto",
        1: "none",
        2: "hdr10",
        3: "hdr10+",
        4: "luminance",
    }
    if isinstance(metadata_code, int):
        metadata_label = metadata_label_map.get(metadata_code, "auto")
    elif isinstance(metadata_code, str):
        metadata_label = metadata_code
    else:
        metadata_label = "auto"
    json_tail["tonemap"]["metadata_label"] = metadata_label
    use_dovi_value = json_tail["tonemap"]["use_dovi"]
    if isinstance(use_dovi_value, str):
        lowered = use_dovi_value.strip().lower()
        if lowered in {"auto", ""}:
            use_dovi_label = "auto"
        elif lowered in {"true", "1", "yes", "on"}:
            use_dovi_label = "on"
        elif lowered in {"false", "0", "no", "off"}:
            use_dovi_label = "off"
        else:
            use_dovi_label = lowered or "auto"
    elif use_dovi_value is None:
        use_dovi_label = "auto"
    else:
        use_dovi_label = "on" if use_dovi_value else "off"
    json_tail["tonemap"]["use_dovi_label"] = use_dovi_label
    layout_data["tonemap"] = json_tail["tonemap"]
    json_tail["overlay"] = {
        "enabled": bool(cfg.color.overlay_enabled),
        "template": cfg.color.overlay_text_template,
        "mode": overlay_mode_value,
    }
    layout_data["overlay"] = json_tail["overlay"]

    reporter.update_values(layout_data)
    reporter.render_sections(["render"])

    verification_records: List[Dict[str, Any]] = []

    try:
        seen_pivot_messages: set[str] = set()

        def _notify_pivot(message: str) -> None:
            if message in seen_pivot_messages:
                return
            seen_pivot_messages.add(message)
            reporter.console.log(message, markup=False)

        if total_screens > 0:
            start_time = time.perf_counter()
            processed = 0
            clip_labels = [_plan_label(plan) for plan in plans]
            clip_total_frames = len(frames)
            clip_count = len(clip_labels)
            clip_progress_enabled = clip_count > 0 and clip_total_frames > 0
            if clip_progress_enabled:
                reporter.update_progress_state(
                    "render_clip_bar",
                    label=clip_labels[0],
                    clip_index=1,
                    clip_total=clip_count,
                    current=0,
                    total=clip_total_frames,
                )

            reporter.update_progress_state(
                "render_bar",
                fps=0.0,
                eta_tc="--:--",
                elapsed_tc="00:00",
                current=0,
                total=total_screens,
            )

            clip_progress = None
            clip_task_id: Optional[int] = None
            clip_index = 0
            clip_completed = 0

            def _clip_description(idx: int) -> str:
                if not clip_labels:
                    return "Rendering clip"
                bounded = max(0, min(idx, len(clip_labels) - 1))
                return f"{clip_labels[bounded]} ({bounded + 1}/{clip_count})"

            with ExitStack() as progress_stack:
                render_progress = progress_stack.enter_context(
                    reporter.create_progress("render_bar", transient=False)
                )
                task_id = render_progress.add_task(
                    "Rendering outputs",
                    total=total_screens,
                )
                if clip_progress_enabled:
                    clip_progress = progress_stack.enter_context(
                        reporter.create_progress("render_clip_bar", transient=False)
                    )
                    clip_task_id = clip_progress.add_task(
                        _clip_description(clip_index),
                        total=clip_total_frames,
                    )

                def advance_render(count: int) -> None:
                    """Update rendering progress metrics and visible bars."""
                    nonlocal processed
                    nonlocal clip_index
                    nonlocal clip_completed
                    processed += count
                    elapsed = max(time.perf_counter() - start_time, 1e-6)
                    fps_val = processed / elapsed
                    remaining = max(total_screens - processed, 0)
                    eta_seconds = (remaining / fps_val) if fps_val > 0 else None
                    reporter.update_progress_state(
                        "render_bar",
                        fps=fps_val,
                        eta_tc=runtime_utils.format_clock(eta_seconds),
                        elapsed_tc=runtime_utils.format_clock(elapsed),
                        current=min(processed, total_screens),
                        total=total_screens,
                    )
                    render_progress.update(task_id, completed=min(total_screens, processed))
                    if clip_progress_enabled and clip_progress is not None and clip_task_id is not None:
                        clip_completed += count
                        clip_completed = min(clip_completed, clip_total_frames)
                        clip_progress.update(
                            clip_task_id,
                            completed=clip_completed,
                            description=_clip_description(clip_index),
                        )
                        reporter.update_progress_state(
                            "render_clip_bar",
                            current=clip_completed,
                            total=clip_total_frames,
                            clip_index=clip_index + 1,
                            clip_total=clip_count,
                            label=clip_labels[clip_index],
                        )
                        if clip_completed >= clip_total_frames and clip_index + 1 < clip_count:
                            clip_index += 1
                            clip_completed = 0
                            cast(Any, clip_progress).reset(
                                clip_task_id,
                                total=clip_total_frames,
                            )
                            clip_progress.update(
                                clip_task_id,
                                completed=clip_completed,
                                description=_clip_description(clip_index),
                            )
                            reporter.update_progress_state(
                                "render_clip_bar",
                                current=clip_completed,
                                total=clip_total_frames,
                                clip_index=clip_index + 1,
                                clip_total=clip_count,
                                label=clip_labels[clip_index],
                            )

                image_paths = generate_screenshots(
                    clips,
                    frames,
                    [str(plan.path) for plan in plans],
                    [plan.metadata for plan in plans],
                    out_dir,
                    cfg.screenshots,
                    cfg.color,
                    trim_offsets=[plan.trim_start for plan in plans],
                    progress_callback=advance_render,
                    frame_labels=frame_categories,
                    selection_details=selection_overlay_details,
                    warnings_sink=collected_warnings,
                    verification_sink=verification_records,
                    pivot_notifier=_notify_pivot,
                    debug_color=bool(getattr(cfg.color, "debug_color", False)),
                    source_frame_props=stored_props_seq,
                )

                if processed < total_screens:
                    elapsed = max(time.perf_counter() - start_time, 1e-6)
                    fps_val = processed / elapsed
                    reporter.update_progress_state(
                        "render_bar",
                        fps=fps_val,
                        eta_tc=runtime_utils.format_clock(0.0),
                        elapsed_tc=runtime_utils.format_clock(elapsed),
                        current=total_screens,
                        total=total_screens,
                    )
                    render_progress.update(task_id, completed=total_screens)
                if clip_progress_enabled and clip_progress is not None and clip_task_id is not None:
                    clip_progress.update(
                        clip_task_id,
                        completed=clip_total_frames,
                        description=_clip_description(min(clip_index, clip_count - 1)),
                    )
                    reporter.update_progress_state(
                        "render_clip_bar",
                        current=clip_total_frames,
                        total=clip_total_frames,
                        clip_index=min(clip_index, clip_count - 1) + 1,
                        clip_total=clip_count,
                        label=clip_labels[min(clip_index, clip_count - 1)],
                    )
        else:
            image_paths = generate_screenshots(
                clips,
                frames,
                [str(plan.path) for plan in plans],
                [plan.metadata for plan in plans],
                out_dir,
                cfg.screenshots,
                cfg.color,
                trim_offsets=[plan.trim_start for plan in plans],
                frame_labels=frame_categories,
                selection_details=selection_overlay_details,
                warnings_sink=collected_warnings,
                verification_sink=verification_records,
                pivot_notifier=_notify_pivot,
                debug_color=bool(getattr(cfg.color, "debug_color", False)),
                source_frame_props=stored_props_seq,
            )
    except ClipProcessError as exc:
        hint = "Run 'frame-compare doctor' for dependency diagnostics."
        raise CLIAppError(
            f"Screenshot generation failed: {exc}\nHint: {hint}",
            rich_message=f"[red]Screenshot generation failed:[/red] {exc}\n[yellow]Hint:[/yellow] {hint}",
        ) from exc
    except ScreenshotError as exc:
        raise CLIAppError(
            f"Screenshot generation failed: {exc}",
            rich_message=f"[red]Screenshot generation failed:[/red] {exc}",
        ) from exc

    verify_threshold = float(cfg.color.verify_luma_threshold)
    if verification_records:
        max_entry = max(verification_records, key=lambda item: item["maximum"])
        delta_summary: dict[str, object] = {
            "max": float(max_entry["maximum"]),
            "average": float(max_entry["average"]),
            "frame": int(max_entry["frame"]),
            "file": str(max_entry["file"]),
            "auto_selected": bool(max_entry["auto_selected"]),
        }
        verify_summary = cast(
            dict[str, object],
            {
                "count": len(verification_records),
                "threshold": verify_threshold,
                "delta": delta_summary,
                "entries": [dict(entry) for entry in verification_records],
            },
        )
    else:
        verify_summary = cast(
            dict[str, object],
            {
                "count": 0,
                "threshold": verify_threshold,
                "delta": {
                    "max": None,
                    "average": None,
                    "frame": None,
                    "file": None,
                    "auto_selected": None,
                },
                "entries": [],
            },
        )

    json_tail["verify"] = verify_summary
    layout_data["verify"] = verify_summary

    slowpics_url: Optional[str] = None
    reporter.render_sections(["publish"])
    reporter.line(_color_text("slow.pics collection (preview):", "blue"))
    inputs_parts = [
        _format_kv(
            "collection_name",
            slowpics_title_inputs["collection_name"],
            label_style="dim blue",
            value_style="bright_white",
        ),
        _format_kv(
            "collection_suffix",
            slowpics_title_inputs["collection_suffix"],
            label_style="dim blue",
            value_style="bright_white",
        ),
    ]
    reporter.line("  " + "  ".join(inputs_parts))
    resolved_display = slowpics_resolved_base or "(n/a)"
    reporter.line(
        "  "
        + _format_kv(
            "resolved_base",
            resolved_display,
            label_style="dim blue",
            value_style="bright_white",
        )
    )
    reporter.line(
        "  "
        + _format_kv(
            "final",
            f'"{slowpics_final_title}"',
            label_style="dim blue",
            value_style="bold bright_white",
        )
    )
    if slowpics_verbose_tmdb_tag:
        reporter.verbose_line(f"  {escape(slowpics_verbose_tmdb_tag)}")
    if cfg.slowpics.auto_upload:
        layout_data["slowpics"]["status"] = "preparing"
        reporter.update_values(layout_data)
        reporter.console.print("[cyan]Preparing slow.pics upload...[/cyan]")
        upload_total = len(image_paths)
        def _safe_size(path_str: str) -> int:
            """
            Return the file size for a given filesystem path, or 0 if the file cannot be accessed.

            Parameters:
                path_str (str): Filesystem path to the file.

            Returns:
                int: File size in bytes, or 0 if stat fails (e.g., file does not exist or is unreadable).
            """
            try:
                return Path(path_str).stat().st_size
            except OSError:
                return 0

        file_sizes = [_safe_size(path) for path in image_paths] if upload_total else []
        total_bytes = sum(file_sizes)

        console_width = getattr(reporter.console.size, "width", 80) or 80
        stats_width_limit = max(24, console_width - 32)

        def _format_duration(seconds: Optional[float]) -> str:
            """
            Format a duration in seconds into a human-readable time string.

            Rounds the input to the nearest second and treats negative values as zero.
            If the value is None or not finite, returns "--:--".
            Outputs "H:MM:SS" when the duration is one hour or more, otherwise "MM:SS".

            Parameters:
                seconds (Optional[float]): Duration in seconds, or None.

            Returns:
                str: Formatted time string ("MM:SS" or "H:MM:SS"), or "--:--" for unknown/invalid input.
            """
            if seconds is None or not math.isfinite(seconds):
                return "--:--"
            total = max(0, int(seconds + 0.5))
            hours, remainder = divmod(total, 3600)
            minutes, secs = divmod(remainder, 60)
            if hours:
                return f"{hours:d}:{minutes:02d}:{secs:02d}"
            return f"{minutes:02d}:{secs:02d}"

        def _format_stats(files_done: int, bytes_done: int, elapsed: float) -> str:
            """
            Format a compact transfer progress summary string for display.

            Parameters:
                files_done (int): Number of files fully processed (unused in output but provided for context).
                bytes_done (int): Total bytes processed so far.
                elapsed (float): Elapsed time in seconds.

            Returns:
                A single-line status string containing transfer speed in MB/s, estimated time remaining, and elapsed time (formatted via `_format_duration`). If the resulting string exceeds the configured stats width, it is truncated with a trailing ellipsis.
            """
            speed_bps = bytes_done / elapsed if elapsed > 0 else 0.0
            speed_mb = speed_bps / (1024 * 1024)
            remaining_bytes = max(total_bytes - bytes_done, 0)
            eta_seconds = (remaining_bytes / speed_bps) if speed_bps > 0 else None
            eta_text = _format_duration(eta_seconds)
            elapsed_text = _format_duration(elapsed)
            stats = f"{speed_mb:5.2f} MB/s | {eta_text} | {elapsed_text}"
            if len(stats) > stats_width_limit:
                stats = stats[: max(0, stats_width_limit - 1)] + "…"
            return stats

        try:
            layout_data["slowpics"]["status"] = "uploading"
            reporter.update_values(layout_data)
            reporter.line(_color_text("[✓] slow.pics: establishing session", "green"))
            if upload_total > 0:
                start_time = time.perf_counter()
                uploaded_files = 0
                uploaded_bytes = 0
                file_index = 0
                initial_stats = _format_stats(0, 0, 0.0)
                reporter.update_progress_state(
                    "upload_bar",
                    description="slow.pics upload",
                    current=0,
                    total=upload_total,
                    stats=initial_stats,
                )
                reporter.render_sections(["publish"])
                with reporter.create_progress("upload_bar", transient=False) as upload_progress:
                    task_id = upload_progress.add_task(
                        "slow.pics upload",
                        total=upload_total,
                    )
                    progress_lock = threading.Lock()

                    def advance_upload(count: int) -> None:
                        """
                        Advance the upload progress by a given number of files and refresh the progress display.

                        Increments internal counters for uploaded files and bytes, advances the current file index for up to `count` files, computes elapsed time since the start, and updates the associated progress task with the new completed count and formatted statistics.

                        Parameters:
                            count (int): Number of files to mark as uploaded.
                        """
                        nonlocal uploaded_files, uploaded_bytes, file_index
                        with progress_lock:
                            uploaded_files += count
                            for _ in range(count):
                                if file_index < len(file_sizes):
                                    uploaded_bytes += file_sizes[file_index]
                                    file_index += 1
                            elapsed = time.perf_counter() - start_time
                            stats_text = _format_stats(uploaded_files, uploaded_bytes, elapsed)
                            completed = min(upload_total, uploaded_files)
                            reporter.update_progress_state(
                                "upload_bar",
                                current=completed,
                                total=upload_total,
                                stats=stats_text,
                            )
                            upload_progress.update(
                                task_id,
                                completed=completed,
                            )

                    slowpics_url = upload_comparison(
                        image_paths,
                        out_dir,
                        cfg.slowpics,
                        progress_callback=advance_upload,
                    )

                    elapsed = time.perf_counter() - start_time
                    final_stats = _format_stats(uploaded_files, uploaded_bytes, elapsed)
                    reporter.update_progress_state(
                        "upload_bar",
                        current=upload_total,
                        total=upload_total,
                        stats=final_stats,
                    )
                    upload_progress.update(
                        task_id,
                        completed=upload_total,
                    )
            else:
                slowpics_url = upload_comparison(
                    image_paths,
                    out_dir,
                    cfg.slowpics,
                )
            layout_data["slowpics"]["status"] = "completed"
            reporter.update_values(layout_data)
            reporter.line(_color_text(f"[✓] slow.pics: uploading {upload_total} images", "green"))
            reporter.line(_color_text("[✓] slow.pics: assembling collection", "green"))
        except SlowpicsAPIError as exc:
            layout_data["slowpics"]["status"] = "failed"
            reporter.update_values(layout_data)
            raise CLIAppError(
                f"slow.pics upload failed: {exc}",
                rich_message=f"[red]slow.pics upload failed:[/red] {exc}",
            ) from exc

    if slowpics_url:
        slowpics_block = ensure_slowpics_block(json_tail, cfg)
        slowpics_block["url"] = slowpics_url
        shortcut_path_obj: Optional[Path] = None
        shortcut_error: Optional[str] = None
        if cfg.slowpics.create_url_shortcut:
            shortcut_filename = build_shortcut_filename(
                cfg.slowpics.collection_name, slowpics_url
            )
            if shortcut_filename:
                shortcut_path_obj = out_dir / shortcut_filename
            else:
                shortcut_error = "invalid_shortcut_name"
        if shortcut_path_obj is not None:
            slowpics_block["shortcut_path"] = str(shortcut_path_obj)
            shortcut_written = shortcut_path_obj.exists()
        else:
            slowpics_block["shortcut_path"] = None
            shortcut_written = False
            if not cfg.slowpics.create_url_shortcut:
                shortcut_error = "disabled"
        if shortcut_written:
            shortcut_error = None
        elif shortcut_path_obj is not None and shortcut_error is None:
            shortcut_error = "write_failed"
        slowpics_block["shortcut_written"] = shortcut_written
        slowpics_block["shortcut_error"] = shortcut_error

    report_index_path: Optional[Path] = None
    report_defaults: ReportJSON = {
        "enabled": report_enabled,
        "path": None,
        "output_dir": cfg.report.output_dir,
        "open_after_generate": bool(getattr(cfg.report, "open_after_generate", True)),
    }
    report_block = json_tail.setdefault(
        "report",
        cast(ReportJSON, report_defaults.copy()),
    )
    report_block.update(report_defaults)
    if report_enabled:
        try:
            report_dir = preflight_utils.resolve_subdir(
                root,
                cfg.report.output_dir,
                purpose="report.output_dir",
            )
            plan_payload = [
                {
                    "label": _plan_label(plan),
                    "metadata": dict(plan.metadata),
                    "path": plan.path,
                }
                for plan in plans
            ]
            report_index_path = html_report.generate_html_report(
                report_dir=report_dir,
                report_cfg=cfg.report,
                frames=list(frames),
                selection_details=selection_details,
                image_paths=image_paths,
                plans=plan_payload,
                metadata_title=metadata_title,
                include_metadata=str(getattr(cfg.report, "include_metadata", "minimal")),
                slowpics_url=slowpics_url,
            )
        except CLIAppError as exc:
            message = f"HTML report generation failed: {exc}"
            reporter.warn(message)
            collected_warnings.append(message)
            report_block["enabled"] = False
            report_block["path"] = None
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("HTML report generation failed")
            message = f"HTML report generation failed: {exc}"
            reporter.warn(message)
            collected_warnings.append(message)
            report_block["enabled"] = False
            report_block["path"] = None
        else:
            report_block["enabled"] = True
            report_block["path"] = str(report_index_path)
    else:
        report_block["enabled"] = False
        report_block["path"] = None

    viewer_block = json_tail.get("viewer", {})
    viewer_mode = "slow_pics" if slowpics_url else "local_report" if report_block.get("enabled") and report_block.get("path") else "none"
    viewer_destination: Optional[str]
    viewer_label = ""
    if viewer_mode == "slow_pics":
        viewer_destination = slowpics_url
        viewer_label = slowpics_url or ""
    elif viewer_mode == "local_report":
        viewer_destination = report_block.get("path")
        viewer_label = viewer_destination or ""
        if viewer_destination:
            try:
                viewer_label = str(Path(viewer_destination).resolve().relative_to(root.resolve()))
            except ValueError:
                viewer_label = viewer_destination
    else:
        viewer_destination = None
    viewer_mode_display = {
        "slow_pics": "slow.pics",
        "local_report": "Local report",
        "none": "None",
    }.get(viewer_mode, viewer_mode.title())
    viewer_block.update(
        {
            "mode": viewer_mode,
            "mode_display": viewer_mode_display,
            "destination": viewer_destination,
            "destination_label": viewer_label,
        }
    )
    json_tail["viewer"] = viewer_block
    layout_data["viewer"] = viewer_block
    reporter.update_values(layout_data)
    reporter.render_sections(["at_a_glance"])

    result = RunResult(
        files=[plan.path for plan in plans],
        frames=list(frames),
        out_dir=out_dir,
        out_dir_created=created_out_dir,
        out_dir_created_path=created_out_dir_path,
        root=root,
        config=cfg,
        image_paths=list(image_paths),
        slowpics_url=slowpics_url,
        json_tail=json_tail,
        report_path=report_index_path,
    )

    raw_layout_sections = getattr(getattr(reporter, "layout", None), "sections", [])
    layout_sections: list[dict[str, object]] = []
    for raw_section in raw_layout_sections:
        if isinstance(raw_section, Mapping):
            layout_sections.append(coerce_str_mapping(cast(Mapping[str, object], raw_section)))

    summary_lines: List[str] = []
    summary_section: dict[str, object] | None = None
    for section_map in layout_sections:
        if section_map.get("id") == "summary":
            summary_section = section_map
            break
    if summary_section is not None:
        items_obj = summary_section.get("items", [])
        renderer = getattr(reporter, "renderer", None)
        render_fn = getattr(renderer, "render_template", None)
        if isinstance(items_obj, list):
            for entry in cast(list[object], items_obj):
                if not isinstance(entry, str):
                    continue
                item = entry
                if callable(render_fn):
                    rendered = render_fn(item, reporter.values, reporter.flags)
                else:
                    rendered = item
                if rendered:
                    summary_lines.append(str(rendered))

    if not summary_lines:
        summary_lines = [
            f"Files     : {len(result.files)}",
            f"Frames    : {len(result.frames)} -> {result.frames}",
            f"Output dir: {result.out_dir}",
        ]
        if result.slowpics_url:
            summary_lines.append(f"Slow.pics : {result.slowpics_url}")

    for warning in collected_warnings:
        reporter.warn(warning)

    warnings_list = list(dict.fromkeys(reporter.iter_warnings()))
    json_tail["warnings"] = warnings_list
    warnings_section: dict[str, object] | None = None
    for section_map in layout_sections:
        if section_map.get("id") == "warnings":
            warnings_section = section_map
            break
    fold_config_source = warnings_section.get("fold_labels") if warnings_section is not None else None
    if isinstance(fold_config_source, Mapping):
        fold_config = coerce_str_mapping(cast(Mapping[str, object], fold_config_source))
    else:
        fold_config = {}
    fold_head = fold_config.get("head")
    fold_tail = fold_config.get("tail")
    fold_when = fold_config.get("when")
    head = int(fold_head) if isinstance(fold_head, (int, float)) else 2
    tail = int(fold_tail) if isinstance(fold_tail, (int, float)) else 1
    joiner = str(fold_config.get("joiner", ", "))
    fold_when_text = str(fold_when) if isinstance(fold_when, str) and fold_when else None
    fold_enabled = runtime_utils.evaluate_rule_condition(fold_when_text, flags=reporter.flags)

    warnings_data: List[Dict[str, object]] = []
    if warnings_list:
        labels_text = runtime_utils.fold_sequence(warnings_list, head=head, tail=tail, joiner=joiner, enabled=fold_enabled)
        warnings_data.append(
            {
                "warning.type": "general",
                "warning.count": len(warnings_list),
                "warning.labels": labels_text,
            }
        )
    else:
        warnings_data.append(
            {
                "warning.type": "general",
                "warning.count": 0,
                "warning.labels": "none",
            }
        )

    layout_data["warnings"] = warnings_data
    reporter.update_values(layout_data)
    reporter.render_sections(["warnings"])
    reporter.render_sections(["summary"])

    has_summary_section = any(section.get("id") == "summary" for section in layout_sections)
    compatibility_required = bool(
        reporter.flags.get("compat.summary_fallback")
        or reporter.flags.get("compatibility_mode")
        or reporter.flags.get("legacy_summary_fallback")
    )

    if not reporter.quiet and (compatibility_required or not has_summary_section):
        summary_lines = runtime_utils.build_legacy_summary_lines(layout_data, emit_json_tail=emit_json_tail_flag)
        reporter.section("Summary")
        for line in summary_lines:
            reporter.line(_color_text(line, "green"))

    return result


def run_cli(
    config_path: str | None,
    input_dir: str | None = None,
    *,
    root_override: str | None = None,
    audio_track_overrides: Iterable[str] | None = None,
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False,
    report_enable_override: Optional[bool] = None,
    skip_wizard: bool = False,
    debug_color: bool = False,
    tonemap_overrides: Optional[Dict[str, Any]] = None,
    impl_module: ModuleType | None = None,
) -> RunResult:
    request = RunRequest(
        config_path=config_path,
        input_dir=input_dir,
        root_override=root_override,
        audio_track_overrides=audio_track_overrides,
        quiet=quiet,
        verbose=verbose,
        no_color=no_color,
        report_enable_override=report_enable_override,
        skip_wizard=skip_wizard,
        debug_color=debug_color,
        tonemap_overrides=tonemap_overrides,
        impl_module=impl_module,
    )
    return run(request)
