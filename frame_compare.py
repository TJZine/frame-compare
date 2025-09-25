from __future__ import annotations

import asyncio
import builtins
import logging
import re
import sys
import shutil
import webbrowser
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from string import Template
import time
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import click
from rich import print
from rich.markup import escape
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from natsort import os_sorted

from src.config_loader import ConfigError, load_config
from src.datatypes import AppConfig
from src.utils import parse_filename_metadata
from src import vs_core
from src.analysis import (
    FrameMetricsCacheInfo,
    SelectionWindowSpec,
    compute_selection_window,
    select_frames,
)
from src.screenshot import generate_screenshots, ScreenshotError
from src.slowpics import SlowpicsAPIError, upload_comparison
from src.tmdb import (
    TMDBAmbiguityError,
    TMDBCandidate,
    TMDBResolution,
    TMDBResolutionError,
    parse_manual_id,
    resolve_tmdb,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTS = (
    ".mkv",
    ".m2ts",
    ".mp4",
    ".webm",
    ".ogm",
    ".mpg",
    ".vob",
    ".iso",
    ".ts",
    ".mts",
    ".mov",
    ".qv",
    ".yuv",
    ".flv",
    ".avi",
    ".rm",
    ".rmvb",
    ".m2v",
    ".m4v",
    ".mp2",
    ".mpeg",
    ".mpe",
    ".mpv",
    ".wmv",
    ".avc",
    ".hevc",
    ".264",
    ".265",
    ".av1",
)


@dataclass
class _ClipPlan:
    path: Path
    metadata: Dict[str, str]
    trim_start: int = 0
    trim_end: Optional[int] = None
    fps_override: Optional[Tuple[int, int]] = None
    use_as_reference: bool = False
    clip: Optional[object] = None
    effective_fps: Optional[Tuple[int, int]] = None
    applied_fps: Optional[Tuple[int, int]] = None
    has_trim_start_override: bool = False
    has_trim_end_override: bool = False


@dataclass
class RunResult:
    files: List[Path]
    frames: List[int]
    out_dir: Path
    config: AppConfig
    image_paths: List[str]
    slowpics_url: Optional[str] = None


class CLIAppError(RuntimeError):
    """Raised when the CLI cannot complete its work."""

    def __init__(self, message: str, *, code: int = 1, rich_message: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.rich_message = rich_message or message


def _discover_media(root: Path) -> List[Path]:
    return [p for p in os_sorted(root.iterdir()) if p.suffix.lower() in SUPPORTED_EXTS]


def _parse_metadata(files: Sequence[Path], naming_cfg) -> List[Dict[str, str]]:
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


def _first_non_empty(metadata: Sequence[Dict[str, str]], key: str) -> str:
    for meta in metadata:
        value = meta.get(key)
        if value:
            return str(value)
    return ""


def _parse_year_hint(value: str) -> Optional[int]:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    if 1900 <= year <= 2100:
        return year
    return None


def _prompt_manual_tmdb(candidates: Sequence[TMDBCandidate]) -> tuple[str, str] | None:
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


def _render_collection_name(template_text: str, context: Mapping[str, str]) -> str:
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


def _normalise_override_mapping(raw: Mapping[str, object]) -> Dict[str, object]:
    normalised: Dict[str, object] = {}
    for key, value in raw.items():
        key_str = str(key).strip().lower()
        if key_str:
            normalised[key_str] = value
    return normalised


def _match_override(
    index: int,
    file: Path,
    metadata: Mapping[str, str],
    mapping: Mapping[str, object],
) -> Optional[object]:
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
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    if isinstance(num, int) and isinstance(den, int) and den:
        return (num, den)
    return (24000, 1001)


def _init_clips(plans: Sequence[_ClipPlan], runtime_cfg, cache_dir: Path | None) -> None:
    vs_core.set_ram_limit(runtime_cfg.ram_limit_mb)

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
        )
        plan.clip = clip
        plan.effective_fps = _extract_clip_fps(clip)
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
        )
        plan.clip = clip
        plan.applied_fps = fps_override
        plan.effective_fps = _extract_clip_fps(clip)


def _build_cache_info(root: Path, plans: Sequence[_ClipPlan], cfg: AppConfig, analyze_index: int) -> Optional[FrameMetricsCacheInfo]:
    if not cfg.analysis.save_frames_data:
        return None

    analyzed = plans[analyze_index]
    fps_num, fps_den = analyzed.effective_fps or (24000, 1001)
    if fps_den <= 0:
        fps_den = 1

    cache_path = (root / cfg.analysis.frame_data_filename).resolve()
    return FrameMetricsCacheInfo(
        path=cache_path,
        files=[plan.path.name for plan in plans],
        analyzed_file=analyzed.path.name,
        release_group=analyzed.metadata.get("release_group", ""),
        trim_start=analyzed.trim_start,
        trim_end=analyzed.trim_end,
        fps_num=fps_num,
        fps_den=fps_den,
    )


def _resolve_selection_windows(
    plans: Sequence[_ClipPlan],
    analysis_cfg,
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


def _print_trim_overrides(plans: Sequence[_ClipPlan]) -> None:
    """Print the trim overrides sourced from the configuration."""

    trimmed = [
        plan
        for plan in plans
        if plan.has_trim_start_override or plan.has_trim_end_override
    ]
    if not trimmed:
        return

    print("[cyan]Trim overrides set in config:[/cyan]")
    for plan in trimmed:
        label = (plan.metadata.get("label") or plan.path.name).strip()
        label_markup = escape(label)
        filename_markup = escape(plan.path.name)
        start_display = str(plan.trim_start) if plan.has_trim_start_override else "unchanged"
        if plan.has_trim_end_override:
            end_display = "None" if plan.trim_end is None else str(plan.trim_end)
        else:
            end_display = "unchanged"
        print(
            f"  - {label_markup} ({filename_markup}): start={start_display}, end={end_display}"
        )


def _print_summary(files: Sequence[Path], frames: Sequence[int], out_dir: Path, url: str | None) -> None:
    print("[green]Comparison ready[/green]")
    print(f"  Files     : {len(files)}")
    print(f"  Frames    : {len(frames)} -> {frames}")
    builtins.print(f"  Output dir: {out_dir}")
    if url:
        print(f"  Slow.pics : {url}")


def run_cli(config_path: str, input_dir: str | None = None) -> RunResult:
    try:
        cfg: AppConfig = load_config(config_path)
    except ConfigError as exc:
        raise CLIAppError(
            f"Config error: {exc}", code=2, rich_message=f"[red]Config error:[/red] {exc}"
        ) from exc

    if input_dir:
        cfg.paths.input_dir = input_dir

    root = Path(cfg.paths.input_dir).expanduser().resolve()
    if not root.exists():
        raise CLIAppError(
            f"Input directory not found: {root}",
            rich_message=f"[red]Input directory not found:[/red] {root}",
        )

    vs_core.configure(
        search_paths=cfg.runtime.vapoursynth_python_paths,
        source_preference=cfg.source.preferred,
    )

    try:
        files = _discover_media(root)
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

    metadata = _parse_metadata(files, cfg.naming)
    year_hint_raw = _first_non_empty(metadata, "year")
    metadata_title = _first_non_empty(metadata, "title") or _first_non_empty(metadata, "anime_title")
    tmdb_resolution: TMDBResolution | None = None
    manual_tmdb: tuple[str, str] | None = None
    tmdb_category: Optional[str] = None
    tmdb_id_value: Optional[str] = None
    tmdb_language: Optional[str] = None
    tmdb_error_message: Optional[str] = None
    tmdb_ambiguous = False
    tmdb_api_key_present = bool(cfg.tmdb.api_key.strip())

    if tmdb_api_key_present:
        base_file = files[0]
        imdb_hint = _first_non_empty(metadata, "imdb_id").lower()
        tvdb_hint = _first_non_empty(metadata, "tvdb_id")
        year_hint = _parse_year_hint(year_hint_raw)
        try:
            tmdb_resolution = asyncio.run(
                resolve_tmdb(
                    base_file.name,
                    config=cfg.tmdb,
                    year=year_hint,
                    imdb_id=imdb_hint or None,
                    tvdb_id=tvdb_hint or None,
                    unattended=cfg.tmdb.unattended,
                    category_preference=cfg.tmdb.category_preference,
                )
            )
        except TMDBAmbiguityError as exc:
            tmdb_ambiguous = True
            manual_tmdb = _prompt_manual_tmdb(exc.candidates)
        except TMDBResolutionError as exc:
            logger.warning("TMDB lookup failed for %s: %s", base_file.name, exc)
            tmdb_error_message = str(exc)
        else:
            if tmdb_resolution is not None:
                tmdb_category = tmdb_resolution.category
                tmdb_id_value = tmdb_resolution.tmdb_id
                tmdb_language = tmdb_resolution.original_language

    if manual_tmdb:
        tmdb_category, tmdb_id_value = manual_tmdb
        tmdb_language = None
        tmdb_resolution = None
        logger.info("TMDB manual override selected: %s/%s", tmdb_category, tmdb_id_value)

    tmdb_context: Dict[str, str] = {
        "Title": metadata_title or (metadata[0].get("label") if metadata else ""),
        "OriginalTitle": "",
        "Year": year_hint_raw or "",
        "TMDBId": tmdb_id_value or "",
        "TMDBCategory": tmdb_category or "",
        "OriginalLanguage": tmdb_language or "",
        "Filename": files[0].stem,
        "FileName": files[0].name,
        "Label": metadata[0].get("label") if metadata else files[0].name,
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

    collection_template = (cfg.slowpics.collection_name or "").strip()
    if collection_template:
        rendered_collection = _render_collection_name(collection_template, tmdb_context).strip()
        cfg.slowpics.collection_name = rendered_collection or "Frame Comparison"
    else:
        derived_title = (tmdb_context.get("Title") or "").strip() or files[0].stem
        derived_year = (tmdb_context.get("Year") or "").strip()
        collection_name = derived_title
        if derived_title and derived_year:
            collection_name = f"{derived_title} ({derived_year})"
        cfg.slowpics.collection_name = collection_name or "Frame Comparison"

    if tmdb_resolution is not None:
        match_title = tmdb_resolution.title or tmdb_context.get("Title") or files[0].stem
        year_text = f" ({tmdb_resolution.year})" if tmdb_resolution.year else ""
        lang_text = tmdb_resolution.original_language or "unknown"
        heuristic = (tmdb_resolution.candidate.reason or "match").replace("_", " ").replace("-", " ")
        source = "filename" if tmdb_resolution.candidate.used_filename_search else "external id"
        print(
            "[cyan]TMDB match:[/cyan] "
            f"{match_title}{year_text} "
            f"[{tmdb_resolution.category}] -> {tmdb_resolution.tmdb_id} "
            f"({source}, {heuristic.strip()}) lang={lang_text}"
        )
    elif manual_tmdb:
        display_title = tmdb_context.get("Title") or files[0].stem
        print(
            "[cyan]TMDB manual override:[/cyan] "
            f"{tmdb_category}/{tmdb_id_value} for {display_title}"
        )
    elif tmdb_api_key_present:
        if tmdb_error_message:
            print(f"[yellow]TMDB lookup failed:[/yellow] {tmdb_error_message}")
        elif tmdb_ambiguous:
            print(
                "[yellow]TMDB: ambiguous results for[/yellow] "
                f"{files[0].name}; continuing without metadata."
            )
        else:
            print(
                "[yellow]TMDB: no confident match for[/yellow] "
                f"{files[0].name}; continuing without metadata."
            )
    elif not (cfg.slowpics.tmdb_id or "").strip():
        print(
            "[yellow]TMDB disabled:[/yellow] set [tmdb].api_key in config.toml to enable automatic matching."
        )

    labels = [meta.get("label") or file.name for meta, file in zip(metadata, files)]
    print("[green]Files detected:[/green]")
    for label, file in zip(labels, files):
        print(f"  - {label} ({file.name})")

    plans = _build_plans(files, metadata, cfg)
    _print_trim_overrides(plans)
    analyze_path = _pick_analyze_file(files, metadata, cfg.analysis.analyze_clip, cache_dir=root)

    try:
        _init_clips(plans, cfg.runtime, root)
    except vs_core.ClipInitError as exc:
        raise CLIAppError(
            f"Failed to open clip: {exc}", rich_message=f"[red]Failed to open clip:[/red] {exc}"
        ) from exc

    clips = [plan.clip for plan in plans]
    if any(clip is None for clip in clips):
        raise CLIAppError("Clip initialisation failed")

    analyze_index = [plan.path for plan in plans].index(analyze_path)
    analyze_clip = plans[analyze_index].clip
    if analyze_clip is None:
        raise CLIAppError("Missing clip for analysis")

    selection_specs, frame_window, windows_collapsed = _resolve_selection_windows(
        plans, cfg.analysis
    )
    analyze_fps_num, analyze_fps_den = plans[analyze_index].effective_fps or _extract_clip_fps(
        analyze_clip
    )
    analyze_fps = analyze_fps_num / analyze_fps_den if analyze_fps_den else 0.0
    _log_selection_windows(
        plans,
        selection_specs,
        frame_window,
        collapsed=windows_collapsed,
        analyze_fps=analyze_fps,
    )

    cache_info = _build_cache_info(root, plans, cfg, analyze_index)

    step_size = max(1, int(cfg.analysis.step))
    total_frames = getattr(analyze_clip, 'num_frames', 0)
    sample_count = 0
    if isinstance(total_frames, int) and total_frames > 0:
        sample_count = (total_frames + step_size - 1) // step_size

    analyze_label_raw = plans[analyze_index].metadata.get('label') or analyze_path.name
    analyze_label = escape(analyze_label_raw.strip())
    analyze_label_colored = f"Analyzing video: [bright_cyan]{analyze_label}[/]"

    cache_exists = cache_info is not None and cache_info.path.exists()
    if cache_exists:
        print(f"[cyan]Using cached frame metrics:[/cyan] {cache_info.path.name}")
        print("[cyan]Selecting frames from cached data...[/cyan]")

    using_frame_total = isinstance(total_frames, int) and total_frames > 0
    progress_total = int(total_frames) if using_frame_total else int(sample_count)

    def _run_selection(progress_callback=None):
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
            )
        if isinstance(result, tuple):
            return result
        frames_only = list(result)
        return frames_only, {frame: "Auto" for frame in frames_only}

    try:
        if sample_count > 0 and not cache_exists:
            start_time = time.perf_counter()
            samples_done = 0

            with Progress(
                TextColumn('{task.description}'),
                BarColumn(),
                TextColumn('{task.completed}/{task.total}'),
                TextColumn('{task.percentage:>6.02f}%'),
                TextColumn('{task.fields[fps]}'),
                TimeRemainingColumn(),
                transient=False,
            ) as analysis_progress:
                task_id = analysis_progress.add_task(
                    analyze_label_colored,
                    total=max(1, progress_total),
                    fps="   0.00 fps",
                )

                def _advance_samples(count: int) -> None:
                    nonlocal samples_done
                    samples_done += count
                    if progress_total <= 0:
                        return
                    elapsed = time.perf_counter() - start_time
                    frames_processed = samples_done * step_size
                    completed = (
                        min(progress_total, frames_processed)
                        if using_frame_total
                        else min(progress_total, samples_done)
                    )
                    fps_val = 0.0
                    if elapsed > 0:
                        fps_val = frames_processed / elapsed
                    analysis_progress.update(
                        task_id,
                        completed=completed,
                        fps=f"{fps_val:7.2f} fps",
                    )

                frames, frame_categories = _run_selection(_advance_samples)
                # Ensure progress completes even if sampling stopped early
                final_completed = progress_total if progress_total > 0 else analysis_progress.tasks[task_id].completed
                analysis_progress.update(task_id, completed=final_completed)
        else:
            frames, frame_categories = _run_selection()

    except Exception as exc:
        tb = traceback.format_exc()
        print("[red]Frame selection trace:[/red]")
        print(tb)
        raise CLIAppError(
            f"Frame selection failed: {exc}",
            rich_message=f"[red]Frame selection failed:[/red] {exc}",
        ) from exc

    if not frames:
        raise CLIAppError(
            "No frames were selected; cannot continue.",
            rich_message="[red]No frames were selected; cannot continue.[/red]",
        )

    out_dir = (root / cfg.screenshots.directory_name).resolve()
    total_screens = len(frames) * len(plans)
    print("[cyan]Preparing screenshot rendering...[/cyan]")
    try:
        if total_screens > 0:
            start_time = time.perf_counter()
            processed = 0

            with Progress(
                TextColumn('{task.description}'),
                BarColumn(),
                TextColumn('{task.completed}/{task.total}'),
                TextColumn('{task.percentage:>6.02f}%'),
                TextColumn('{task.fields[rate]}'),
                TimeRemainingColumn(),
                transient=False,
            ) as render_progress:
                task_id = render_progress.add_task(
                    'Generating screenshots',
                    total=total_screens,
                    rate="   0.00 fps",
                )

                def advance_render(count: int) -> None:
                    nonlocal processed
                    processed += count
                    elapsed = time.perf_counter() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0.0
                    render_progress.update(
                        task_id,
                        completed=min(total_screens, processed),
                        rate=f"{rate:7.2f} fps",
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
                )

                if processed < total_screens:
                    render_progress.update(
                        task_id,
                        completed=total_screens,
                        rate=f"{(processed / max(1e-6, time.perf_counter() - start_time)):7.2f} fps",
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
            )
    except ScreenshotError as exc:
        raise CLIAppError(
            f"Screenshot generation failed: {exc}",
            rich_message=f"[red]Screenshot generation failed:[/red] {exc}",
        ) from exc

    slowpics_url: Optional[str] = None
    if cfg.slowpics.auto_upload:
        print("[cyan]Preparing slow.pics upload...[/cyan]")
        upload_total = len(image_paths)
        try:
            if upload_total > 0:
                start_time = time.perf_counter()
                uploaded = 0

                with Progress(
                    TextColumn('{task.description}'),
                    BarColumn(),
                    TextColumn('{task.completed}/{task.total}'),
                    TextColumn('{task.percentage:>6.02f}%'),
                    TextColumn('{task.fields[rate]}'),
                    TimeRemainingColumn(),
                    transient=False,
                ) as upload_progress:
                    task_id = upload_progress.add_task(
                        'Uploading to slow.pics',
                        total=upload_total,
                        rate="   0.00 fps",
                    )

                    def advance_upload(count: int) -> None:
                        nonlocal uploaded
                        uploaded += count
                        elapsed = time.perf_counter() - start_time
                        rate = uploaded / elapsed if elapsed > 0 else 0.0
                        upload_progress.update(
                            task_id,
                            completed=min(upload_total, uploaded),
                            rate=f"{rate:7.2f} fps",
                        )

                    slowpics_url = upload_comparison(
                        image_paths,
                        out_dir,
                        cfg.slowpics,
                        progress_callback=advance_upload,
                    )

                    if uploaded < upload_total:
                        upload_progress.update(
                            task_id,
                            completed=upload_total,
                            rate=f"{(uploaded / max(1e-6, time.perf_counter() - start_time)):7.2f} fps",
                        )
            else:
                slowpics_url = upload_comparison(
                    image_paths,
                    out_dir,
                    cfg.slowpics,
                )
        except SlowpicsAPIError as exc:
            raise CLIAppError(
                f"slow.pics upload failed: {exc}",
                rich_message=f"[red]slow.pics upload failed:[/red] {exc}",
            ) from exc

    result = RunResult(
        files=[plan.path for plan in plans],
        frames=list(frames),
        out_dir=out_dir,
        config=cfg,
        image_paths=list(image_paths),
        slowpics_url=slowpics_url,
    )
    _print_summary(result.files, result.frames, result.out_dir, result.slowpics_url)
    return result


@click.command()
@click.option("--config", "config_path", default="config.toml", show_default=True, help="Path to config.toml")
@click.option("--input", "input_dir", default=None, help="Override [paths.input_dir] from config.toml")
def main(config_path: str, input_dir: str | None) -> None:
    try:
        result = run_cli(config_path, input_dir)
    except CLIAppError as exc:
        print(exc.rich_message)
        raise click.exceptions.Exit(exc.code) from exc

    slowpics_url = result.slowpics_url
    cfg = result.config
    out_dir = result.out_dir

    if slowpics_url:
        if cfg.slowpics.open_in_browser:
            try:
                webbrowser.open(slowpics_url)
            except Exception:
                print("[yellow]Warning:[/yellow] Unable to open browser for slow.pics URL")
        try:
            import pyperclip  # type: ignore

            pyperclip.copy(slowpics_url)
        except Exception:
            pass
        if cfg.slowpics.delete_screen_dir_after_upload:
            try:
                shutil.rmtree(out_dir)
                print("[yellow]Screenshot directory removed:[/yellow]")
                builtins.print(f"  {out_dir}")
            except OSError as exc:
                print(f"[yellow]Warning:[/yellow] Failed to delete screenshot directory: {exc}")


if __name__ == "__main__":
    main()
