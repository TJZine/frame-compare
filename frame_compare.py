from __future__ import annotations

import asyncio
import builtins
import json
import logging
import math
import random
import re
import shutil
import sys
import time
import traceback
import webbrowser
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import datetime as _dt
from pathlib import Path
from string import Template
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import click
from rich import print
from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from natsort import os_sorted

from src.config_loader import ConfigError, load_config
from src.datatypes import AppConfig
from src import audio_alignment
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
from src.cli_layout import CliLayoutRenderer, CliLayoutError, load_cli_layout

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


def _color_text(text: str, style: Optional[str]) -> str:
    if style:
        return f"[{style}]{text}[/]"
    return text


def _format_kv(
    label: str,
    value: object,
    *,
    label_style: Optional[str] = "dim",
    value_style: Optional[str] = "bright_white",
    sep: str = "=",
) -> str:
    label_text = escape(str(label))
    value_text = escape(str(value))
    return f"{_color_text(label_text, label_style)}{sep}{_color_text(value_text, value_style)}"


def _format_bool(
    label: str,
    flag: bool,
    *,
    label_style: Optional[str] = "dim",
    true_style: Optional[str] = "green",
    false_style: Optional[str] = "red",
    sep: str = "=",
) -> str:
    value_style = true_style if flag else false_style
    value_text = "true" if flag else "false"
    return _format_kv(label, value_text, label_style=label_style, value_style=value_style, sep=sep)


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
    source_fps: Optional[Tuple[int, int]] = None
    source_num_frames: Optional[int] = None
    source_width: Optional[int] = None
    source_height: Optional[int] = None
    has_trim_start_override: bool = False
    has_trim_end_override: bool = False
    alignment_frames: int = 0
    alignment_status: str = ""


@dataclass
class RunResult:
    files: List[Path]
    frames: List[int]
    out_dir: Path
    config: AppConfig
    image_paths: List[str]
    slowpics_url: Optional[str] = None
    json_tail: Dict[str, object] | None = None


@dataclass
class _AudioAlignmentSummary:
    offsets_path: Path
    reference_name: str
    measurements: Sequence[audio_alignment.AlignmentMeasurement]
    applied_frames: Dict[str, int]
    baseline_shift: int
    statuses: Dict[str, str]
    reference_plan: _ClipPlan
    final_adjustments: Dict[str, int]
    swap_details: Dict[str, str]


@dataclass
class _AudioAlignmentDisplayData:
    stream_lines: List[str]
    estimation_line: Optional[str]
    offset_lines: List[str]
    offsets_file_line: str
    json_reference_stream: Optional[str]
    json_target_streams: Dict[str, str]
    json_offsets_sec: Dict[str, float]
    json_offsets_frames: Dict[str, int]
    warnings: List[str]
    preview_paths: List[str] = field(default_factory=list)
    confirmation: Optional[str] = None
    correlations: Dict[str, float] = field(default_factory=dict)
    threshold: float = 0.0


class CliOutputManager:
    """Layout-driven CLI presentation controller."""

    def __init__(
        self,
        *,
        quiet: bool,
        verbose: bool,
        no_color: bool,
        layout_path: Path,
        console: Console | None = None,
    ) -> None:
        self.quiet = quiet
        self.verbose = verbose and not quiet
        self.no_color = no_color
        self.console = console or Console(no_color=no_color, highlight=False)
        try:
            self.layout = load_cli_layout(layout_path)
        except CliLayoutError as exc:
            raise CLIAppError(str(exc)) from exc
        self.renderer = CliLayoutRenderer(
            self.layout,
            self.console,
            quiet=quiet,
            verbose=self.verbose,
            no_color=no_color,
        )
        self.flags: Dict[str, Any] = {
            "quiet": quiet,
            "verbose": self.verbose,
            "no_color": no_color,
        }
        self.values: Dict[str, Any] = {
            "theme": {
                "colors": dict(self.layout.theme.colors),
                "symbols": dict(self.renderer.symbols),
            }
        }
        self._warnings: List[str] = []

    def set_flag(self, key: str, value: Any) -> None:
        self.flags[key] = value

    def update_values(self, mapping: Mapping[str, Any]) -> None:
        self.values.update(mapping)

    def warn(self, text: str) -> None:
        self._warnings.append(text)

    def get_warnings(self) -> List[str]:
        return list(self._warnings)

    def render_sections(self, section_ids: Iterable[str]) -> None:
        target_ids = set(section_ids)
        self.renderer.bind_context(self.values, self.flags)
        for section in self.layout.sections:
            section_id = section.get("id")
            if section_id in target_ids:
                self.renderer.render_section(section, self.values, self.flags)

    def create_progress(self, progress_id: str, *, transient: bool = False) -> Progress:
        self.renderer.bind_context(self.values, self.flags)
        return self.renderer.create_progress(progress_id, transient=transient)

    def update_progress_state(self, progress_id: str, **state: Any) -> None:
        self.renderer.update_progress_state(progress_id, state=state)

    # ------------------------------------------------------------------
    # Backwards-compatible helpers (to be removed once layout integration
    # is complete).
    # ------------------------------------------------------------------

    def banner(self, text: str) -> None:
        if self.quiet:
            self.console.print(text)
            return
        self.console.print(f"[bold bright_cyan]{escape(text)}[/]")

    def section(self, title: str) -> None:
        if self.quiet:
            return
        self.console.print(f"[bold cyan]{title}[/]")

    def line(self, text: str) -> None:
        if self.quiet:
            return
        self.console.print(text)

    def verbose_line(self, text: str) -> None:
        if self.quiet or not self.verbose:
            return
        if not text:
            return
        self.console.print(f"[dim]{escape(text)}[/]")

    def progress(self, *columns, transient: bool = False) -> Progress:
        return Progress(*columns, console=self.console, transient=transient)

    def iter_warnings(self) -> List[str]:
        return list(self._warnings)


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


def _parse_audio_track_overrides(entries: Iterable[str]) -> Dict[str, int]:
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


def _prompt_tmdb_confirmation(
    resolution: TMDBResolution,
) -> tuple[bool, tuple[str, str] | None]:
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


def _format_seconds(value: float) -> str:
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


def _build_legacy_summary_lines(values: Mapping[str, Any]) -> List[str]:
    """Compose legacy summary lines from the collected layout values."""

    def _maybe_number(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_number(value: Any, fmt: str, fallback: str) -> str:
        number = _maybe_number(value)
        if number is None:
            return fallback
        return format(number, fmt)

    def _string(value: Any, fallback: str = "n/a") -> str:
        if value is None:
            return fallback
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _bool_text(value: Any) -> str:
        return "true" if bool(value) else "false"

    clips_raw = values.get("clips")
    clips = clips_raw if isinstance(clips_raw, Mapping) else {}
    window_raw = values.get("window")
    window = window_raw if isinstance(window_raw, Mapping) else {}
    analysis_raw = values.get("analysis")
    analysis = analysis_raw if isinstance(analysis_raw, Mapping) else {}
    counts_raw = analysis.get("counts") if isinstance(analysis, Mapping) else {}
    counts = counts_raw if isinstance(counts_raw, Mapping) else {}
    audio_raw = values.get("audio_alignment")
    audio = audio_raw if isinstance(audio_raw, Mapping) else {}
    render_raw = values.get("render")
    render = render_raw if isinstance(render_raw, Mapping) else {}
    tonemap_raw = values.get("tonemap")
    tonemap = tonemap_raw if isinstance(tonemap_raw, Mapping) else {}
    cache_raw = values.get("cache")
    cache = cache_raw if isinstance(cache_raw, Mapping) else {}

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

    lines.append(
        "Tonemap: "
        f"{_string(tonemap.get('tone_curve'), 'n/a')}@"
        f"{_format_number(tonemap.get('target_nits'), '.0f', '0')}nits "
        f"dpd={_bool_text(tonemap.get('dynamic_peak_detection'))}  "
        f"verify≤{_format_number(tonemap.get('verify_luma_threshold'), '.2f', '0.00')}"
    )

    lines.append(
        f"Output: {_string(render.get('out_dir'), 'n/a')}  compression={_string(render.get('compression'), 'n/a')}"
    )

    lines.append(f"Cache: {_string(cache.get('file'), 'n/a')}  {_string(cache.get('status'), 'unknown')}")

    frame_count = _string(analysis.get("output_frame_count"), "0")
    preview = _string(analysis.get("output_frames_preview"), "")
    preview_display = f"[{preview}]" if preview else "[]"
    lines.append(
        f"Output frames: {frame_count}  e.g., {preview_display}  (full list in JSON)"
    )

    return [line for line in lines if line]


def _format_clock(seconds: Optional[float]) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "--:--"
    total = max(0, int(seconds + 0.5))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


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
        )
        plan.clip = clip
        plan.applied_fps = fps_override
        plan.effective_fps = _extract_clip_fps(clip)
        plan.source_fps = plan.effective_fps
        plan.source_num_frames = int(getattr(clip, "num_frames", 0) or 0)
        plan.source_width = int(getattr(clip, "width", 0) or 0)
        plan.source_height = int(getattr(clip, "height", 0) or 0)


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


def _resolve_alignment_reference(
    plans: Sequence[_ClipPlan],
    analyze_path: Path,
    reference_hint: str,
) -> _ClipPlan:
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
    reporter: CliOutputManager | None = None,
) -> tuple[_AudioAlignmentSummary | None, _AudioAlignmentDisplayData | None]:
    audio_cfg = cfg.audio_alignment
    offsets_path = (root / audio_cfg.offsets_filename).resolve()
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

    if not audio_cfg.enable:
        return None, display_data
    if len(plans) < 2:
        _warn("Audio alignment skipped: need at least two clips.")
        return None, display_data

    reference_plan = _resolve_alignment_reference(plans, analyze_path, audio_cfg.reference)
    targets = [plan for plan in plans if plan is not reference_plan]
    if not targets:
        _warn("Audio alignment skipped: no secondary clips to compare.")
        return None, display_data

    plan_labels: Dict[Path, str] = {
        plan.path: (plan.metadata.get("label") or plan.path.name).strip() or plan.path.name
        for plan in plans
    }
    name_to_label: Dict[str, str] = {plan.path.name: plan_labels[plan.path] for plan in plans}

    stream_infos: Dict[Path, List[audio_alignment.AudioStreamInfo]] = {}
    for plan in plans:
        try:
            infos = audio_alignment.probe_audio_streams(plan.path)
        except audio_alignment.AudioAlignmentError as exc:
            logger.warning("ffprobe audio stream probe failed for %s: %s", plan.path.name, exc)
            infos = []
        stream_infos[plan.path] = infos

    forced_streams: set[Path] = set()

    def _match_audio_override(plan: _ClipPlan) -> Optional[int]:
        value = _match_override(plans.index(plan), plan.path, plan.metadata, audio_track_overrides)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _pick_default(streams: Sequence[audio_alignment.AudioStreamInfo]) -> int:
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

    def _score_candidate(candidate: audio_alignment.AudioStreamInfo) -> float:
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

    for idx, target in enumerate(targets):
        stream_idx = target_stream_indices.get(target.path, 0)
        target_stream_text, target_descriptor = _describe_stream(target, stream_idx)
        display_data.json_target_streams[plan_labels[target.path]] = target_descriptor
        if idx == 0:
            display_data.stream_lines.append(
                f"Audio streams: ref={reference_stream_text}  target={target_stream_text}"
            )
        else:
            display_data.stream_lines.append(f"Audio streams: target={target_stream_text}")

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
        _, existing_entries = audio_alignment.load_offsets(offsets_path)
    except audio_alignment.AudioAlignmentError as exc:
        raise CLIAppError(
            f"Failed to read audio offsets file: {exc}",
            rich_message=f"[red]Failed to read audio offsets file:[/red] {exc}",
        ) from exc

    try:
        base_start = float(audio_cfg.start_seconds or 0.0)
        base_duration_param: Optional[float]
        if audio_cfg.duration_seconds is None:
            base_duration_param = None
        else:
            base_duration_param = float(audio_cfg.duration_seconds)
        hop_length = max(1, min(audio_cfg.hop_length, max(1, audio_cfg.sample_rate // 100)))

        measurements: List[audio_alignment.AlignmentMeasurement]
        negative_offsets: Dict[str, bool] = {}

        progress_columns = (
            TextColumn('{task.description}'),
            BarColumn(),
            TextColumn('{task.completed}/{task.total}'),
            TextColumn('{task.percentage:>6.02f}%'),
            TextColumn('{task.fields[rate]}'),
            TimeRemainingColumn(),
        )
        progress_manager = (
            reporter.progress(*progress_columns, transient=False)
            if reporter is not None
            else Progress(*progress_columns, transient=False)
        )
        with progress_manager as audio_progress:
            task_id = audio_progress.add_task(
                'Estimating audio offsets',
                total=len(targets),
                rate='   0.00 pairs/s',
            )
            processed = 0
            start_time = time.perf_counter()

            def _advance_audio(count: int) -> None:
                nonlocal processed
                processed += count
                elapsed = time.perf_counter() - start_time
                rate_val = processed / elapsed if elapsed > 0 else 0.0
                audio_progress.update(
                    task_id,
                    completed=min(processed, len(targets)),
                    rate=f"{rate_val:7.2f} pairs/s",
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

            if processed < len(targets):
                elapsed = time.perf_counter() - start_time
                final_rate = processed / elapsed if elapsed > 0 else 0.0
                audio_progress.update(
                    task_id,
                    completed=len(targets),
                    rate=f"{final_rate:7.2f} pairs/s",
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

        negative_override_notes: Dict[str, str] = {}
        swap_details: Dict[str, str] = {}
        swap_candidates: List[audio_alignment.AlignmentMeasurement] = []
        swap_enabled = len(targets) == 1

        for measurement in measurements:
            if measurement.frames is not None and measurement.frames < 0:
                if swap_enabled:
                    swap_candidates.append(measurement)
                    continue
                measurement.frames = abs(int(measurement.frames))
                negative_offsets[measurement.file.name] = True
                negative_override_notes[measurement.key] = (
                    "Suggested negative offset applied to the opposite clip for trim-first behaviour."
                )

        if swap_enabled and swap_candidates:
            additional_measurements: List[audio_alignment.AlignmentMeasurement] = []
            reference_name = reference_plan.path.name
            existing_keys = {m.file.name for m in measurements}

            for measurement in swap_candidates:
                seconds = float(measurement.offset_seconds)
                seconds_abs = abs(seconds)
                target_name = measurement.file.name

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
                negative_offsets.pop(measurement.file.name, None)
                label = name_to_label.get(measurement.file.name, measurement.file.name)
                raw_warning_messages.append(f"{label}: {measurement.error}")

        for warning_message in dict.fromkeys(raw_warning_messages):
            _warn(warning_message)

        offset_lines: List[str] = []
        offsets_sec: Dict[str, float] = {}
        offsets_frames: Dict[str, int] = {}

        for measurement in measurements:
            clip_name = measurement.file.name
            if clip_name == reference_plan.path.name and len(measurements) > 1:
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

        applied_frames, statuses = audio_alignment.update_offsets_file(
            offsets_path,
            reference_plan.path.name,
            measurements,
            existing_entries,
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
        )
        return summary, display_data
    except audio_alignment.AudioAlignmentError as exc:
        raise CLIAppError(
            f"Audio alignment failed: {exc}",
            rich_message=f"[red]Audio alignment failed:[/red] {exc}",
        ) from exc

def _print_alignment_summary(summary: _AudioAlignmentSummary, plans: Sequence[_ClipPlan]) -> None:
    print("[cyan]Audio alignment summary:[/cyan]")
    ref_label = escape(summary.reference_name)
    if summary.baseline_shift:
        print(
            f"  Reference {ref_label}: trimmed +{summary.baseline_shift} frame(s) for baseline alignment"
        )
    else:
        print(f"  Reference {ref_label}: no trim applied")

    plan_map = {plan.path.name: plan for plan in plans}

    for measurement in summary.measurements:
        name = measurement.file.name
        plan = plan_map.get(name)
        status = summary.statuses.get(name, "skipped")
        applied = summary.applied_frames.get(name)
        corr = f"{measurement.correlation:.2f}" if not math.isnan(measurement.correlation) else "nan"
        if plan is None:
            continue
        if applied is None:
            note = measurement.error or "no offset applied"
            print(f"  - {escape(name)}: skipped ({escape(note)})")
            continue
        adjustment = summary.final_adjustments.get(name, 0)
        seconds = measurement.target_fps and applied / measurement.target_fps if measurement.target_fps else None
        seconds_text = f" ({applied / measurement.target_fps:.3f}s)" if seconds is not None else ""
        print(
            f"  - {escape(name)}: {status} trim +{adjustment} frame(s) [correlation={corr}]{seconds_text}"
        )
        detail = summary.swap_details.get(name)
        if detail:
            print(f"      note: {escape(detail)}")

    print(
        f"  Offsets file: {summary.offsets_path}"
    )


def _pick_preview_frames(clip: object, count: int, seed: int) -> List[int]:
    total = getattr(clip, "num_frames", 0)
    if not isinstance(total, int) or total <= 0:
        return [i for i in range(count)]
    if total <= count:
        return list(range(total))
    step = max(total // (count + 1), 1)
    frames = [min(total - 1, step * (idx + 1)) for idx in range(count)]
    deduped = sorted(set(frames))
    while len(deduped) < count:
        next_frame = min(total - 1, deduped[-1] + 1 if deduped else 0)
        if next_frame not in deduped:
            deduped.append(next_frame)
        else:
            break
    return deduped[:count]


def _sample_random_frames(clip: object, count: int, seed: int, exclude: Sequence[int]) -> List[int]:
    total = getattr(clip, "num_frames", 0)
    if not isinstance(total, int) or total <= 0:
        return [i for i in range(count)]
    exclude_set = set(exclude)
    available = [idx for idx in range(total) if idx not in exclude_set]
    if not available:
        return list(range(min(count, total)))
    rng = random.Random(seed)
    if len(available) <= count:
        return sorted(available)
    return sorted(rng.sample(available, count))



def _confirm_alignment_with_screenshots(
    plans: Sequence[_ClipPlan],
    summary: _AudioAlignmentSummary | None,
    cfg: AppConfig,
    root: Path,
    reporter: CliOutputManager,
    display: _AudioAlignmentDisplayData | None,
) -> None:
    if summary is None or display is None:
        return
    if not cfg.audio_alignment.confirm_with_screenshots:
        display.confirmation = display.confirmation or "auto"
        return

    clips = [plan.clip for plan in plans]
    if any(clip is None for clip in clips):
        display.confirmation = display.confirmation or "auto"
        return

    reference_clip = summary.reference_plan.clip
    if reference_clip is None:
        display.confirmation = display.confirmation or "auto"
        return

    timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base_dir = Path(cfg.screenshots.directory_name)
    metadata = summary.reference_plan.metadata
    name_candidates = [
        metadata.get("label"),
        metadata.get("title"),
        metadata.get("anime_title"),
        metadata.get("file_name"),
        summary.reference_name,
        summary.reference_plan.path.stem,
    ]
    base_name = next((str(value).strip() for value in name_candidates if value and str(value).strip()), "clip")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name).strip("._-") or "clip"
    preview_folder = f"{safe_name}-{timestamp}"
    preview_dir = (root / base_dir / "audio_alignment" / preview_folder).resolve()

    initial_frames = _pick_preview_frames(reference_clip, 2, cfg.audio_alignment.random_seed)

    try:
        generated = generate_screenshots(
            clips,
            initial_frames,
            [str(plan.path) for plan in plans],
            [plan.metadata for plan in plans],
            preview_dir,
            cfg.screenshots,
            cfg.color,
            trim_offsets=[plan.trim_start for plan in plans],
        )
    except ScreenshotError as exc:
        raise CLIAppError(
            f"Alignment preview failed: {exc}",
            rich_message=f"[red]Alignment preview failed:[/red] {exc}",
        ) from exc

        preview_paths = [str(path) for path in generated]
        display.preview_paths = preview_paths
        if preview_paths:
            reporter.line(f"Preview saved: {', '.join(preview_paths)}")

    reporter.line("Awaiting alignment confirmation. (press y/n)")

    if not sys.stdin.isatty():  # pragma: no cover - runtime-dependent
        display.confirmation = "auto"
        reporter.line("confirm=auto")
        display.warnings.append("[AUDIO] Audio alignment confirmation skipped (non-interactive session).")
        return

    if click.confirm(
        "Do the preview frames look aligned?",
        default=True,
        show_default=True,
    ):
        display.confirmation = "yes"
        reporter.line("confirm=yes")
        return

    display.confirmation = "no"
    reporter.line("confirm=no")

    inspection_dir = preview_dir / "inspection"
    extra_frames = _sample_random_frames(
        reference_clip,
        5,
        cfg.audio_alignment.random_seed + 1,
        exclude=initial_frames,
    )
    try:
        extra_paths = generate_screenshots(
            clips,
            extra_frames,
            [str(plan.path) for plan in plans],
            [plan.metadata for plan in plans],
            inspection_dir,
            cfg.screenshots,
            cfg.color,
            trim_offsets=[plan.trim_start for plan in plans],
        )
    except ScreenshotError as exc:
        raise CLIAppError(
            f"Alignment inspection failed: {exc}",
            rich_message=f"[red]Alignment inspection failed:[/red] {exc}",
        ) from exc

        if extra_paths:
            reporter.line(
                f"Additional inspection frames saved: {', '.join(str(path) for path in extra_paths)}"
            )

    reporter.console.print(
        "[yellow]Audio alignment not confirmed.[/yellow] Adjust the offsets in the generated file and rerun."
    )
    try:
        click.launch(str(summary.offsets_path))
    except Exception:
        reporter.console.print(f"[yellow]Open and edit:[/yellow] {summary.offsets_path}")

    raise CLIAppError(
        "Audio alignment requires manual adjustment.",
        rich_message=(
            "[red]Audio alignment requires manual adjustment.[/red] "
            f"Edit {summary.offsets_path} and rerun."
        ),
    )

def _print_summary(files: Sequence[Path], frames: Sequence[int], out_dir: Path, url: str | None) -> None:
    print("[green]Comparison ready[/green]")
    print(f"  Files     : {len(files)}")
    print(f"  Frames    : {len(frames)} -> {frames}")
    builtins.print(f"  Output dir: {out_dir}")
    if url:
        print(f"  Slow.pics : {url}")


def run_cli(
    config_path: str,
    input_dir: str | None = None,
    *,
    audio_track_overrides: Iterable[str] | None = None,
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False,
) -> RunResult:
    config_location = Path(config_path).expanduser()

    try:
        cfg: AppConfig = load_config(str(config_location))
    except FileNotFoundError as exc:
        message = f"Config file not found: {config_location}"
        raise CLIAppError(
            message,
            code=2,
            rich_message=f"[red]Config file not found:[/red] {config_location}",
        ) from exc
    except PermissionError as exc:
        message = f"Config file is not readable: {config_location}"
        raise CLIAppError(
            message,
            code=2,
            rich_message=f"[red]Config file is not readable:[/red] {config_location}",
        ) from exc
    except OSError as exc:
        message = f"Failed to read config file: {exc}"
        raise CLIAppError(
            message,
            code=2,
            rich_message=f"[red]Failed to read config file:[/red] {exc}",
        ) from exc
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

    layout_path = Path(__file__).with_name("cli_layout.v1.json")
    reporter = CliOutputManager(
        quiet=quiet,
        verbose=verbose,
        no_color=no_color,
        layout_path=layout_path,
    )
    collected_warnings: List[str] = []
    json_tail: Dict[str, object] = {
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
            "offsets_filename": str((root / cfg.audio_alignment.offsets_filename).resolve()),
        },
        "analysis": {},
        "render": {},
        "tonemap": {},
        "cache": {},
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
            "deleted_screens_dir": False,
            "is_public": bool(cfg.slowpics.is_public),
            "is_hentai": bool(cfg.slowpics.is_hentai),
            "remove_after_days": int(cfg.slowpics.remove_after_days),
        },
        "warnings": [],
    }

    audio_track_override_map = _parse_audio_track_overrides(audio_track_overrides or [])

    layout_data: Dict[str, Any] = {
        "clips": {
            "count": 0,
            "items": [],
            "ref": {},
            "tgt": {},
        },
        "trims": {},
        "window": json_tail["window"],
        "alignment": json_tail["alignment"],
        "audio_alignment": json_tail["audio_alignment"],
        "analysis": json_tail["analysis"],
        "render": json_tail.get("render", {}),
        "tonemap": json_tail.get("tonemap", {}),
        "overlay": json_tail.get("overlay", {}),
        "cache": json_tail["cache"],
        "slowpics": json_tail["slowpics"],
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
    tmdb_line: Optional[str] = None
    tmdb_colored_line: Optional[str] = None
    tmdb_notes: List[str] = []
    slowpics_tmdb_disclosure_line: Optional[str] = None
    slowpics_verbose_tmdb_tag: Optional[str] = None

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
                if cfg.tmdb.confirm_matches and not cfg.tmdb.unattended:
                    accepted, override = _prompt_tmdb_confirmation(tmdb_resolution)
                    if override:
                        manual_tmdb = override
                        tmdb_resolution = None
                    elif not accepted:
                        tmdb_resolution = None
                    else:
                        tmdb_category = tmdb_resolution.category
                        tmdb_id_value = tmdb_resolution.tmdb_id
                        tmdb_language = tmdb_resolution.original_language
                else:
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
        rendered_collection = _render_collection_name(collection_template, tmdb_context).strip()
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
    slowpics_title_inputs = {
        "resolved_base": slowpics_resolved_base,
        "collection_name": cfg.slowpics.collection_name,
        "collection_suffix": suffix_literal,
    }
    slowpics_inputs_json = json_tail["slowpics"]["title"]["inputs"]
    slowpics_inputs_json["resolved_base"] = slowpics_title_inputs["resolved_base"]
    slowpics_inputs_json["collection_name"] = slowpics_title_inputs["collection_name"]
    slowpics_inputs_json["collection_suffix"] = slowpics_title_inputs["collection_suffix"]
    json_tail["slowpics"]["title"]["final"] = slowpics_final_title

    if tmdb_resolution is not None:
        match_title = tmdb_resolution.title or tmdb_context.get("Title") or files[0].stem
        year_display = tmdb_context.get("Year") or ""
        lang_text = tmdb_resolution.original_language or "und"
        tmdb_identifier = f"{tmdb_resolution.category}/{tmdb_resolution.tmdb_id}"
        tmdb_line = (
            f"TMDB: {tmdb_identifier}  "
            f"\"{match_title} ({year_display})\"  lang={lang_text}"
        )
        title_segment = _color_text(escape(f'"{match_title} ({year_display})"'), "bright_white")
        lang_segment = _format_kv("lang", lang_text, label_style="dim cyan", value_style="blue")
        tmdb_colored_line = "  ".join(
            [
                _format_kv("TMDB", tmdb_identifier, label_style="cyan", value_style="bright_white"),
                title_segment,
                lang_segment,
            ]
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
        slowpics_tmdb_disclosure_line = (
            f'slow.pics title inputs: base="{escape(str(base_display))}"  '
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
        tmdb_line = (
            f"TMDB: {category_display}/{id_display}  "
            f"\"{display_title} ({tmdb_context.get('Year') or ''})\"  lang={lang_text}"
        )
        identifier = f"{category_display}/{id_display}".strip("/")
        title_segment = _color_text(
            escape(f'"{display_title} ({tmdb_context.get("Year") or ""})"'),
            "bright_white",
        )
        lang_segment = _format_kv("lang", lang_text, label_style="dim cyan", value_style="blue")
        tmdb_colored_line = "  ".join(
            [
                _format_kv("TMDB", identifier, label_style="cyan", value_style="bright_white"),
                title_segment,
                lang_segment,
            ]
        )
        if slowpics_resolved_base:
            base_display = slowpics_resolved_base
        else:
            year_component = tmdb_context.get("Year") or ""
            if display_title and year_component:
                base_display = f"{display_title} ({year_component})"
            else:
                base_display = display_title or "(n/a)"
        slowpics_tmdb_disclosure_line = (
            f'slow.pics title inputs: base="{escape(str(base_display))}"  '
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
            message = f"TMDB lookup failed: {tmdb_error_message}"
            tmdb_notes.append(message)
            collected_warnings.append(message)
        elif tmdb_ambiguous:
            message = f"TMDB ambiguous results for {files[0].name}; continuing without metadata."
            tmdb_notes.append(message)
            collected_warnings.append(message)
        else:
            message = f"TMDB could not find a confident match for {files[0].name}."
            tmdb_notes.append(message)
            collected_warnings.append(message)
    elif not (cfg.slowpics.tmdb_id or "").strip():
        message = "TMDB disabled: set [tmdb].api_key in config.toml to enable automatic matching."
        tmdb_notes.append(message)
        collected_warnings.append(message)

    plans = _build_plans(files, metadata, cfg)
    analyze_path = _pick_analyze_file(files, metadata, cfg.analysis.analyze_clip, cache_dir=root)

    alignment_summary, alignment_display = _maybe_apply_audio_alignment(
        plans,
        cfg,
        analyze_path,
        root,
        audio_track_override_map,
        reporter=reporter,
    )
    audio_offsets_applied = alignment_summary is not None
    if alignment_display is not None:
        json_tail["audio_alignment"]["offsets_filename"] = alignment_display.offsets_file_line.split(": ", 1)[-1]
        json_tail["audio_alignment"]["reference_stream"] = alignment_display.json_reference_stream
        json_tail["audio_alignment"]["target_stream"] = alignment_display.json_target_streams
        json_tail["audio_alignment"]["offsets_sec"] = alignment_display.json_offsets_sec
        json_tail["audio_alignment"]["offsets_frames"] = alignment_display.json_offsets_frames
        if alignment_display.warnings:
            collected_warnings.extend(alignment_display.warnings)
    else:
        json_tail["audio_alignment"]["reference_stream"] = None
        json_tail["audio_alignment"]["target_stream"] = {}
        json_tail["audio_alignment"]["offsets_sec"] = {}
        json_tail["audio_alignment"]["offsets_frames"] = {}
    json_tail["audio_alignment"]["enabled"] = bool(cfg.audio_alignment.enable)

    try:
        _init_clips(plans, cfg.runtime, root)
    except vs_core.ClipInitError as exc:
        raise CLIAppError(
            f"Failed to open clip: {exc}", rich_message=f"[red]Failed to open clip:[/red] {exc}"
        ) from exc

    clips = [plan.clip for plan in plans]
    if any(clip is None for clip in clips):
        raise CLIAppError("Clip initialisation failed")

    clip_records: List[Dict[str, object]] = []
    trim_details: List[Dict[str, object]] = []
    for plan in plans:
        label = (plan.metadata.get("label") or plan.path.name).strip()
        frames_total = int(plan.source_num_frames or getattr(plan.clip, "num_frames", 0) or 0)
        width = int(plan.source_width or getattr(plan.clip, "width", 0) or 0)
        height = int(plan.source_height or getattr(plan.clip, "height", 0) or 0)
        fps_tuple = plan.effective_fps or plan.source_fps or (24000, 1001)
        fps_float = _fps_to_float(fps_tuple)
        duration_seconds = frames_total / fps_float if fps_float > 0 else 0.0
        clip_records.append(
            {
                "label": label,
                "width": width,
                "height": height,
                "fps": fps_float,
                "frames": frames_total,
                "duration": duration_seconds,
                "duration_tc": _format_seconds(duration_seconds),
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
                "duration_tc": _format_seconds(duration_seconds),
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
        json_tail["trims"]["per_clip"][label] = {
            "lead_f": lead_frames,
            "trail_f": trail_frames,
            "lead_s": lead_seconds,
            "trail_s": trail_seconds,
        }

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
    manual_start_frame, manual_end_frame = frame_window
    analyze_total_frames = int(clip_records[analyze_index]["frames"])
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

    cache_info = _build_cache_info(root, plans, cfg, analyze_index)

    cache_filename = cfg.analysis.frame_data_filename
    cache_status = "disabled"
    cache_reason = None
    if not cfg.analysis.save_frames_data:
        cache_status = "disabled"
        cache_reason = "save_frames_data=false"
    elif cache_info is None:
        cache_status = "disabled"
        cache_reason = "no_cache_info"
    elif cache_info.path.exists():
        cache_status = "reused"
    else:
        cache_status = "recomputed"
        cache_reason = "missing"

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
    analyze_label = escape(analyze_label_raw.strip())
    analyze_label_colored = f"Analyzing video: [bright_cyan]{analyze_label}[/]"

    cache_exists = cache_info is not None and cache_info.path.exists()
    if cache_exists:
        reporter.verbose_line(f"Using cached frame metrics: {cache_info.path.name}")
    elif cache_status == "recomputed" and cache_info is not None:
        reporter.verbose_line(f"Frame metrics cache will be refreshed: {cache_info.path.name}")
    overrides_text = "change_fps" if cfg.overrides.change_fps else "none"
    layout_data["overrides"]["change_fps"] = overrides_text

    analysis_method = "absdiff" if cfg.analysis.motion_use_absdiff else "edge"
    json_tail["analysis"] = {
        "step": int(cfg.analysis.step),
        "downscale_height": int(cfg.analysis.downscale_height),
        "motion_method": analysis_method,
        "motion_scenecut_quantile": float(cfg.analysis.motion_scenecut_quantile),
        "motion_diff_radius": int(cfg.analysis.motion_diff_radius),
        "counts": {
            "dark": int(cfg.analysis.frame_count_dark),
            "bright": int(cfg.analysis.frame_count_bright),
            "motion": int(cfg.analysis.frame_count_motion),
            "random": int(cfg.analysis.random_frames),
            "user": len(cfg.analysis.user_frames),
        },
        "screen_separation_sec": float(cfg.analysis.screen_separation_sec),
        "random_seed": int(cfg.analysis.random_seed),
    }

    layout_data["analysis"] = dict(json_tail["analysis"])
    layout_data["clips"]["count"] = len(clip_records)
    layout_data["clips"]["items"] = clip_records
    layout_data["clips"]["ref"] = clip_records[0] if clip_records else {}
    layout_data["clips"]["tgt"] = clip_records[1] if len(clip_records) > 1 else {}

    trims_per_clip = json_tail["trims"]["per_clip"]
    trim_lookup = {detail["label"]: detail for detail in trim_details}

    def _trim_entry(label: str) -> Dict[str, object]:
        detail = trim_lookup.get(label, {})
        trim = trims_per_clip.get(label, {})
        return {
            "lead_f": trim.get("lead_f", 0),
            "trail_f": trim.get("trail_f", 0),
            "lead_s": detail.get("lead_seconds", 0.0),
            "trail_s": detail.get("trail_seconds", 0.0),
        }

    layout_data["trims"] = {}
    if clip_records:
        layout_data["trims"]["ref"] = _trim_entry(clip_records[0]["label"])
    if len(clip_records) > 1:
        layout_data["trims"]["tgt"] = _trim_entry(clip_records[1]["label"])

    reporter.update_values(layout_data)
    reporter.render_sections(["banner", "at_a_glance", "discover", "prepare"])
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
    audio_alignment_view = dict(json_tail["audio_alignment"])
    offsets_sec_map = audio_alignment_view.get("offsets_sec", {})
    offsets_frames_map = audio_alignment_view.get("offsets_frames", {})
    correlations_map = alignment_display.correlations if alignment_display else {}
    primary_label = None
    if isinstance(offsets_sec_map, dict) and offsets_sec_map:
        primary_label = sorted(offsets_sec_map.keys())[0]
    offsets_sec_value = float(offsets_sec_map.get(primary_label, 0.0)) if isinstance(offsets_sec_map, dict) else 0.0
    offsets_frames_value = int(offsets_frames_map.get(primary_label, 0)) if isinstance(offsets_frames_map, dict) else 0
    corr_value = float(correlations_map.get(primary_label, 0.0)) if correlations_map else 0.0
    if math.isnan(corr_value):
        corr_value = 0.0
    threshold_value = float(getattr(alignment_display, "threshold", cfg.audio_alignment.correlation_threshold))
    audio_alignment_view.update(
        {
            "offsets_sec": offsets_sec_value,
            "offsets_frames": offsets_frames_value,
            "corr": corr_value,
            "threshold": threshold_value,
        }
    )
    layout_data["audio_alignment"] = audio_alignment_view

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
                        eta_tc=_format_clock(eta_seconds),
                        elapsed_tc=_format_clock(elapsed),
                    )
                    analysis_progress.update(task_id, completed=completed)

                frames, frame_categories = _run_selection(_advance_samples)
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

    kept_count = len(frames)
    scanned_count = progress_total if progress_total > 0 else max(sample_count, kept_count)
    cache_summary_label = "reused" if cache_status == "reused" else ("new" if cache_status == "recomputed" else cache_status)
    json_tail["analysis"]["kept"] = kept_count
    json_tail["analysis"]["scanned"] = scanned_count
    layout_data["analysis"]["kept"] = kept_count
    layout_data["analysis"]["scanned"] = scanned_count
    layout_data["analysis"]["cache_summary_label"] = cache_summary_label
    reporter.update_values(layout_data)

    preview_rule: Dict[str, object] = reporter.layout.folding.get("frames_preview", {}) if hasattr(reporter, "layout") else {}
    head = int(preview_rule.get("head", 4)) if isinstance(preview_rule.get("head"), (int, float)) else 4
    tail = int(preview_rule.get("tail", 4)) if isinstance(preview_rule.get("tail"), (int, float)) else 4
    joiner = str(preview_rule.get("joiner", ", "))
    fold_enabled = _evaluate_rule_condition(str(preview_rule.get("when", "")) if preview_rule.get("when") else None, flags=reporter.flags)
    preview_text = _fold_sequence(frames, head=head, tail=tail, joiner=joiner, enabled=fold_enabled)

    json_tail["analysis"]["output_frame_count"] = kept_count
    json_tail["analysis"]["output_frames"] = list(frames)
    json_tail["analysis"]["output_frames_preview"] = preview_text
    layout_data["analysis"]["output_frame_count"] = kept_count
    layout_data["analysis"]["output_frames_preview"] = preview_text

    out_dir = (root / cfg.screenshots.directory_name).resolve()
    total_screens = len(frames) * len(plans)

    writer_name = "FFmpeg" if cfg.screenshots.use_ffmpeg else "VS"
    overlay_mode_value = getattr(cfg.color, "overlay_mode", "minimal")

    json_tail["render"] = {
        "writer": writer_name,
        "out_dir": str(out_dir),
        "add_frame_info": bool(cfg.screenshots.add_frame_info),
        "single_res": int(cfg.screenshots.single_res),
        "upscale": bool(cfg.screenshots.upscale),
        "mod_crop": int(cfg.screenshots.mod_crop),
        "letterbox_pillarbox_aware": bool(cfg.screenshots.letterbox_pillarbox_aware),
        "pad_to_canvas": cfg.screenshots.pad_to_canvas,
        "center_pad": bool(cfg.screenshots.center_pad),
        "letterbox_px_tolerance": int(cfg.screenshots.letterbox_px_tolerance),
        "compression": int(cfg.screenshots.compression_level),
    }
    layout_data["render"] = json_tail["render"]
    json_tail["tonemap"] = {
        "preset": cfg.color.preset,
        "tone_curve": cfg.color.tone_curve,
        "dynamic_peak_detection": bool(cfg.color.dynamic_peak_detection),
        "target_nits": float(cfg.color.target_nits),
        "verify_luma_threshold": float(cfg.color.verify_luma_threshold),
        "overlay_enabled": bool(cfg.color.overlay_enabled),
        "overlay_mode": overlay_mode_value,
    }
    layout_data["tonemap"] = json_tail["tonemap"]
    json_tail["overlay"] = {
        "enabled": bool(cfg.color.overlay_enabled),
        "template": cfg.color.overlay_text_template,
        "mode": overlay_mode_value,
    }
    layout_data["overlay"] = json_tail["overlay"]

    reporter.update_values(layout_data)
    reporter.render_sections(["render"])

    try:
        if total_screens > 0:
            start_time = time.perf_counter()
            processed = 0

            reporter.update_progress_state(
                "render_bar",
                fps="0.00 fps",
                eta_tc="--:--",
                elapsed_tc="00:00",
                current=0,
                total=total_screens,
            )

            with reporter.create_progress("render_bar", transient=False) as render_progress:
                task_id = render_progress.add_task(
                    'Rendering outputs',
                    total=total_screens,
                )

                def advance_render(count: int) -> None:
                    nonlocal processed
                    processed += count
                    elapsed = max(time.perf_counter() - start_time, 1e-6)
                    fps_val = processed / elapsed
                    remaining = max(total_screens - processed, 0)
                    eta_seconds = (remaining / fps_val) if fps_val > 0 else None
                    reporter.update_progress_state(
                        "render_bar",
                        fps=f"{fps_val:7.2f} fps",
                        eta_tc=_format_clock(eta_seconds),
                        elapsed_tc=_format_clock(elapsed),
                        current=min(processed, total_screens),
                        total=total_screens,
                    )
                    render_progress.update(task_id, completed=min(total_screens, processed))

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
                    warnings_sink=collected_warnings,
                )

                if processed < total_screens:
                    elapsed = max(time.perf_counter() - start_time, 1e-6)
                    fps_val = processed / elapsed
                    reporter.update_progress_state(
                        "render_bar",
                        fps=f"{fps_val:7.2f} fps",
                        eta_tc=_format_clock(0.0),
                        elapsed_tc=_format_clock(elapsed),
                        current=total_screens,
                        total=total_screens,
                    )
                    render_progress.update(task_id, completed=total_screens)
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
                warnings_sink=collected_warnings,
            )
    except ScreenshotError as exc:
        raise CLIAppError(
            f"Screenshot generation failed: {exc}",
            rich_message=f"[red]Screenshot generation failed:[/red] {exc}",
        ) from exc

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
        print("[cyan]Preparing slow.pics upload...[/cyan]")
        upload_total = len(image_paths)
        def _safe_size(path_str: str) -> int:
            try:
                return Path(path_str).stat().st_size
            except OSError:
                return 0

        file_sizes = [_safe_size(path) for path in image_paths] if upload_total else []
        total_bytes = sum(file_sizes)

        console_width = getattr(reporter.console.size, "width", 80) or 80
        stats_width_limit = max(24, console_width - 32)

        def _format_duration(seconds: Optional[float]) -> str:
            if seconds is None or not math.isfinite(seconds):
                return "--:--"
            total = max(0, int(seconds + 0.5))
            hours, remainder = divmod(total, 3600)
            minutes, secs = divmod(remainder, 60)
            if hours:
                return f"{hours:d}:{minutes:02d}:{secs:02d}"
            return f"{minutes:02d}:{secs:02d}"

        def _format_stats(files_done: int, bytes_done: int, elapsed: float) -> str:
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
            reporter.line(_color_text("[✓] slow.pics: establishing session", "green"))
            if upload_total > 0:
                start_time = time.perf_counter()
                uploaded_files = 0
                uploaded_bytes = 0
                file_index = 0

                columns = [
                    TextColumn('{task.percentage:>6.02f}% {task.completed}/{task.total}', justify='left'),
                    BarColumn(),
                    TextColumn('{task.fields[stats]}', justify='right'),
                ]
                with reporter.progress(*columns, transient=False) as upload_progress:
                    task_id = upload_progress.add_task(
                        '',
                        total=upload_total,
                        stats=_format_stats(0, 0, 0.0),
                    )

                    def advance_upload(count: int) -> None:
                        nonlocal uploaded_files, uploaded_bytes, file_index
                        uploaded_files += count
                        for _ in range(count):
                            if file_index < len(file_sizes):
                                uploaded_bytes += file_sizes[file_index]
                                file_index += 1
                        elapsed = time.perf_counter() - start_time
                        upload_progress.update(
                            task_id,
                            completed=min(upload_total, uploaded_files),
                            stats=_format_stats(uploaded_files, uploaded_bytes, elapsed),
                        )

                    slowpics_url = upload_comparison(
                        image_paths,
                        out_dir,
                        cfg.slowpics,
                        progress_callback=advance_upload,
                    )

                    elapsed = time.perf_counter() - start_time
                    upload_progress.update(
                        task_id,
                        completed=upload_total,
                        stats=_format_stats(uploaded_files, uploaded_bytes, elapsed),
                    )
            else:
                slowpics_url = upload_comparison(
                    image_paths,
                    out_dir,
                    cfg.slowpics,
                )
            reporter.line(_color_text(f"[✓] slow.pics: uploading {upload_total} images", "green"))
            reporter.line(_color_text("[✓] slow.pics: assembling collection", "green"))
        except SlowpicsAPIError as exc:
            raise CLIAppError(
                f"slow.pics upload failed: {exc}",
                rich_message=f"[red]slow.pics upload failed:[/red] {exc}",
            ) from exc

    if slowpics_url:
        slowpics_block = json_tail.get("slowpics")
        if slowpics_block is not None:
            slowpics_block["url"] = slowpics_url
            if cfg.slowpics.create_url_shortcut:
                key = slowpics_url.rstrip("/").rsplit("/", 1)[-1]
                if key:
                    slowpics_block["shortcut_path"] = str(out_dir / f"slowpics_{key}.url")
                else:
                    slowpics_block.setdefault("shortcut_path", None)
            else:
                slowpics_block["shortcut_path"] = None

    result = RunResult(
        files=[plan.path for plan in plans],
        frames=list(frames),
        out_dir=out_dir,
        config=cfg,
        image_paths=list(image_paths),
        slowpics_url=slowpics_url,
        json_tail=json_tail,
    )

    summary_lines: List[str] = []
    summary_section = next(
        (section for section in reporter.layout.sections if section.get("id") == "summary"),
        None,
    )
    if isinstance(summary_section, Mapping):
        items = summary_section.get("items", [])
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, str):
                    continue
                rendered = reporter.renderer.render_template(item, reporter.values, reporter.flags)
                if rendered:
                    summary_lines.append(rendered)

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
    warnings_section = next((section for section in reporter.layout.sections if section.get("id") == "warnings"), {})
    fold_config = warnings_section.get("fold_labels", {}) if isinstance(warnings_section, Mapping) else {}
    head = int(fold_config.get("head", 2)) if isinstance(fold_config.get("head"), (int, float)) else 2
    tail = int(fold_config.get("tail", 1)) if isinstance(fold_config.get("tail"), (int, float)) else 1
    joiner = str(fold_config.get("joiner", ", "))
    fold_enabled = _evaluate_rule_condition(str(fold_config.get("when")) if fold_config.get("when") else None, flags=reporter.flags)

    warnings_data: List[Dict[str, object]] = []
    if warnings_list:
        labels_text = _fold_sequence(warnings_list, head=head, tail=tail, joiner=joiner, enabled=fold_enabled)
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

    layout_sections = getattr(getattr(reporter, "layout", None), "sections", [])
    has_summary_section = any(
        isinstance(section, Mapping) and section.get("id") == "summary"
        for section in layout_sections
    )
    compatibility_required = bool(
        reporter.flags.get("compat.summary_fallback")
        or reporter.flags.get("compatibility_mode")
        or reporter.flags.get("legacy_summary_fallback")
    )

    if not reporter.quiet and (compatibility_required or not has_summary_section):
        summary_lines = _build_legacy_summary_lines(layout_data)
        reporter.section("Summary")
        for line in summary_lines:
            reporter.line(_color_text(line, "green"))

    return result


@click.command()
@click.option("--config", "config_path", default="config.toml", show_default=True, help="Path to config.toml")
@click.option("--input", "input_dir", default=None, help="Override [paths.input_dir] from config.toml")
@click.option(
    "--audio-align-track",
    "audio_align_track_option",
    type=str,
    multiple=True,
    help="Manual audio track override in the form label=index. Repeatable.",
)
@click.option("--quiet", is_flag=True, help="Suppress verbose output; show banner, progress, and JSON only.")
@click.option("--verbose", is_flag=True, help="Show additional diagnostic output during run.")
@click.option("--no-color", is_flag=True, help="Disable ANSI colour output.")
@click.option("--json-pretty", is_flag=True, help="Pretty-print the JSON tail output.")
def main(
    config_path: str,
    input_dir: str | None,
    *,
    audio_align_track_option: tuple[str, ...],
    quiet: bool,
    verbose: bool,
    no_color: bool,
    json_pretty: bool,
) -> None:
    try:
        result = run_cli(
            config_path,
            input_dir,
            audio_track_overrides=audio_align_track_option,
            quiet=quiet,
            verbose=verbose,
            no_color=no_color,
        )
    except CLIAppError as exc:
        print(exc.rich_message)
        raise click.exceptions.Exit(exc.code) from exc

    slowpics_url = result.slowpics_url
    cfg = result.config
    out_dir = result.out_dir
    json_tail = result.json_tail or {}

    slowpics_block = json_tail.get("slowpics")
    shortcut_path_str: Optional[str] = None
    deleted_dir = False
    clipboard_hint = ""

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
            clipboard_hint = ""
        else:
            clipboard_hint = " (copied to clipboard)"

        if cfg.slowpics.create_url_shortcut:
            key = slowpics_url.rstrip("/").rsplit("/", 1)[-1]
            if key:
                shortcut_path_str = str(out_dir / f"slowpics_{key}.url")

        print("[✓] slow.pics: verifying & saving shortcut")
        url_line = f"slow.pics URL: {slowpics_url}{clipboard_hint}"
        print(url_line)
        if shortcut_path_str:
            print(f"Shortcut: {shortcut_path_str}")
        else:
            print("Shortcut: (disabled)")

        if cfg.slowpics.delete_screen_dir_after_upload:
            try:
                shutil.rmtree(out_dir)
                deleted_dir = True
                print("Cleaned up screenshots after upload")
                builtins.print(f"  {out_dir}")
            except OSError as exc:
                print(f"[yellow]Warning:[/yellow] Failed to delete screenshot directory: {exc}")
        if slowpics_block is not None:
            slowpics_block["url"] = slowpics_url
            slowpics_block["shortcut_path"] = shortcut_path_str
            slowpics_block["deleted_screens_dir"] = deleted_dir
        else:
            json_tail.setdefault("slowpics", {}).update(
                {
                    "url": slowpics_url,
                    "shortcut_path": shortcut_path_str,
                    "deleted_screens_dir": deleted_dir,
                }
            )
    elif slowpics_block is not None:
        slowpics_block.setdefault("deleted_screens_dir", False)
        slowpics_block.setdefault("shortcut_path", None)
        slowpics_block.setdefault("url", None)

    if json_pretty:
        json_output = json.dumps(json_tail, indent=2)
    else:
        json_output = json.dumps(json_tail, separators=(",", ":"))
    print(json_output)


if __name__ == "__main__":
    main()
