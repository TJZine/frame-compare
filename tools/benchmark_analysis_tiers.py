#!/usr/bin/env python3
"""Benchmark analysis performance mode against quality on local clips."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from frame_compare.analysis.cache_io import compute_cache_key, delete_metrics_cache_entry
from frame_compare.analysis.metrics import calculate_metrics
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.tier_validation import (
    SelectionCategory,
    compare_rankings,
    compare_selection_category,
    tier_category_tolerance,
)
from frame_compare.analysis.timing import AnalysisTimingRecorder
from frame_compare.analysis.types import (
    ActiveRectAlgorithmId,
    ActiveRectDetectionMode,
    ActiveRectSource,
    FrameMetrics,
    FrameSelection,
    MetricActiveRect,
    MetricCacheRequest,
)
from frame_compare.config.loader import load_config
from frame_compare.config.schema import AnalysisConfig, ConfigSchema
from frame_compare.config.schema_enums import (
    AnalysisPerformanceMode,
    ScreenshotActiveRectDetection,
    SourceMatchFpsMode,
)
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.context import (
    ACTIVE_RECT_RESOLUTION_ALGORITHM,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
)
from frame_compare.orchestration.selection_domain import (
    build_selection_domain_clips_with_diagnostics,
)
from frame_compare.orchestration.source_selection import (
    resolve_source_selection,
    resolve_source_selector,
)
from frame_compare.vs.loader import DefaultVSLoader

type JsonObject = dict[str, Any]
type MetricCachePolicy = Literal["cold", "reuse"]

FFPROBE_TIMEOUT_SECONDS = 120.0


class _FramesReadable(Protocol):
    num_frames: int

    def frames(self, *, close: bool = False) -> Iterator[object]: ...


class _PlaneStatsNamespace(Protocol):
    def PlaneStats(self) -> _FramesReadable: ...


class _PlaneStatsSource(Protocol):
    num_frames: int
    std: _PlaneStatsNamespace


@dataclass(frozen=True, slots=True)
class BenchmarkActiveRect:
    """Active-rect geometry and provenance used for benchmark cache metadata."""

    rect: MetricActiveRect | None
    source: ActiveRectSource
    detection_mode: ActiveRectDetectionMode
    algorithm_id: ActiveRectAlgorithmId = ACTIVE_RECT_RESOLUTION_ALGORITHM


@dataclass(frozen=True, slots=True)
class BenchmarkAnalysisSource:
    """Resolved benchmark source and cache-domain facts."""

    path: Path
    ordered_paths: tuple[Path, ...]
    effective_fps: Fraction | None
    active_rect: BenchmarkActiveRect
    overrides_by_path: Mapping[Path, SourceOverrideConfig]

    @property
    def reference_path(self) -> Path:
        return self.ordered_paths[0]


def main() -> int:
    args = _parse_args()
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    output_path = args.output if args.output.is_absolute() else root / args.output
    input_paths = tuple(
        path if path.is_absolute() else root / path for path in cast(Sequence[Path], args.inputs)
    )
    config = load_config(config_path)
    input_dir = _resolve_config_path(root, config.paths.input_dir)
    cache_dir = (
        args.cache_dir
        if args.cache_dir is not None
        else _resolve_config_path(root, config.paths.generated_dir) / "cache" / "analysis"
    )
    if not cache_dir.is_absolute():
        cache_dir = root / cache_dir
    analysis_source = _resolve_benchmark_analysis_source(
        root=root,
        input_dir=input_dir,
        input_paths=input_paths,
        config=config,
    )
    _require_selection_domain_for_analysis_cache_identity(
        selection_domain=args.selection_domain,
        video_paths=input_paths,
        analysis_source=analysis_source,
        active_rect_detection=config.screenshots.active_rect_detection,
    )
    source_indexes = _source_index_facts(analysis_source.ordered_paths)
    selected_index = source_indexes[analysis_source.path.as_posix()]
    if args.require_warm_source_index and not selected_index["detected"]:
        raise SystemExit(
            "A warm source index was required but no adjacent L-SMASH index was detected "
            f"for the selected analysis source: {analysis_source.path.as_posix()}"
        )
    warnings: list[str] = []

    quality, comparisons = _run_benchmark_tiers(
        candidate_modes=cast(Sequence[str], args.modes),
        video_paths=analysis_source.ordered_paths,
        analysis_config=config.analysis,
        cache_dir=cache_dir,
        analysis_source_path=analysis_source.path,
        effective_fps=analysis_source.effective_fps,
        active_rect=analysis_source.active_rect,
        selection_domain=args.selection_domain,
        window_start=args.window_start,
        window_end_exclusive=args.window_end_exclusive,
        progress_enabled=not args.no_progress,
        repetitions=args.repetitions,
        metric_cache_policy=cast(MetricCachePolicy, args.metric_cache_policy),
    )
    decode_baseline = (
        None
        if args.skip_decode_baseline
        else _run_decode_baseline(analysis_source_path=analysis_source.path)
    )
    source_probe = _probe_source_facts(
        analysis_source.path,
        inspect_frame_types=args.inspect_frame_types,
        timeout_seconds=args.ffprobe_timeout,
    )

    if args.window_end_exclusive is None:
        warnings.append(
            "No explicit --window-end-exclusive was provided; comparisons use the full analysis metric domain."
        )
    if args.selection_domain is None:
        warnings.append(
            "No orchestration selection-domain token was provided; cache identity may differ from a full run with trims or source overrides."
        )
    if not args.inspect_frame_types:
        warnings.append(
            "Frame-type/GOP inspection was not requested; pass --inspect-frame-types to "
            "record keyframe and I/P/B-frame distribution outside timed trials."
        )

    report: JsonObject = {
        "inputs": [path.as_posix() for path in analysis_source.ordered_paths],
        "config": {
            "config_path": config_path.as_posix(),
            "analysis_source": config.sources.analysis_source,
            "analysis_source_path": analysis_source.path.as_posix(),
            "effective_fps": (
                str(analysis_source.effective_fps)
                if analysis_source.effective_fps is not None
                else None
            ),
            "metric_active_rect": _metric_active_rect_json(analysis_source.active_rect.rect),
            "active_rect_source": analysis_source.active_rect.source,
            "active_rect_detection_mode": analysis_source.active_rect.detection_mode,
            "active_rect_algorithm_id": analysis_source.active_rect.algorithm_id,
            "selection_window": {
                "start_frame": quality["window"]["start_frame"],
                "end_frame_exclusive": quality["window"]["end_frame_exclusive"],
            },
            "selection_counts": {
                "dark": config.analysis.dark_frame_count,
                "bright": config.analysis.bright_frame_count,
                "motion": config.analysis.motion_frame_count,
                "random": config.analysis.random_frame_count,
                "user": len(config.analysis.user_frames),
            },
            "quantiles": {
                "dark": config.analysis.dark_quantile,
                "bright": config.analysis.bright_quantile,
            },
            "selection_domain": args.selection_domain,
            "metric_cache_policy": args.metric_cache_policy,
            "repetitions": args.repetitions,
            "trial_order_policy": "deterministic_rotation",
            "require_warm_source_index": args.require_warm_source_index,
        },
        "runtime": _runtime_facts(),
        "source": {
            "analysis_source": source_probe,
            "indexes": source_indexes,
        },
        "decode_baseline": decode_baseline,
        "quality": _tier_summary(quality),
        "comparisons": comparisons,
        "warnings": warnings,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output_path.as_posix())
    return 0


def _resolve_config_path(root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else root / path


def _runtime_facts() -> JsonObject:
    facts: JsonObject = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "logical_cpu_count": os.cpu_count(),
        "ffmpeg": _command_version("ffmpeg"),
        "ffprobe": _command_version("ffprobe"),
    }
    try:
        import vapoursynth as vs

        facts["vapoursynth"] = str(getattr(vs, "__version__", "unknown"))
        facts["vapoursynth_api"] = str(getattr(vs, "__api_version__", "unknown"))
        facts["vapoursynth_core_threads"] = int(vs.core.num_threads)
        facts["vapoursynth_core_max_cache_mb"] = int(vs.core.max_cache_size)
    except Exception as exc:
        facts["vapoursynth_error"] = f"{type(exc).__name__}: {exc}"
    return facts


def _command_version(command: str) -> str | None:
    try:
        result = subprocess.run(
            [command, "-version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    return first_line or None


def _source_index_facts(paths: Sequence[Path]) -> dict[str, JsonObject]:
    facts: dict[str, JsonObject] = {}
    for path in paths:
        candidates = list(
            dict.fromkeys(
                (
                    Path(f"{path}.lwi"),
                    path.with_suffix(".lwi"),
                    path.with_suffix(f"{path.suffix}.lwi"),
                )
            )
        )
        existing = [candidate for candidate in candidates if candidate.is_file()]
        facts[path.as_posix()] = {
            "detected": bool(existing),
            "paths": [candidate.as_posix() for candidate in existing],
            "sizes_bytes": [candidate.stat().st_size for candidate in existing],
        }
    return facts


def _probe_source_facts(
    path: Path,
    *,
    inspect_frame_types: bool,
    timeout_seconds: float,
) -> JsonObject:
    stream_payload = _run_ffprobe_json(
        [
            "-select_streams",
            "v:0",
            "-show_entries",
            (
                "stream=codec_name,codec_long_name,profile,pix_fmt,width,height,"
                "bits_per_raw_sample,avg_frame_rate,r_frame_rate,nb_frames,duration:"
                "format=format_name,duration,size,bit_rate"
            ),
        ],
        path=path,
        timeout_seconds=timeout_seconds,
    )
    result: JsonObject = {
        "path": path.as_posix(),
        "size_bytes": path.stat().st_size,
        "stream_and_format": stream_payload,
    }
    if inspect_frame_types:
        started = time.perf_counter()
        frame_payload = _run_ffprobe_json(
            [
                "-select_streams",
                "v:0",
                "-show_frames",
                "-show_entries",
                "frame=key_frame,pict_type",
            ],
            path=path,
            timeout_seconds=timeout_seconds,
        )
        result["frame_type_inspection_seconds"] = time.perf_counter() - started
        result["frame_types"] = _frame_type_summary(frame_payload)
    return result


def _run_ffprobe_json(
    options: Sequence[str],
    *,
    path: Path,
    timeout_seconds: float,
) -> JsonObject:
    try:
        completed = subprocess.run(
            ["ffprobe", "-v", "error", *options, "-of", "json", str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except OSError as exc:
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"ffprobe timed out after {timeout_seconds}s"}
    if completed.returncode != 0:
        return {
            "success": False,
            "returncode": completed.returncode,
            "error": completed.stderr.strip(),
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"invalid ffprobe JSON: {exc}"}
    if not isinstance(payload, dict):
        return {"success": False, "error": "ffprobe JSON root was not an object"}
    return {"success": True, "payload": payload}


def _frame_type_summary(ffprobe_result: JsonObject) -> JsonObject:
    payload = ffprobe_result.get("payload")
    if not isinstance(payload, Mapping):
        return {"available": False}
    typed_payload = cast(Mapping[str, object], payload)
    frames_value = typed_payload.get("frames")
    if not isinstance(frames_value, list):
        return {"available": False}
    frames = cast(list[object], frames_value)

    type_counts: dict[str, int] = {}
    keyframe_indices: list[int] = []
    for index, raw_frame in enumerate(frames):
        if not isinstance(raw_frame, Mapping):
            continue
        pict_type = raw_frame.get("pict_type")
        if isinstance(pict_type, str):
            type_counts[pict_type] = type_counts.get(pict_type, 0) + 1
        if raw_frame.get("key_frame") == 1:
            keyframe_indices.append(index)
    keyframe_gaps = [
        right - left for left, right in zip(keyframe_indices, keyframe_indices[1:], strict=False)
    ]
    return {
        "available": True,
        "frame_count": len(frames),
        "type_counts": type_counts,
        "keyframe_count": len(keyframe_indices),
        "keyframe_gap_frames": _distribution([float(gap) for gap in keyframe_gaps]),
    }


def _run_decode_baseline(*, analysis_source_path: Path) -> JsonObject:
    loader = DefaultVSLoader()
    cpu_started = time.process_time()
    overall_started = time.perf_counter()
    load_started = time.perf_counter()
    source = loader.load(analysis_source_path)
    source_load_seconds = time.perf_counter() - load_started
    try:
        graph_started = time.perf_counter()
        node = cast(_PlaneStatsSource, source.clip)
        stats = node.std.PlaneStats()
        graph_build_seconds = time.perf_counter() - graph_started
        render_started = time.perf_counter()
        rendered_frames = sum(1 for _frame in stats.frames(close=True))
        frame_render_seconds = time.perf_counter() - render_started
    finally:
        del source
    wall_seconds = time.perf_counter() - overall_started
    cpu_seconds = time.process_time() - cpu_started
    return {
        "operation": "full_source_plane0_planestats_concurrent",
        "frame_count": rendered_frames,
        "wall_seconds": wall_seconds,
        "source_load_seconds": source_load_seconds,
        "graph_build_seconds": graph_build_seconds,
        "frame_render_seconds": frame_render_seconds,
        "frames_per_second": (
            0.0 if frame_render_seconds <= 0.0 else rendered_frames / frame_render_seconds
        ),
        "process_cpu_seconds": cpu_seconds,
        "cpu_to_wall_ratio": 0.0 if wall_seconds <= 0.0 else cpu_seconds / wall_seconds,
        "peak_rss_bytes": _peak_rss_bytes(),
        "note": "Executed after timed mode trials so it cannot warm their source/frame caches.",
    }


def _resolve_benchmark_analysis_source_path(
    *,
    input_dir: Path,
    input_paths: Sequence[Path],
    config: ConfigSchema,
) -> Path:
    if config.sources.analysis_source == "fastest":
        raise SystemExit(
            "sources.analysis_source = 'fastest' is not supported by this benchmark tool; "
            "use an explicit source selector so benchmark evidence names the analyzed clip."
        )
    if config.sources.match_fps != SourceMatchFpsMode.DISABLED:
        raise SystemExit(
            "sources.match_fps automatic FPS policies are not supported by this benchmark tool; "
            "use explicit sources.overrides effective_fps values for benchmark evidence."
        )

    selection = resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=list(input_paths),
        config=config.sources,
    )
    if config.sources.analysis_source == "reference":
        return selection.ordered_paths[0]
    return resolve_source_selector(
        selector=config.sources.analysis_source,
        input_dir=input_dir,
        paths=selection.ordered_paths,
        role="sources.analysis_source",
    )


def _resolve_benchmark_analysis_source(
    *,
    root: Path,
    input_dir: Path,
    input_paths: Sequence[Path],
    config: ConfigSchema,
) -> BenchmarkAnalysisSource:
    source_path = _resolve_benchmark_analysis_source_path(
        input_dir=input_dir,
        input_paths=input_paths,
        config=config,
    )
    selection = resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=list(input_paths),
        config=config.sources,
    )
    override = selection.overrides_by_path.get(source_path)
    effective_fps = None if override is None else override.effective_fps
    active_rect = _benchmark_active_rect_from_prepared_clip(
        source_path=source_path,
        override=override,
        prepared_clip=_prepared_benchmark_clip(
            root=root,
            input_paths=selection.ordered_paths,
            config=config,
            source_path=source_path,
            overrides_by_path=selection.overrides_by_path,
        ),
        config=config,
    )
    return BenchmarkAnalysisSource(
        path=source_path,
        ordered_paths=tuple(selection.ordered_paths),
        effective_fps=effective_fps,
        active_rect=active_rect,
        overrides_by_path=selection.overrides_by_path,
    )


def _effective_fps_override_for_path(
    *,
    input_dir: Path,
    input_paths: Sequence[Path],
    config: ConfigSchema,
    source_path: Path,
) -> Fraction | None:
    selection = resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=list(input_paths),
        config=config.sources,
    )
    override = selection.overrides_by_path.get(source_path)
    return None if override is None else override.effective_fps


def _prepared_benchmark_clip(
    *,
    root: Path,
    input_paths: Sequence[Path],
    config: ConfigSchema,
    source_path: Path,
    overrides_by_path: dict[Path, SourceOverrideConfig],
) -> ClipState | None:
    cache_path = _resolve_config_path(root, config.paths.generated_dir) / "clip_probe.toml"
    entries_by_key = dict(load_clip_probe_cache(cache_path))
    snapshots_by_path: dict[Path, ClipProbeSnapshot] = {}
    for path in input_paths:
        stats = path.stat()
        fingerprint = ClipFingerprint(
            path=path,
            size_bytes=stats.st_size,
            mtime_ns=stats.st_mtime_ns,
        )
        snapshot = entries_by_key.get(compute_probe_cache_key(fingerprint))
        if snapshot is None:
            return None
        snapshots_by_path[path] = snapshot

    result = build_selection_domain_clips_with_diagnostics(
        ordered_paths=list(input_paths),
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=overrides_by_path,
        labels_by_path={path: path.stem for path in input_paths},
        match_fps=config.sources.match_fps,
        active_rect_detection=config.screenshots.active_rect_detection,
    )
    return next(clip for clip in result.clips if clip.path == source_path)


def _benchmark_active_rect_from_prepared_clip(
    *,
    source_path: Path,
    override: SourceOverrideConfig | None,
    prepared_clip: ClipState | None,
    config: ConfigSchema,
) -> BenchmarkActiveRect:
    if override is not None and override.active_rect is not None:
        rect = override.active_rect
        return BenchmarkActiveRect(
            rect=MetricActiveRect(
                x=rect.x,
                y=rect.y,
                width=rect.width,
                height=rect.height,
            ),
            source="explicit",
            detection_mode=config.screenshots.active_rect_detection.value,
        )
    if prepared_clip is None or prepared_clip.active_rect is None:
        raise SystemExit(
            "Benchmark active-rect provenance is unavailable because prepared clip probe "
            f"data for {source_path.name} is missing. Run a normal preparation path to "
            "write generated/clip_probe.toml, or configure an explicit "
            "sources.overrides.<selector>.active_rect for benchmark evidence."
        )
    prepared = prepared_clip.active_rect
    if (
        config.screenshots.active_rect_detection == ScreenshotActiveRectDetection.AUTO
        and prepared.source == "full-frame"
    ):
        raise SystemExit(
            "Benchmark active-rect provenance is incomplete for "
            "screenshots.active_rect_detection = 'auto' because content refinement is not "
            "run by this benchmark tool. Run the normal pipeline and benchmark with an "
            "explicit prepared active_rect, or use a non-auto detection mode."
        )
    return BenchmarkActiveRect(
        rect=MetricActiveRect(
            x=prepared.x,
            y=prepared.y,
            width=prepared.width,
            height=prepared.height,
        ),
        source=prepared.source,
        detection_mode=prepared.detection_mode,
        algorithm_id=prepared.algorithm_id,
    )


def _metric_active_rect_json(rect: MetricActiveRect | None) -> JsonObject | None:
    if rect is None:
        return None
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
    }


def _require_selection_domain_for_analysis_cache_identity(
    *,
    selection_domain: str | None,
    video_paths: Sequence[Path],
    analysis_source: BenchmarkAnalysisSource,
    active_rect_detection: ScreenshotActiveRectDetection,
) -> None:
    """Require the production token whenever the benchmark domain is non-default."""
    if selection_domain is not None:
        return
    domain_is_default = (
        bool(video_paths)
        and analysis_source.reference_path == video_paths[0]
        and analysis_source.path == video_paths[0]
        and analysis_source.effective_fps is None
        and active_rect_detection == ScreenshotActiveRectDetection.ASPECT_RATIO
        and not any(
            _source_override_affects_selection_domain(override)
            for override in analysis_source.overrides_by_path.values()
        )
    )
    if domain_is_default:
        return
    raise SystemExit(
        "A benchmark selection-domain token is required when benchmark inputs affect "
        "analysis cache identity. Domain-affecting inputs include: a non-default reference "
        "or analysis source, active-rect detection policy, source trims, effective FPS "
        "overrides, and explicit active rectangles. Pass --selection-domain from a "
        "prepared run or benchmark with default inputs."
    )


def _source_override_affects_selection_domain(override: SourceOverrideConfig) -> bool:
    return bool(
        override.trim_start_frames
        or override.trim_end_frames
        or override.effective_fps is not None
        or override.active_rect is not None
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare performance analysis mode against quality and write JSON.",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Input video paths in run order.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Workspace root.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/config.toml"),
        help="Config TOML path relative to root unless absolute.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path.")
    parser.add_argument(
        "--mode",
        dest="modes",
        action="append",
        choices=["performance"],
        help="Candidate mode to compare. Repeatable; defaults to performance.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Analysis cache directory. Defaults to generated/cache/analysis under root.",
    )
    parser.add_argument(
        "--selection-domain",
        default=None,
        help="Optional orchestration selection-domain token to include in cache identity.",
    )
    parser.add_argument("--window-start", type=int, default=0, help="Source-frame window start.")
    parser.add_argument(
        "--window-end-exclusive",
        type=int,
        default=None,
        help="Source-frame window end. Defaults to metric frame count.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable stderr progress display for scripted runs.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=3,
        help="Timed repetitions per mode; trial order rotates each repetition (default: 3).",
    )
    parser.add_argument(
        "--metric-cache-policy",
        choices=["cold", "reuse"],
        default="cold",
        help="Delete each mode's metric cache before every trial, or allow reuse.",
    )
    parser.add_argument(
        "--require-warm-source-index",
        action="store_true",
        help=(
            "Fail unless an adjacent L-SMASH .lwi index is detected for the selected "
            "analysis source."
        ),
    )
    parser.add_argument(
        "--skip-decode-baseline",
        action="store_true",
        help="Skip the post-trial decode/PlaneStats throughput baseline.",
    )
    parser.add_argument(
        "--inspect-frame-types",
        action="store_true",
        help="Use ffprobe outside timed trials to record I/P/B and keyframe distribution.",
    )
    parser.add_argument(
        "--ffprobe-timeout",
        type=float,
        default=FFPROBE_TIMEOUT_SECONDS,
        help="Timeout in seconds for each source-inspection ffprobe command.",
    )
    args = parser.parse_args()
    if args.modes is None:
        args.modes = ["performance"]
    if args.window_start < 0:
        parser.error("--window-start must be non-negative")
    if args.window_end_exclusive is not None and args.window_end_exclusive <= args.window_start:
        parser.error("--window-end-exclusive must be greater than --window-start")
    if args.repetitions <= 0:
        parser.error("--repetitions must be positive")
    if args.ffprobe_timeout <= 0:
        parser.error("--ffprobe-timeout must be positive")
    return args


def _run_benchmark_tiers(
    *,
    candidate_modes: Sequence[str],
    video_paths: Sequence[Path],
    analysis_config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    selection_domain: str | None,
    window_start: int,
    window_end_exclusive: int | None,
    progress_enabled: bool,
    repetitions: int = 1,
    metric_cache_policy: MetricCachePolicy = "reuse",
) -> tuple[JsonObject, dict[str, JsonObject]]:
    console = Console(stderr=True)
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        disable=not progress_enabled,
    )
    modes = list(dict.fromkeys(("quality", *candidate_modes)))
    total = len(modes) * repetitions
    trials_by_mode: dict[str, list[JsonObject]] = {mode: [] for mode in modes}

    with progress:
        task_id = progress.add_task("Starting analysis benchmark", total=total)
        for repetition in range(repetitions):
            order = _rotated_trial_order(modes, repetition)
            for order_index, mode in enumerate(order):
                progress.update(
                    task_id,
                    description=f"Running {mode} analysis ({repetition + 1}/{repetitions})",
                )
                trials_by_mode[mode].append(
                    _run_tier(
                        mode=mode,
                        video_paths=video_paths,
                        analysis_config=analysis_config,
                        cache_dir=cache_dir,
                        analysis_source_path=analysis_source_path,
                        effective_fps=effective_fps,
                        active_rect=active_rect,
                        selection_domain=selection_domain,
                        window_start=window_start,
                        window_end_exclusive=window_end_exclusive,
                        metric_cache_policy=metric_cache_policy,
                        repetition=repetition,
                        order_index=order_index,
                    )
                )
                progress.advance(task_id)

        progress.update(task_id, description="Analysis benchmark complete")

    quality = _aggregate_tier_trials(trials_by_mode["quality"])
    comparisons = {
        mode: _compare_tier(
            quality=quality,
            candidate=_aggregate_tier_trials(trials_by_mode[mode]),
        )
        for mode in modes
        if mode != "quality"
    }
    return quality, comparisons


def _rotated_trial_order(modes: Sequence[str], repetition: int) -> list[str]:
    """Rotate mode order deterministically to spread warm-cache/order bias."""
    if not modes:
        return []
    offset = repetition % len(modes)
    return [*modes[offset:], *modes[:offset]]


def _run_tier(
    *,
    mode: str,
    video_paths: Sequence[Path],
    analysis_config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    selection_domain: str | None,
    window_start: int,
    window_end_exclusive: int | None,
    metric_cache_policy: MetricCachePolicy = "reuse",
    repetition: int = 0,
    order_index: int = 0,
) -> JsonObject:
    tier_config = analysis_config.model_copy(
        update={"performance_mode": AnalysisPerformanceMode(mode)}
    )
    if metric_cache_policy == "cold":
        _delete_tier_metrics_cache(
            video_paths=video_paths,
            config=tier_config,
            cache_dir=cache_dir,
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            active_rect=active_rect,
            selection_domain=selection_domain,
        )
    timing_recorder = AnalysisTimingRecorder()
    cpu_started = time.process_time()
    trial_started = time.perf_counter()
    started = time.perf_counter()
    metrics = _calculate_metrics_with_expected_active_rect(
        video_paths=video_paths,
        config=tier_config,
        cache_dir=cache_dir,
        analysis_source_path=analysis_source_path,
        effective_fps=effective_fps,
        active_rect=active_rect,
        selection_domain=selection_domain,
        timing_recorder=timing_recorder,
    )
    analyze_seconds = time.perf_counter() - started
    windowed_metrics, source_offset = _windowed_metrics(
        metrics,
        window_start=window_start,
        window_end_exclusive=window_end_exclusive,
    )
    selection_started = time.perf_counter()
    selection = select_frames(
        windowed_metrics,
        _config_for_window(
            tier_config,
            window_start=source_offset,
            window_end=source_offset + windowed_metrics.metadata.frame_count,
        ),
    )
    selection_seconds = time.perf_counter() - selection_started
    trial_seconds = time.perf_counter() - trial_started
    process_cpu_seconds = time.process_time() - cpu_started
    return {
        "mode": mode,
        "analyze_seconds": analyze_seconds,
        "cache_state": timing_recorder.cache_state,
        "cache_write_state": timing_recorder.cache_write_state,
        "phase_timings_seconds": timing_recorder.as_dict(),
        "selection_seconds": selection_seconds,
        "trial_seconds": trial_seconds,
        "process_cpu_seconds": process_cpu_seconds,
        "cpu_to_wall_ratio": (0.0 if trial_seconds <= 0.0 else process_cpu_seconds / trial_seconds),
        "peak_rss_bytes": _peak_rss_bytes(),
        "repetition": repetition,
        "order_index": order_index,
        "metrics": metrics,
        "windowed_metrics": windowed_metrics,
        "selection": _selection_with_offset(selection, source_offset),
        "window": {
            "start_frame": source_offset,
            "end_frame_exclusive": source_offset + windowed_metrics.metadata.frame_count,
        },
        "metadata": {
            "frame_count": metrics.metadata.frame_count,
            "performance_mode": metrics.metadata.performance_mode,
            "algorithm_id": metrics.metadata.algorithm_id,
            "metric_backend": metrics.metadata.metric_backend,
            "algorithm_identity": json.loads(metrics.metadata.algorithm_identity_json),
        },
    }


def _delete_tier_metrics_cache(
    *,
    video_paths: Sequence[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    selection_domain: str | None,
) -> None:
    cache_key = compute_cache_key(
        list(video_paths),
        config,
        selection_domain=selection_domain,
        metric_request=MetricCacheRequest(
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            metric_active_rect=active_rect.rect,
            active_rect_source=active_rect.source,
            active_rect_detection_mode=active_rect.detection_mode,
            active_rect_algorithm_id=active_rect.algorithm_id,
        ),
    )
    delete_metrics_cache_entry(cache_dir, cache_key)


def _aggregate_tier_trials(trials: Sequence[JsonObject]) -> JsonObject:
    if not trials:
        raise ValueError("Cannot aggregate an empty benchmark trial set")
    aggregate = dict(trials[0])
    trial_summaries = [_trial_result_summary(trial) for trial in trials]
    aggregate["trials"] = trial_summaries
    aggregate["timing_summary"] = _timing_summary(trial_summaries)
    analyze_distribution = aggregate["timing_summary"]["analyze_seconds"]
    aggregate["analyze_seconds"] = cast(JsonObject, analyze_distribution)["median"]
    cache_states: dict[str, int] = {}
    cache_write_states: dict[str, int] = {}
    for trial in trials:
        state = cast(str, trial["cache_state"])
        cache_states[state] = cache_states.get(state, 0) + 1
        write_state = cast(str, trial["cache_write_state"])
        cache_write_states[write_state] = cache_write_states.get(write_state, 0) + 1
    aggregate["cache_state"] = cache_states
    aggregate["cache_write_state"] = cache_write_states
    return aggregate


def _trial_result_summary(trial: JsonObject) -> JsonObject:
    return {
        "repetition": trial["repetition"],
        "order_index": trial["order_index"],
        "cache_state": trial["cache_state"],
        "cache_write_state": trial["cache_write_state"],
        "analyze_seconds": trial["analyze_seconds"],
        "selection_seconds": trial["selection_seconds"],
        "trial_seconds": trial["trial_seconds"],
        "process_cpu_seconds": trial["process_cpu_seconds"],
        "cpu_to_wall_ratio": trial["cpu_to_wall_ratio"],
        "peak_rss_bytes": trial["peak_rss_bytes"],
        "phase_timings_seconds": trial["phase_timings_seconds"],
    }


def _timing_summary(trials: Sequence[JsonObject]) -> JsonObject:
    summary: JsonObject = {}
    for field_name in (
        "analyze_seconds",
        "selection_seconds",
        "trial_seconds",
        "process_cpu_seconds",
        "cpu_to_wall_ratio",
    ):
        summary[field_name] = _distribution(
            [float(cast(float, trial[field_name])) for trial in trials]
        )

    phase_names = sorted(
        {
            phase
            for trial in trials
            for phase in cast(Mapping[str, float], trial["phase_timings_seconds"])
        }
    )
    summary["phase_timings_seconds"] = {
        phase: _distribution(
            [
                float(cast(Mapping[str, float], trial["phase_timings_seconds"]).get(phase, 0.0))
                for trial in trials
            ]
        )
        for phase in phase_names
    }
    return summary


def _distribution(values: Sequence[float]) -> JsonObject:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "pstdev": statistics.pstdev(values),
    }


def _peak_rss_bytes() -> int | None:
    if sys.platform == "win32":
        return None

    import resource

    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def _calculate_metrics_with_expected_active_rect(
    *,
    video_paths: Sequence[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    selection_domain: str | None,
    timing_recorder: AnalysisTimingRecorder | None = None,
) -> FrameMetrics:
    metrics = _calculate_metrics_once(
        video_paths=video_paths,
        config=config,
        cache_dir=cache_dir,
        analysis_source_path=analysis_source_path,
        effective_fps=effective_fps,
        active_rect=active_rect,
        selection_domain=selection_domain,
        timing_recorder=timing_recorder,
    )
    if _metrics_active_rect_metadata_matches(metrics, active_rect):
        return metrics

    cache_key = compute_cache_key(
        list(video_paths),
        config,
        selection_domain=selection_domain,
        metric_request=MetricCacheRequest(
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            metric_active_rect=active_rect.rect,
            active_rect_source=active_rect.source,
            active_rect_detection_mode=active_rect.detection_mode,
            active_rect_algorithm_id=active_rect.algorithm_id,
        ),
    )
    delete_metrics_cache_entry(cache_dir, cache_key)
    metrics = _calculate_metrics_once(
        video_paths=video_paths,
        config=config,
        cache_dir=cache_dir,
        analysis_source_path=analysis_source_path,
        effective_fps=effective_fps,
        active_rect=active_rect,
        selection_domain=selection_domain,
        timing_recorder=timing_recorder,
    )
    if _metrics_active_rect_metadata_matches(metrics, active_rect):
        return metrics

    raise SystemExit(
        "Benchmark analysis cache active-rect metadata does not match the requested "
        "benchmark active rectangle after recomputing. Remove the benchmark analysis "
        "cache entry and rerun."
    )


def _calculate_metrics_once(
    *,
    video_paths: Sequence[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    selection_domain: str | None,
    timing_recorder: AnalysisTimingRecorder | None = None,
) -> FrameMetrics:
    return calculate_metrics(
        list(video_paths),
        config,
        cache_dir,
        analysis_source_path=analysis_source_path,
        effective_fps=effective_fps,
        metric_active_rect=active_rect.rect,
        active_rect_source=active_rect.source,
        active_rect_detection_mode=active_rect.detection_mode,
        active_rect_algorithm_id=active_rect.algorithm_id,
        selection_domain=selection_domain,
        timing_recorder=timing_recorder,
    )


def _metrics_active_rect_metadata_matches(
    metrics: FrameMetrics,
    active_rect: BenchmarkActiveRect,
) -> bool:
    metadata = metrics.metadata
    return (
        metadata.metric_active_rect == active_rect.rect
        and metadata.active_rect_source == active_rect.source
        and metadata.active_rect_detection_mode == active_rect.detection_mode
        and metadata.active_rect_algorithm_id == active_rect.algorithm_id
    )


def _compare_tier(*, quality: JsonObject, candidate: JsonObject) -> JsonObject:
    quality_selection = cast(FrameSelection, quality["selection"])
    candidate_selection = cast(FrameSelection, candidate["selection"])
    quality_metrics = cast(FrameMetrics, quality["windowed_metrics"])
    candidate_metrics = cast(FrameMetrics, candidate["windowed_metrics"])
    mode = cast(str, candidate["mode"])
    categories: dict[SelectionCategory, tuple[Sequence[int], Sequence[int]]] = {
        "dark": (
            quality_selection.breakdown.quantile_dark,
            candidate_selection.breakdown.quantile_dark,
        ),
        "bright": (
            quality_selection.breakdown.quantile_bright,
            candidate_selection.breakdown.quantile_bright,
        ),
        "motion": (
            quality_selection.breakdown.motion,
            candidate_selection.breakdown.motion,
        ),
    }
    category_comparisons = {
        category: asdict(
            compare_selection_category(
                quality_frames=quality_frames,
                candidate_frames=candidate_frames,
                tolerance_frames=tier_category_tolerance(cast(Any, mode), category),
            )
        )
        for category, (quality_frames, candidate_frames) in categories.items()
    }
    ranking = compare_rankings(
        quality_luminance=quality_metrics.luminance,
        candidate_luminance=candidate_metrics.luminance,
        quality_motion=quality_metrics.motion,
        candidate_motion=candidate_metrics.motion,
        dark_count=len(quality_selection.breakdown.quantile_dark),
        bright_count=len(quality_selection.breakdown.quantile_bright),
        motion_count=len(quality_selection.breakdown.motion),
        source_offset=cast(dict[str, int], candidate["window"])["start_frame"],
    )
    return {
        "mode": mode,
        "analyze_seconds": candidate["analyze_seconds"],
        "cache_state": candidate["cache_state"],
        "cache_write_state": candidate.get("cache_write_state"),
        "timing_summary": candidate.get("timing_summary"),
        "trials": candidate.get("trials", []),
        "metadata": candidate["metadata"],
        "selected": _selected_summary(candidate_selection),
        "comparisons": category_comparisons,
        "ranking": asdict(ranking),
    }


def _tier_summary(tier: JsonObject) -> JsonObject:
    selection = cast(FrameSelection, tier["selection"])
    return {
        "analyze_seconds": tier["analyze_seconds"],
        "cache_state": tier["cache_state"],
        "cache_write_state": tier.get("cache_write_state"),
        "timing_summary": tier.get("timing_summary"),
        "trials": tier.get("trials", []),
        "metadata": tier["metadata"],
        "selected": _selected_summary(selection),
    }


def _selected_summary(selection: FrameSelection) -> JsonObject:
    return {
        "frames": list(selection.frames),
        "dark": list(selection.breakdown.quantile_dark),
        "bright": list(selection.breakdown.quantile_bright),
        "motion": list(selection.breakdown.motion),
        "random": list(selection.breakdown.random),
        "user": list(selection.breakdown.user),
    }


def _windowed_metrics(
    metrics: FrameMetrics,
    *,
    window_start: int,
    window_end_exclusive: int | None,
) -> tuple[FrameMetrics, int]:
    frame_count = metrics.metadata.frame_count
    end = frame_count if window_end_exclusive is None else min(window_end_exclusive, frame_count)
    start = min(window_start, end)
    return (
        FrameMetrics(
            luminance=metrics.luminance[start:end],
            motion=metrics.motion[start:end],
            metadata=replace(metrics.metadata, frame_count=end - start),
        ),
        start,
    )


def _config_for_window(
    config: AnalysisConfig,
    *,
    window_start: int,
    window_end: int,
) -> AnalysisConfig:
    return config.model_copy(
        update={
            "user_frames": [
                frame - window_start
                for frame in config.user_frames
                if window_start <= frame < window_end
            ]
        }
    )


def _selection_with_offset(selection: FrameSelection, source_offset: int) -> FrameSelection:
    breakdown = selection.breakdown
    return FrameSelection(
        frames=[frame + source_offset for frame in selection.frames],
        seed=selection.seed,
        breakdown=replace(
            breakdown,
            user=[frame + source_offset for frame in breakdown.user],
            quantile_dark=[frame + source_offset for frame in breakdown.quantile_dark],
            quantile_bright=[frame + source_offset for frame in breakdown.quantile_bright],
            motion=[frame + source_offset for frame in breakdown.motion],
            random=[frame + source_offset for frame in breakdown.random],
        ),
        selection_details={},
    )


if __name__ == "__main__":
    raise SystemExit(main())
