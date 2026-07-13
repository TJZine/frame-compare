#!/usr/bin/env python3
"""Benchmark analysis performance mode against quality on local clips."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.metric_strategies import (
    calculate_performance_planestats_metrics,
    calculate_quality_planestats_metrics,
)
from frame_compare.analysis.metrics import calculate_metrics, slice_frame_metrics
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.tier_validation import (
    SelectionCategory,
    TopKOverlap,
    compare_rankings,
    compare_selection_category,
    tier_category_tolerance,
)
from frame_compare.analysis.timing import AnalysisTimingRecorder, record_span
from frame_compare.analysis.types import (
    ActiveRectAlgorithmId,
    ActiveRectDetectionMode,
    ActiveRectSource,
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricActiveRect,
    MetricCacheRequest,
    MetricFrameRange,
    MetricsMetadata,
    SelectionBreakdown,
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
from frame_compare.vs.source import LWLibavSourceOptions, load_source

type JsonObject = dict[str, Any]
type MetricCachePolicy = Literal["cold", "reuse"]

FFPROBE_TIMEOUT_SECONDS = 120.0
QUALITY_PLANESTATS_CANDIDATE_MODE = "quality-planestats-candidate"
QUALITY_PLANESTATS_CANDIDATE_ALGORITHM_ID = "quality_fullres_planestats_candidate_v1"
QUALITY_PLANESTATS_CANDIDATE_BACKEND = "vapoursynth-planestats-fullres"
PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_MODE = "performance-skip-loop-filter-candidate"
PERFORMANCE_SKIP_LOOP_FILTER_MAX_THREADS_CANDIDATE_MODE = (
    "performance-skip-loop-filter-max-threads-candidate"
)
PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_ALGORITHM_ID = (
    "performance_320_planestats_skip_loop_filter_candidate_v1"
)
PERFORMANCE_SKIP_LOOP_FILTER_MAX_THREADS_CANDIDATE_ALGORITHM_ID = (
    "performance_320_planestats_skip_loop_filter_max_threads_candidate_v1"
)
PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_BACKEND = (
    "vapoursynth-planestats-320-lwlibavsource-skip-loop-filter"
)
NVIDIA_CUVID_CANDIDATE_MODE = "quality-nvidia-cuvid-candidate"
NVIDIA_CUVID_CANDIDATE_ALGORITHM_ID = "quality_fullres_planestats_nvidia_cuvid_requested_v1"
NVIDIA_CUVID_CANDIDATE_BACKEND = "vapoursynth-planestats-fullres-lwlibavsource-prefer-hw"
SPARSE_CANDIDATE_SPECS: dict[str, tuple[Fraction, bool]] = {
    "performance-sparse-25pct-candidate": (Fraction(1, 4), False),
    "performance-sparse-25pct-skip-loop-filter-candidate": (Fraction(1, 4), True),
    "performance-sparse-12_5pct-candidate": (Fraction(1, 8), False),
    "performance-sparse-12_5pct-skip-loop-filter-candidate": (Fraction(1, 8), True),
    "performance-sparse-6_25pct-candidate": (Fraction(1, 16), False),
    "performance-sparse-6_25pct-skip-loop-filter-candidate": (Fraction(1, 16), True),
}
SPARSE_CANDIDATE_MODES = frozenset(SPARSE_CANDIDATE_SPECS)
SPARSE_CANDIDATE_BACKEND = "vapoursynth-planestats-fullres-contiguous-bursts"
SPARSE_CANDIDATE_ALGORITHM_VERSION = "v1"
SPARSE_DEFAULT_BURST_COUNT = 8
BENCHMARK_ONLY_CANDIDATE_MODES = frozenset(
    {
        QUALITY_PLANESTATS_CANDIDATE_MODE,
        PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_MODE,
        PERFORMANCE_SKIP_LOOP_FILTER_MAX_THREADS_CANDIDATE_MODE,
        NVIDIA_CUVID_CANDIDATE_MODE,
        *SPARSE_CANDIDATE_MODES,
    }
)
PERFORMANCE_DECODER_CANDIDATE_MODES = frozenset(
    {
        PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_MODE,
        PERFORMANCE_SKIP_LOOP_FILTER_MAX_THREADS_CANDIDATE_MODE,
    }
)
PERFORMANCE_COMPARISON_MODES = frozenset({"performance", *PERFORMANCE_DECODER_CANDIDATE_MODES})
SKIP_LOOP_FILTER_FF_OPTIONS = "skip_loop_filter=all"
DENSE_EQUIVALENCE_RTOL = 0.0
DENSE_EQUIVALENCE_ATOL = 1e-12


class _FramesReadable(Protocol):
    num_frames: int

    def frames(self, *, close: bool = False) -> Iterator[object]: ...


class _PlaneStatsNamespace(Protocol):
    def PlaneStats(self) -> _FramesReadable: ...


class _PlaneStatsSource(Protocol):
    num_frames: int
    std: _PlaneStatsNamespace

    def __getitem__(self, key: slice) -> _PlaneStatsSource: ...


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
    source_frame_count: int | None = None
    source_fps: Fraction | None = None

    @property
    def reference_path(self) -> Path:
        return self.ordered_paths[0]


@dataclass(frozen=True, slots=True)
class SparseBurst:
    """One analyzed contiguous run and its optional motion-lookbehind frame."""

    start: int
    end_exclusive: int
    decode_start: int

    @property
    def frame_count(self) -> int:
        return self.end_exclusive - self.start


@dataclass(frozen=True, slots=True)
class SparseMetricSet:
    """Benchmark-only sparse metrics mapped to their source-frame coordinates."""

    luminance: tuple[float, ...]
    motion: tuple[float, ...]
    source_frames: tuple[int, ...]
    source_frame_count: int
    fps: Fraction
    window_start: int
    window_end_exclusive: int
    sampling_fraction: Fraction
    requested_burst_count: int
    bursts: tuple[SparseBurst, ...]
    mode: str
    algorithm_id: str
    metric_backend: str
    algorithm_identity_json: str

    def __post_init__(self) -> None:
        if not (len(self.luminance) == len(self.motion) == len(self.source_frames)):
            raise ValueError("Sparse metric arrays and source-frame map must have equal lengths")
        if tuple(sorted(set(self.source_frames))) != self.source_frames:
            raise ValueError("Sparse source-frame map must be sorted and unique")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
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
    nvidia_preflight = (
        _require_nvidia_preflight()
        if NVIDIA_CUVID_CANDIDATE_MODE in cast(Sequence[str], args.modes)
        else None
    )
    sparse_modes = [
        mode for mode in cast(Sequence[str], args.modes) if mode in SPARSE_CANDIDATE_MODES
    ]
    if args.window_end_exclusive is not None and analysis_source.source_frame_count is None:
        raise SystemExit(
            "An explicit benchmark window requires the selected source frame count from "
            "generated/clip_probe.toml. Run the normal preparation path, then rerun the benchmark."
        )
    if sparse_modes and analysis_source.source_frame_count is None:
        raise SystemExit(
            "Sparse analysis candidates require the selected source frame count from "
            "generated/clip_probe.toml. Run the normal preparation path, then rerun the benchmark."
        )
    if (
        args.window_end_exclusive is not None
        and analysis_source.source_frame_count is not None
        and args.window_end_exclusive > analysis_source.source_frame_count
    ):
        raise SystemExit(
            "--window-end-exclusive exceeds the selected analysis source frame count "
            f"({analysis_source.source_frame_count})."
        )
    _require_selection_coordinate_compatibility(analysis_source)
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
        source_frame_count=analysis_source.source_frame_count,
        sparse_burst_count=args.sparse_burst_count,
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
        window_start=args.window_start,
        window_end_exclusive=args.window_end_exclusive,
        source_fps=analysis_source.source_fps,
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
            "requested_modes": list(args.modes),
            "repetitions": args.repetitions,
            "trial_order_policy": "deterministic_rotation",
            "require_warm_source_index": args.require_warm_source_index,
            "sparse_burst_count": args.sparse_burst_count,
        },
        "runtime": _runtime_facts(),
        "nvidia_preflight": nvidia_preflight,
        "source": {
            "analysis_source": source_probe,
            "indexes": source_indexes,
        },
        "decode_baseline": decode_baseline,
        "quality": _tier_summary(quality),
        "comparisons": comparisons,
        "quality_planestats_candidate_timing_comparisons": (
            _quality_planestats_candidate_timing_comparisons(
                comparisons,
                requested_modes=cast(Sequence[str], args.modes),
            )
        ),
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
    window_start: int = 0,
    window_end_exclusive: int | None = None,
    source_fps: Fraction | None = None,
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
        frame_probe_options, inspection_scope = _frame_type_probe_options(
            window_start=window_start,
            window_end_exclusive=window_end_exclusive,
            source_fps=source_fps,
        )
        frame_payload = _run_ffprobe_json(
            frame_probe_options,
            path=path,
            timeout_seconds=timeout_seconds,
        )
        result["frame_type_inspection_seconds"] = time.perf_counter() - started
        result["frame_type_inspection_scope"] = inspection_scope
        result["frame_types"] = _frame_type_summary(frame_payload)
    return result


def _frame_type_probe_options(
    *,
    window_start: int,
    window_end_exclusive: int | None,
    source_fps: Fraction | None,
) -> tuple[list[str], JsonObject]:
    """Bound expensive frame decoding to the benchmark window when possible."""
    options = ["-select_streams", "v:0"]
    if window_end_exclusive is not None and source_fps is not None:
        start_seconds = Fraction(window_start, 1) / source_fps
        duration_seconds = Fraction(window_end_exclusive - window_start, 1) / source_fps
        read_interval = f"{float(start_seconds):.6f}%+{float(duration_seconds):.6f}"
        options.extend(["-read_intervals", read_interval])
        scope: JsonObject = {
            "kind": "benchmark-window",
            "start_frame": window_start,
            "end_frame_exclusive": window_end_exclusive,
            "source_fps": str(source_fps),
            "read_interval": read_interval,
        }
    else:
        scope = {"kind": "full-source"}
        if window_end_exclusive is not None:
            scope["fallback_reason"] = "source_fps_unavailable"
            scope["requested_start_frame"] = window_start
            scope["requested_end_frame_exclusive"] = window_end_exclusive
    options.extend(
        [
            "-show_frames",
            "-show_entries",
            "frame=key_frame,pict_type",
        ]
    )
    return options, scope


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
    if ffprobe_result.get("success") is not True:
        summary: JsonObject = {"available": False}
        error = ffprobe_result.get("error")
        if isinstance(error, str) and error:
            summary["error"] = error
        returncode = ffprobe_result.get("returncode")
        if isinstance(returncode, int):
            summary["returncode"] = returncode
        return summary
    payload = ffprobe_result.get("payload")
    if not isinstance(payload, Mapping):
        return {"available": False, "error": "ffprobe JSON root was not an object"}
    typed_payload = cast(Mapping[str, object], payload)
    frames_value = typed_payload.get("frames")
    if not isinstance(frames_value, list):
        return {"available": False, "error": "ffprobe JSON payload did not contain frames"}
    frames = cast(list[object], frames_value)

    type_counts: dict[str, int] = {}
    keyframe_indices: list[int] = []
    for index, raw_frame in enumerate(frames):
        if not isinstance(raw_frame, Mapping):
            continue
        typed_frame = cast(Mapping[str, object], raw_frame)
        pict_type = typed_frame.get("pict_type")
        if isinstance(pict_type, str):
            type_counts[pict_type] = type_counts.get(pict_type, 0) + 1
        if typed_frame.get("key_frame") == 1:
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
    prepared_clip = _prepared_benchmark_clip(
        root=root,
        input_paths=selection.ordered_paths,
        config=config,
        source_path=source_path,
        overrides_by_path=selection.overrides_by_path,
    )
    active_rect = _benchmark_active_rect_from_prepared_clip(
        source_path=source_path,
        override=override,
        prepared_clip=prepared_clip,
        config=config,
    )
    return BenchmarkAnalysisSource(
        path=source_path,
        ordered_paths=tuple(selection.ordered_paths),
        effective_fps=effective_fps,
        active_rect=active_rect,
        overrides_by_path=selection.overrides_by_path,
        source_frame_count=None if prepared_clip is None else prepared_clip.probe.num_frames,
        source_fps=None if prepared_clip is None else prepared_clip.probe.fps,
    )


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


def _require_selection_coordinate_compatibility(
    analysis_source: BenchmarkAnalysisSource,
) -> None:
    """Reject a benchmark domain whose selected-frame coordinates need translation."""
    analysis_override = analysis_source.overrides_by_path.get(analysis_source.path)
    reference_override = analysis_source.overrides_by_path.get(analysis_source.reference_path)
    analysis_trim_start = 0 if analysis_override is None else analysis_override.trim_start_frames
    reference_trim_start = 0 if reference_override is None else reference_override.trim_start_frames
    if analysis_trim_start == reference_trim_start:
        return
    raise SystemExit(
        "This benchmark cannot report production-equivalent selected source-frame numbers "
        "when the reference and analysis source have different trim_start_frames. Use the "
        "reference as the analysis source, align the trim starts for benchmarking, or extend "
        "the benchmark with explicit reference/analysis coordinate translation first."
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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
        choices=[
            "performance",
            QUALITY_PLANESTATS_CANDIDATE_MODE,
            PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_MODE,
            PERFORMANCE_SKIP_LOOP_FILTER_MAX_THREADS_CANDIDATE_MODE,
            NVIDIA_CUVID_CANDIDATE_MODE,
            *sorted(SPARSE_CANDIDATE_MODES),
        ],
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
        "--sparse-burst-count",
        type=int,
        default=SPARSE_DEFAULT_BURST_COUNT,
        help=(
            "Number of deterministic contiguous analysis bursts for sparse candidates "
            f"(default: {SPARSE_DEFAULT_BURST_COUNT})."
        ),
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
    args = parser.parse_args(argv)
    if args.modes is None:
        args.modes = ["performance"]
    cold_only_modes = [mode for mode in args.modes if mode in BENCHMARK_ONLY_CANDIDATE_MODES]
    if cold_only_modes and args.metric_cache_policy != "cold":
        parser.error(f"--mode {cold_only_modes[0]} requires --metric-cache-policy cold")
    if args.window_start < 0:
        parser.error("--window-start must be non-negative")
    if args.window_start > 0 and args.window_end_exclusive is None:
        parser.error("--window-start requires --window-end-exclusive when nonzero")
    if args.window_end_exclusive is not None and args.window_end_exclusive <= args.window_start:
        parser.error("--window-end-exclusive must be greater than --window-start")
    sparse_modes = [mode for mode in args.modes if mode in SPARSE_CANDIDATE_MODES]
    if sparse_modes and args.window_end_exclusive is None:
        parser.error(f"--mode {sparse_modes[0]} requires --window-end-exclusive")
    if sparse_modes and not args.inspect_frame_types:
        parser.error(
            f"--mode {sparse_modes[0]} requires --inspect-frame-types so the benchmark "
            "artifact records GOP/keyframe evidence"
        )
    if args.sparse_burst_count <= 0:
        parser.error("--sparse-burst-count must be positive")
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
    source_frame_count: int | None = None,
    sparse_burst_count: int = SPARSE_DEFAULT_BURST_COUNT,
    progress_enabled: bool,
    repetitions: int = 1,
    metric_cache_policy: MetricCachePolicy = "reuse",
) -> tuple[JsonObject, dict[str, JsonObject]]:
    cold_only_modes = [mode for mode in candidate_modes if mode in BENCHMARK_ONLY_CANDIDATE_MODES]
    if cold_only_modes and metric_cache_policy != "cold":
        raise ValueError(f"{cold_only_modes[0]} requires metric_cache_policy='cold'")
    if window_start > 0 and window_end_exclusive is None:
        raise ValueError("A nonzero benchmark window start requires an explicit window end")
    sparse_modes = [mode for mode in candidate_modes if mode in SPARSE_CANDIDATE_MODES]
    if window_end_exclusive is not None and source_frame_count is None:
        raise ValueError("An explicit benchmark window requires a source frame count")
    if sparse_modes and (window_end_exclusive is None or source_frame_count is None):
        raise ValueError(
            f"{sparse_modes[0]} requires an explicit window end and source frame count"
        )
    metric_frame_range = (
        MetricFrameRange(
            source_frame_count=source_frame_count,
            start=window_start,
            end_exclusive=window_end_exclusive,
        )
        if source_frame_count is not None and window_end_exclusive is not None
        else None
    )
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
                        metric_frame_range=metric_frame_range,
                        sparse_burst_count=sparse_burst_count,
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
    metric_frame_range: MetricFrameRange | None = None,
    sparse_burst_count: int = SPARSE_DEFAULT_BURST_COUNT,
    metric_cache_policy: MetricCachePolicy = "reuse",
    repetition: int = 0,
    order_index: int = 0,
) -> JsonObject:
    is_quality_planestats_candidate = mode == QUALITY_PLANESTATS_CANDIDATE_MODE
    is_performance_decoder_candidate = mode in PERFORMANCE_DECODER_CANDIDATE_MODES
    is_nvidia_candidate = mode == NVIDIA_CUVID_CANDIDATE_MODE
    is_sparse_candidate = mode in SPARSE_CANDIDATE_MODES
    is_benchmark_only_candidate = mode in BENCHMARK_ONLY_CANDIDATE_MODES
    runtime_mode = (
        "quality"
        if is_quality_planestats_candidate or is_nvidia_candidate
        else "performance"
        if is_performance_decoder_candidate or is_sparse_candidate
        else mode
    )
    tier_config = analysis_config.model_copy(
        update={"performance_mode": AnalysisPerformanceMode(runtime_mode)}
    )
    if metric_cache_policy == "cold" and not is_benchmark_only_candidate:
        _delete_tier_metrics_cache(
            video_paths=video_paths,
            config=tier_config,
            cache_dir=cache_dir,
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            active_rect=active_rect,
            selection_domain=selection_domain,
            metric_frame_range=metric_frame_range,
        )
    timing_recorder = AnalysisTimingRecorder()
    nvidia_utilization_before = _nvidia_decoder_utilization() if is_nvidia_candidate else None
    cpu_started = time.process_time()
    trial_started = time.perf_counter()
    started = time.perf_counter()
    sparse_metrics: SparseMetricSet | None = None
    decoder_evidence: JsonObject | None = None
    if is_sparse_candidate:
        if metric_frame_range is None:
            raise ValueError(f"{mode} requires an exact benchmark metric frame range")
        sparse_metrics = _calculate_sparse_candidate_trial_metrics(
            mode=mode,
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            active_rect=active_rect,
            metric_frame_range=metric_frame_range,
            burst_count=sparse_burst_count,
            timing_recorder=timing_recorder,
        )
        metrics = None
        cache_state = "bypassed"
        cache_write_state = "not-written"
    elif is_nvidia_candidate:
        metrics = _calculate_nvidia_candidate_trial_metrics(
            video_paths=video_paths,
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            active_rect=active_rect,
            metric_frame_range=metric_frame_range,
            timing_recorder=timing_recorder,
        )
        cache_state = "bypassed"
        cache_write_state = "not-written"
    elif is_quality_planestats_candidate:
        metrics = _calculate_quality_planestats_candidate_trial_metrics(
            video_paths=video_paths,
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            active_rect=active_rect,
            metric_frame_range=metric_frame_range,
            timing_recorder=timing_recorder,
        )
        cache_state = "bypassed"
        cache_write_state = "not-written"
    elif is_performance_decoder_candidate:
        metrics = _calculate_performance_decoder_candidate_trial_metrics(
            mode=mode,
            video_paths=video_paths,
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            active_rect=active_rect,
            metric_frame_range=metric_frame_range,
            timing_recorder=timing_recorder,
        )
        cache_state = "bypassed"
        cache_write_state = "not-written"
    else:
        metrics = _calculate_metrics_with_expected_active_rect(
            video_paths=video_paths,
            config=tier_config,
            cache_dir=cache_dir,
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            active_rect=active_rect,
            selection_domain=selection_domain,
            metric_frame_range=metric_frame_range,
            timing_recorder=timing_recorder,
        )
        cache_state = timing_recorder.cache_state
        cache_write_state = timing_recorder.cache_write_state
    analyze_seconds = time.perf_counter() - started
    phase_timings_seconds = timing_recorder.as_dict()
    compute_pipeline_seconds = _compute_pipeline_seconds(
        analyze_seconds=analyze_seconds,
        phase_timings_seconds=phase_timings_seconds,
    )
    selection_started = time.perf_counter()
    if sparse_metrics is not None:
        selection = _select_sparse_frames(sparse_metrics, tier_config)
        source_offset = sparse_metrics.window_start
        windowed_metrics = None
        window_end = sparse_metrics.window_end_exclusive
    else:
        assert metrics is not None
        windowed_metrics, source_offset = _windowed_metrics(
            metrics,
            window_start=window_start,
            window_end_exclusive=window_end_exclusive,
        )
        selection = select_frames(
            windowed_metrics,
            _config_for_window(
                tier_config,
                window_start=source_offset,
                window_end=source_offset + windowed_metrics.metadata.frame_count,
            ),
        )
        selection = _selection_with_offset(selection, source_offset)
        window_end = source_offset + windowed_metrics.metadata.frame_count
    selection_seconds = time.perf_counter() - selection_started
    trial_seconds = time.perf_counter() - trial_started
    process_cpu_seconds = time.process_time() - cpu_started
    if is_nvidia_candidate:
        decoder_evidence = _nvidia_decoder_evidence(
            utilization_before=nvidia_utilization_before,
            utilization_after=_nvidia_decoder_utilization(),
        )
    return {
        "mode": mode,
        "analyze_seconds": analyze_seconds,
        "compute_pipeline_seconds": compute_pipeline_seconds,
        "cache_state": cache_state,
        "cache_write_state": cache_write_state,
        "phase_timings_seconds": phase_timings_seconds,
        "selection_seconds": selection_seconds,
        "trial_seconds": trial_seconds,
        "process_cpu_seconds": process_cpu_seconds,
        "cpu_to_wall_ratio": (0.0 if trial_seconds <= 0.0 else process_cpu_seconds / trial_seconds),
        "peak_rss_bytes": _peak_rss_bytes(),
        "repetition": repetition,
        "order_index": order_index,
        "metrics": metrics,
        "windowed_metrics": windowed_metrics,
        "sparse_metrics": sparse_metrics,
        "selection": selection,
        "window": {
            "start_frame": source_offset,
            "end_frame_exclusive": window_end,
        },
        "metadata": _tier_metadata(metrics=metrics, sparse_metrics=sparse_metrics),
        "sampling": (None if sparse_metrics is None else _sparse_sampling_json(sparse_metrics)),
        "decoder_evidence": decoder_evidence,
    }


def _calculate_quality_planestats_candidate_trial_metrics(
    *,
    video_paths: Sequence[Path],
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    metric_frame_range: MetricFrameRange | None = None,
    timing_recorder: AnalysisTimingRecorder,
) -> FrameMetrics:
    with record_span(timing_recorder, "source_load"):
        source = DefaultVSLoader().load(analysis_source_path)
    metric_clip, has_lookbehind, resolved_range = _bounded_metric_clip(
        source.clip,
        metric_frame_range,
    )
    luminance, motion = calculate_quality_planestats_metrics(
        metric_clip,
        metric_active_rect=active_rect.rect,
        timing_recorder=timing_recorder,
    )
    if has_lookbehind:
        luminance = luminance[1:]
        motion = motion[1:]
    algorithm_identity_json = json.dumps(
        {
            "algorithm_id": QUALITY_PLANESTATS_CANDIDATE_ALGORITHM_ID,
            "backend": QUALITY_PLANESTATS_CANDIDATE_BACKEND,
            "benchmark_only": True,
            "luminance": "full_resolution_luma_planestats_average",
            "motion": "full_resolution_luma_planestats_diff_all_adjacent_pairs",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=resolved_range.frame_count,
            fps=effective_fps if effective_fps is not None else source.fps,
            config_fingerprint="benchmark-only-non-cacheable",
            clips=_benchmark_clip_identities(video_paths),
            source_frame_count=resolved_range.source_frame_count,
            metric_source_start=resolved_range.start,
            metric_source_end_exclusive=resolved_range.end_exclusive,
            analysis_source_path=str(analysis_source_path),
            performance_mode=QUALITY_PLANESTATS_CANDIDATE_MODE,
            algorithm_id=QUALITY_PLANESTATS_CANDIDATE_ALGORITHM_ID,
            metric_backend=QUALITY_PLANESTATS_CANDIDATE_BACKEND,
            algorithm_identity_json=algorithm_identity_json,
            metric_active_rect=active_rect.rect,
            active_rect_source=active_rect.source,
            active_rect_detection_mode=active_rect.detection_mode,
            active_rect_algorithm_id=active_rect.algorithm_id,
        ),
    )


def _calculate_performance_decoder_candidate_trial_metrics(
    *,
    mode: str,
    video_paths: Sequence[Path],
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    metric_frame_range: MetricFrameRange | None = None,
    timing_recorder: AnalysisTimingRecorder,
) -> FrameMetrics:
    if mode not in PERFORMANCE_DECODER_CANDIDATE_MODES:
        raise ValueError(f"Unsupported decoder benchmark candidate: {mode}")

    logical_threads: int | None = None
    thread_policy = "automatic"
    if mode == PERFORMANCE_SKIP_LOOP_FILTER_MAX_THREADS_CANDIDATE_MODE:
        logical_threads = os.cpu_count()
        if logical_threads is None or logical_threads <= 0:
            raise SystemExit(
                "The max-threads decoder candidate requires a positive logical CPU count, "
                "but os.cpu_count() did not provide one."
            )
        thread_policy = "explicit_logical_cpu_count"

    decoder_options = LWLibavSourceOptions(
        threads=logical_threads,
        ff_options=SKIP_LOOP_FILTER_FF_OPTIONS,
    )
    with record_span(timing_recorder, "source_load"):
        source = load_source(analysis_source_path, decoder_options=decoder_options)
    metric_clip, has_lookbehind, resolved_range = _bounded_metric_clip(
        source.clip,
        metric_frame_range,
    )
    luminance, motion = calculate_performance_planestats_metrics(
        metric_clip,
        metric_active_rect=active_rect.rect,
        timing_recorder=timing_recorder,
    )
    if has_lookbehind:
        luminance = luminance[1:]
        motion = motion[1:]
    algorithm_id = (
        PERFORMANCE_SKIP_LOOP_FILTER_MAX_THREADS_CANDIDATE_ALGORITHM_ID
        if logical_threads is not None
        else PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_ALGORITHM_ID
    )
    algorithm_identity_json = json.dumps(
        {
            "algorithm_id": algorithm_id,
            "backend": PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_BACKEND,
            "benchmark_only": True,
            "decoder": {
                "ff_options": SKIP_LOOP_FILTER_FF_OPTIONS,
                "source": "LWLibavSource",
                "thread_policy": thread_policy,
                "threads": logical_threads,
            },
            "luminance": "max_width_320_luma_planestats_average_all_frames",
            "motion": "max_width_320_luma_planestats_diff_all_adjacent_pairs",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=resolved_range.frame_count,
            fps=effective_fps if effective_fps is not None else source.fps,
            config_fingerprint="benchmark-only-non-cacheable",
            clips=_benchmark_clip_identities(video_paths),
            source_frame_count=resolved_range.source_frame_count,
            metric_source_start=resolved_range.start,
            metric_source_end_exclusive=resolved_range.end_exclusive,
            analysis_source_path=str(analysis_source_path),
            performance_mode=mode,
            algorithm_id=algorithm_id,
            metric_backend=PERFORMANCE_SKIP_LOOP_FILTER_CANDIDATE_BACKEND,
            algorithm_identity_json=algorithm_identity_json,
            metric_active_rect=active_rect.rect,
            active_rect_source=active_rect.source,
            active_rect_detection_mode=active_rect.detection_mode,
            active_rect_algorithm_id=active_rect.algorithm_id,
        ),
    )


def _bounded_metric_clip(
    clip: Any,
    metric_frame_range: MetricFrameRange | None,
) -> tuple[Any, bool, MetricFrameRange]:
    source_frame_count = clip.num_frames
    resolved_range = metric_frame_range or MetricFrameRange(
        source_frame_count=source_frame_count,
        start=0,
        end_exclusive=source_frame_count,
    )
    if resolved_range.source_frame_count != source_frame_count:
        raise ValueError("Benchmark metric range differs from the loaded source frame count")
    if resolved_range.start == 0 and resolved_range.end_exclusive == source_frame_count:
        return clip, False, resolved_range
    decode_start = max(0, resolved_range.start - 1)
    return (
        clip[decode_start : resolved_range.end_exclusive],
        resolved_range.start > 0,
        resolved_range,
    )


def _calculate_nvidia_candidate_trial_metrics(
    *,
    video_paths: Sequence[Path],
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    metric_frame_range: MetricFrameRange | None,
    timing_recorder: AnalysisTimingRecorder,
) -> FrameMetrics:
    """Request CUVID while reporting that L-SMASH may silently fall back to software."""
    with record_span(timing_recorder, "source_load"):
        source = load_source(
            analysis_source_path,
            decoder_options=LWLibavSourceOptions(prefer_hw=1),
        )
    metric_clip, has_lookbehind, resolved_range = _bounded_metric_clip(
        source.clip,
        metric_frame_range,
    )
    luminance, motion = calculate_quality_planestats_metrics(
        metric_clip,
        metric_active_rect=active_rect.rect,
        timing_recorder=timing_recorder,
    )
    if has_lookbehind:
        luminance = luminance[1:]
        motion = motion[1:]
    identity = {
        "algorithm_id": NVIDIA_CUVID_CANDIDATE_ALGORITHM_ID,
        "backend": NVIDIA_CUVID_CANDIDATE_BACKEND,
        "benchmark_only": True,
        "decoder_request": {"prefer_hw": 1, "requested_decoder": "nvidia_cuvid"},
        "effective_decoder_contract": "unverified_fallback_possible",
        "luminance": "full_resolution_luma_planestats_average",
        "motion": "full_resolution_luma_planestats_diff_with_window_lookbehind",
    }
    return FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=resolved_range.frame_count,
            fps=effective_fps if effective_fps is not None else source.fps,
            config_fingerprint="benchmark-only-non-cacheable",
            clips=_benchmark_clip_identities(video_paths),
            source_frame_count=resolved_range.source_frame_count,
            metric_source_start=resolved_range.start,
            metric_source_end_exclusive=resolved_range.end_exclusive,
            analysis_source_path=str(analysis_source_path),
            performance_mode=NVIDIA_CUVID_CANDIDATE_MODE,
            algorithm_id=NVIDIA_CUVID_CANDIDATE_ALGORITHM_ID,
            metric_backend=NVIDIA_CUVID_CANDIDATE_BACKEND,
            algorithm_identity_json=json.dumps(identity, sort_keys=True, separators=(",", ":")),
            metric_active_rect=active_rect.rect,
            active_rect_source=active_rect.source,
            active_rect_detection_mode=active_rect.detection_mode,
            active_rect_algorithm_id=active_rect.algorithm_id,
        ),
    )


def _nvidia_decoder_evidence(
    *,
    utilization_before: float | None,
    utilization_after: float | None,
) -> JsonObject:
    observed = any(
        value is not None and value > 0.0 for value in (utilization_before, utilization_after)
    )
    return {
        "requested_policy": "L-SMASH Works prefer_hw=1 (NVIDIA CUVID with software fallback)",
        "effective_decoder_proven": False,
        "verification_status": (
            "decoder_engine_activity_observed_unattributed" if observed else "requested_unverified"
        ),
        "decoder_utilization_percent_before": utilization_before,
        "decoder_utilization_percent_after": utilization_after,
        "telemetry_scope": "system-wide; not attributable to this process",
        "software_fallback_possible": True,
    }


def _require_nvidia_preflight() -> JsonObject:
    """Fail before timing when the host cannot establish an NVIDIA runtime."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(
            "The NVIDIA candidate requires a working nvidia-smi command before timed trials."
        ) from exc
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not lines:
        detail = result.stderr.strip() or "no GPU rows returned"
        raise SystemExit(f"NVIDIA preflight failed before timed trials: {detail}")
    gpus: list[JsonObject] = []
    for line in lines:
        name, separator, driver = line.rpartition(",")
        gpus.append(
            {
                "name": name.strip() if separator else line,
                "driver_version": driver.strip() if separator else None,
            }
        )
    return {
        "nvidia_smi_available": True,
        "gpus": gpus,
        "effective_decoder_proven": False,
        "note": (
            "GPU presence does not prove L-SMASH selected CUVID; prefer_hw=1 may fall "
            "back to software."
        ),
    }


def _nvidia_decoder_utilization() -> float | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.decoder",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    values: list[float] = []
    for line in result.stdout.splitlines():
        try:
            values.append(float(line.strip()))
        except ValueError:
            continue
    return max(values) if values else None


def _plan_sparse_bursts(
    *,
    window_start: int,
    window_end_exclusive: int,
    sampling_fraction: Fraction,
    requested_burst_count: int,
) -> tuple[SparseBurst, ...]:
    """Plan deterministic centered runs with an exact ceil-fraction frame budget."""
    window_length = window_end_exclusive - window_start
    if window_length <= 0:
        raise ValueError("Sparse analysis window must contain at least one frame")
    if not 0 < sampling_fraction <= 1:
        raise ValueError("Sparse sampling fraction must be within (0, 1]")
    if requested_burst_count <= 0:
        raise ValueError("Sparse burst count must be positive")

    budget = min(
        window_length,
        math.ceil(window_length * sampling_fraction.numerator / sampling_fraction.denominator),
    )
    burst_count = min(requested_burst_count, budget)
    base_size, larger_bursts = divmod(budget, burst_count)
    bursts: list[SparseBurst] = []
    for index in range(burst_count):
        stratum_start = window_start + window_length * index // burst_count
        stratum_end = window_start + window_length * (index + 1) // burst_count
        run_size = base_size + (1 if index < larger_bursts else 0)
        if run_size > stratum_end - stratum_start:
            raise ValueError("Sparse burst budget does not fit its deterministic stratum")
        start = stratum_start + (stratum_end - stratum_start - run_size) // 2
        bursts.append(
            SparseBurst(
                start=start,
                end_exclusive=start + run_size,
                decode_start=max(0, start - 1),
            )
        )
    return tuple(bursts)


def _calculate_sparse_candidate_trial_metrics(
    *,
    mode: str,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    metric_frame_range: MetricFrameRange,
    burst_count: int,
    timing_recorder: AnalysisTimingRecorder,
) -> SparseMetricSet:
    """Calculate full-resolution PlaneStats only for benchmark-planned bursts."""
    try:
        sampling_fraction, skip_loop_filter = SPARSE_CANDIDATE_SPECS[mode]
    except KeyError as exc:
        raise ValueError(f"Unsupported sparse benchmark candidate: {mode}") from exc

    decoder_options = (
        LWLibavSourceOptions(ff_options=SKIP_LOOP_FILTER_FF_OPTIONS) if skip_loop_filter else None
    )
    with record_span(timing_recorder, "source_load"):
        source = (
            load_source(analysis_source_path, decoder_options=decoder_options)
            if decoder_options is not None
            else DefaultVSLoader().load(analysis_source_path)
        )
    if source.clip.num_frames != metric_frame_range.source_frame_count:
        raise ValueError("Sparse benchmark source frame count differs from prepared probe metadata")

    bursts = _plan_sparse_bursts(
        window_start=metric_frame_range.start,
        window_end_exclusive=metric_frame_range.end_exclusive,
        sampling_fraction=sampling_fraction,
        requested_burst_count=burst_count,
    )
    luminance: list[float] = []
    motion: list[float] = []
    source_frames: list[int] = []
    for burst in bursts:
        burst_clip = source.clip[burst.decode_start : burst.end_exclusive]
        burst_luminance, burst_motion = calculate_quality_planestats_metrics(
            burst_clip,
            metric_active_rect=active_rect.rect,
            timing_recorder=timing_recorder,
        )
        if burst.decode_start < burst.start:
            burst_luminance = burst_luminance[1:]
            burst_motion = burst_motion[1:]
        if len(burst_luminance) != burst.frame_count or len(burst_motion) != burst.frame_count:
            raise ValueError("Sparse PlaneStats burst returned an unexpected metric count")
        luminance.extend(float(value) for value in burst_luminance)
        motion.extend(float(value) for value in burst_motion)
        source_frames.extend(range(burst.start, burst.end_exclusive))

    fraction_token = f"{sampling_fraction.numerator}_{sampling_fraction.denominator}"
    decoder_identity = (
        {"ff_options": SKIP_LOOP_FILTER_FF_OPTIONS, "source": "LWLibavSource"}
        if skip_loop_filter
        else {"ff_options": None, "source": "LWLibavSource"}
    )
    decoder_token = "skip_loop_filter" if skip_loop_filter else "default_decoder"
    algorithm_id = (
        f"performance_sparse_fullres_planestats_{fraction_token}_{burst_count}_bursts_"
        f"{decoder_token}_{SPARSE_CANDIDATE_ALGORITHM_VERSION}"
    )
    identity = {
        "algorithm_id": algorithm_id,
        "backend": SPARSE_CANDIDATE_BACKEND,
        "benchmark_only": True,
        "burst_count_requested": burst_count,
        "decoder": decoder_identity,
        "luminance": "full_resolution_luma_planestats_average_sampled_bursts",
        "motion": "full_resolution_luma_planestats_diff_with_per_burst_lookbehind",
        "sampling_fraction": str(sampling_fraction),
    }
    return SparseMetricSet(
        luminance=tuple(luminance),
        motion=tuple(motion),
        source_frames=tuple(source_frames),
        source_frame_count=metric_frame_range.source_frame_count,
        fps=effective_fps if effective_fps is not None else source.fps,
        window_start=metric_frame_range.start,
        window_end_exclusive=metric_frame_range.end_exclusive,
        sampling_fraction=sampling_fraction,
        requested_burst_count=burst_count,
        bursts=bursts,
        mode=mode,
        algorithm_id=algorithm_id,
        metric_backend=SPARSE_CANDIDATE_BACKEND,
        algorithm_identity_json=json.dumps(identity, sort_keys=True, separators=(",", ":")),
    )


def _select_sparse_frames(metrics: SparseMetricSet, config: AnalysisConfig) -> FrameSelection:
    """Apply analysis selection while keeping every exclusion/gap in source coordinates."""
    selected: set[int] = set()
    user = sorted(
        {
            frame
            for frame in config.user_frames
            if metrics.window_start <= frame < metrics.window_end_exclusive
        }
    )
    selected.update(user)
    sampled_luminance = list(zip(metrics.source_frames, metrics.luminance, strict=True))
    sampled_motion = list(zip(metrics.source_frames, metrics.motion, strict=True))

    dark = _select_sparse_quantile(
        sampled_luminance,
        count=config.dark_frame_count,
        exclude=selected,
        quantile=config.dark_quantile,
        largest=False,
    )
    selected.update(dark)
    bright = _select_sparse_quantile(
        sampled_luminance,
        count=config.bright_frame_count,
        exclude=selected,
        quantile=config.bright_quantile,
        largest=True,
    )
    selected.update(bright)
    motion = _select_sparse_motion(sampled_motion, config.motion_frame_count, selected)
    selected.update(motion)
    random_frames = _select_sparse_random(
        start=metrics.window_start,
        end_exclusive=metrics.window_end_exclusive,
        count=config.random_frame_count,
        seed=config.random_seed,
        exclude=selected,
    )
    selected.update(random_frames)

    requested = (
        len(user)
        + config.dark_frame_count
        + config.bright_frame_count
        + config.motion_frame_count
        + config.random_frame_count
    )
    if len(selected) < requested:
        raise SelectionError(
            reason="insufficient_candidates",
            requested=requested,
            found=len(selected),
        )
    return FrameSelection(
        frames=sorted(selected),
        seed=config.random_seed,
        breakdown=SelectionBreakdown(
            user=user,
            quantile_dark=dark,
            quantile_bright=bright,
            motion=motion,
            random=random_frames,
        ),
        selection_details={},
    )


def _select_sparse_quantile(
    values: Sequence[tuple[int, float]],
    *,
    count: int,
    exclude: set[int],
    quantile: float,
    largest: bool,
) -> list[int]:
    if count <= 0 or not values:
        return []
    ordered = sorted(values, key=lambda item: item[1])
    if largest:
        cutoff = min(len(ordered) - 1, int(len(ordered) * quantile))
        pool = [frame for frame, _value in ordered[cutoff:] if frame not in exclude]
        if len(pool) < count:
            pool = [frame for frame, _value in ordered if frame not in exclude][-count:]
    else:
        cutoff = max(1, int(len(ordered) * quantile))
        pool = [frame for frame, _value in ordered[:cutoff] if frame not in exclude]
        if len(pool) < count:
            pool = [frame for frame, _value in ordered if frame not in exclude][:count]
    return sorted(_sample_sparse_evenly(pool, count))


def _sample_sparse_evenly(items: Sequence[int], count: int) -> list[int]:
    if count <= 0:
        return []
    if len(items) <= count:
        return list(items)
    if count == 1:
        return [items[0]]
    last = len(items) - 1
    positions: list[int] = []
    for index in range(count):
        position = math.floor(index * last / (count - 1) + 0.5)
        if positions:
            position = max(position, positions[-1] + 1)
        position = min(position, last - (count - index - 1))
        positions.append(position)
    return [items[position] for position in positions]


def _select_sparse_motion(
    values: Sequence[tuple[int, float]],
    count: int,
    exclude: set[int],
) -> list[int]:
    selected: list[int] = []
    for frame, _value in sorted(values, key=lambda item: item[1], reverse=True):
        if len(selected) >= count:
            break
        if frame in exclude:
            continue
        if all(abs(frame - other) >= 5 for other in selected) and all(
            abs(frame - other) >= 5 for other in exclude
        ):
            selected.append(frame)
    return sorted(selected)


def _select_sparse_random(
    *,
    start: int,
    end_exclusive: int,
    count: int,
    seed: int,
    exclude: set[int],
) -> list[int]:
    candidates = sorted(
        range(start, end_exclusive),
        key=lambda frame: hashlib.blake2b(
            f"{seed}:{frame - start}".encode("ascii"), digest_size=16
        ).digest(),
    )
    selected: list[int] = []
    for frame in candidates:
        if len(selected) >= count:
            break
        if frame in exclude:
            continue
        if all(abs(frame - other) >= 5 for other in selected) and all(
            abs(frame - other) >= 5 for other in exclude
        ):
            selected.append(frame)
    return sorted(selected)


def _tier_metadata(
    *,
    metrics: FrameMetrics | None,
    sparse_metrics: SparseMetricSet | None,
) -> JsonObject:
    if sparse_metrics is not None:
        return {
            "frame_count": len(sparse_metrics.source_frames),
            "source_frame_count": sparse_metrics.source_frame_count,
            "performance_mode": sparse_metrics.mode,
            "algorithm_id": sparse_metrics.algorithm_id,
            "metric_backend": sparse_metrics.metric_backend,
            "algorithm_identity": json.loads(sparse_metrics.algorithm_identity_json),
        }
    if metrics is None:
        raise ValueError("Tier result is missing metric data")
    return {
        "frame_count": metrics.metadata.frame_count,
        "source_frame_count": metrics.metadata.source_frame_count,
        "performance_mode": metrics.metadata.performance_mode,
        "algorithm_id": metrics.metadata.algorithm_id,
        "metric_backend": metrics.metadata.metric_backend,
        "algorithm_identity": json.loads(metrics.metadata.algorithm_identity_json),
    }


def _sparse_sampling_json(metrics: SparseMetricSet) -> JsonObject:
    analyzed_count = len(metrics.source_frames)
    window_count = metrics.window_end_exclusive - metrics.window_start
    return {
        "sampling_fraction_requested": str(metrics.sampling_fraction),
        "sampling_fraction_actual": analyzed_count / window_count,
        "analyzed_frame_count": analyzed_count,
        "window_frame_count": window_count,
        "requested_burst_count": metrics.requested_burst_count,
        "actual_burst_count": len(metrics.bursts),
        "source_frames": list(metrics.source_frames),
        "bursts": [
            {
                "start_frame": burst.start,
                "end_frame_exclusive": burst.end_exclusive,
                "frame_count": burst.frame_count,
                "decode_start_frame": burst.decode_start,
                "lookbehind_frame": (
                    burst.decode_start if burst.decode_start < burst.start else None
                ),
            }
            for burst in metrics.bursts
        ],
    }


def _benchmark_clip_identities(video_paths: Sequence[Path]) -> list[ClipIdentity]:
    return [
        ClipIdentity(
            path=str(path),
            size=path.stat().st_size,
            mtime=path.stat().st_mtime,
        )
        for path in video_paths
    ]


def _delete_tier_metrics_cache(
    *,
    video_paths: Sequence[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    active_rect: BenchmarkActiveRect,
    selection_domain: str | None,
    metric_frame_range: MetricFrameRange | None = None,
) -> None:
    cache_key = compute_cache_key(
        list(video_paths),
        config,
        selection_domain=selection_domain,
        metric_request=MetricCacheRequest(
            analysis_source_path=analysis_source_path,
            metric_frame_range=metric_frame_range,
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
    compute_distribution = aggregate["timing_summary"]["compute_pipeline_seconds"]
    aggregate["compute_pipeline_seconds"] = cast(JsonObject, compute_distribution)["median"]
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
    summary = {
        "repetition": trial["repetition"],
        "order_index": trial["order_index"],
        "cache_state": trial["cache_state"],
        "cache_write_state": trial["cache_write_state"],
        "analyze_seconds": trial["analyze_seconds"],
        "compute_pipeline_seconds": trial["compute_pipeline_seconds"],
        "selection_seconds": trial["selection_seconds"],
        "trial_seconds": trial["trial_seconds"],
        "process_cpu_seconds": trial["process_cpu_seconds"],
        "cpu_to_wall_ratio": trial["cpu_to_wall_ratio"],
        "peak_rss_bytes": trial["peak_rss_bytes"],
        "phase_timings_seconds": trial["phase_timings_seconds"],
    }
    if trial.get("decoder_evidence") is not None:
        summary["decoder_evidence"] = trial["decoder_evidence"]
    return summary


def _timing_summary(trials: Sequence[JsonObject]) -> JsonObject:
    summary: JsonObject = {}
    for field_name in (
        "analyze_seconds",
        "compute_pipeline_seconds",
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


def _compute_pipeline_seconds(
    *,
    analyze_seconds: float,
    phase_timings_seconds: Mapping[str, float],
) -> float:
    persistence_seconds = phase_timings_seconds.get(
        "cache_lookup", 0.0
    ) + phase_timings_seconds.get("cache_write", 0.0)
    return max(0.0, analyze_seconds - persistence_seconds)


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


def _quality_planestats_candidate_timing_comparisons(
    comparisons: Mapping[str, JsonObject],
    *,
    requested_modes: Sequence[str],
) -> dict[str, JsonObject]:
    """Compare decoder candidates with the requested PlaneStats quality candidate."""
    if QUALITY_PLANESTATS_CANDIDATE_MODE not in requested_modes:
        return {}
    reference = comparisons.get(QUALITY_PLANESTATS_CANDIDATE_MODE)
    if reference is None:
        return {}

    result: dict[str, JsonObject] = {}
    for mode in requested_modes:
        if mode not in PERFORMANCE_COMPARISON_MODES:
            continue
        candidate = comparisons.get(mode)
        if candidate is None:
            continue
        result[mode] = _timing_comparison(
            reference_mode=QUALITY_PLANESTATS_CANDIDATE_MODE,
            reference=reference,
            candidate_mode=mode,
            candidate=candidate,
        )
    return result


def _timing_comparison(
    *,
    reference_mode: str,
    reference: JsonObject,
    candidate_mode: str,
    candidate: JsonObject,
) -> JsonObject:
    reference_distribution = cast(
        Mapping[str, float],
        cast(Mapping[str, object], reference["timing_summary"])["compute_pipeline_seconds"],
    )
    candidate_distribution = cast(
        Mapping[str, float],
        cast(Mapping[str, object], candidate["timing_summary"])["compute_pipeline_seconds"],
    )
    reference_median = float(reference_distribution["median"])
    candidate_median = float(candidate_distribution["median"])
    reference_pstdev = float(reference_distribution["pstdev"])
    candidate_pstdev = float(candidate_distribution["pstdev"])
    speedup = None if candidate_median <= 0.0 else reference_median / candidate_median
    percent_time_reduction = (
        None
        if reference_median <= 0.0
        else (reference_median - candidate_median) / reference_median * 100.0
    )
    median_delta = reference_median - candidate_median
    noise_band = max(reference_pstdev, candidate_pstdev)

    reference_by_repetition = {
        int(cast(int, trial["repetition"])): float(cast(float, trial["compute_pipeline_seconds"]))
        for trial in cast(Sequence[JsonObject], reference.get("trials", []))
    }
    candidate_by_repetition = {
        int(cast(int, trial["repetition"])): float(cast(float, trial["compute_pipeline_seconds"]))
        for trial in cast(Sequence[JsonObject], candidate.get("trials", []))
    }
    paired_repetitions = sorted(reference_by_repetition.keys() & candidate_by_repetition.keys())
    paired_faster_count = sum(
        candidate_by_repetition[repetition] < reference_by_repetition[repetition]
        for repetition in paired_repetitions
    )
    return {
        "reference_mode": reference_mode,
        "candidate_mode": candidate_mode,
        "timing_field": "compute_pipeline_seconds",
        "speedup": speedup,
        "percent_time_reduction": percent_time_reduction,
        "reference_median_seconds": reference_median,
        "candidate_median_seconds": candidate_median,
        "reference_minus_candidate_median_seconds": median_delta,
        "reference_pstdev_seconds": reference_pstdev,
        "candidate_pstdev_seconds": candidate_pstdev,
        "max_pstdev_noise_band_seconds": noise_band,
        "outside_noise_band": median_delta > noise_band,
        "paired_faster_count": paired_faster_count,
        "paired_count": len(paired_repetitions),
        "meets_1_5x_speedup": speedup is not None and speedup >= 1.5,
        "meets_2x_speedup": speedup is not None and speedup >= 2.0,
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
    metric_frame_range: MetricFrameRange | None = None,
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
        metric_frame_range=metric_frame_range,
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
            metric_frame_range=metric_frame_range,
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
        metric_frame_range=metric_frame_range,
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
    metric_frame_range: MetricFrameRange | None = None,
    timing_recorder: AnalysisTimingRecorder | None = None,
) -> FrameMetrics:
    return calculate_metrics(
        list(video_paths),
        config,
        cache_dir,
        analysis_source_path=analysis_source_path,
        effective_fps=effective_fps,
        metric_active_rect=active_rect.rect,
        metric_frame_range=metric_frame_range,
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
    if cast(str, candidate["mode"]) in SPARSE_CANDIDATE_MODES:
        return _compare_sparse_tier(quality=quality, candidate=candidate)
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
                tolerance_frames=_category_tolerance(mode, category),
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
        "compute_pipeline_seconds": candidate["compute_pipeline_seconds"],
        "cache_state": candidate["cache_state"],
        "cache_write_state": candidate.get("cache_write_state"),
        "decoder_evidence": candidate.get("decoder_evidence"),
        "timing_summary": candidate.get("timing_summary"),
        "trials": candidate.get("trials", []),
        "metadata": candidate["metadata"],
        "window": candidate["window"],
        "timing_comparison": _timing_comparison(
            reference_mode="quality",
            reference=quality,
            candidate_mode=mode,
            candidate=candidate,
        ),
        "selected": _selected_summary(candidate_selection),
        "comparisons": category_comparisons,
        "quality_category_retention": _quality_category_retention(
            quality_metrics=quality_metrics,
            candidate_selection=candidate_selection,
            source_offset=cast(dict[str, int], quality["window"])["start_frame"],
        ),
        "ranking": asdict(ranking),
        "dense_metric_differences": {
            "tolerance": {
                "rtol": DENSE_EQUIVALENCE_RTOL,
                "atol": DENSE_EQUIVALENCE_ATOL,
            },
            "luminance": _dense_metric_difference(
                quality_metrics.luminance,
                candidate_metrics.luminance,
                source_offset=cast(dict[str, int], candidate["window"])["start_frame"],
            ),
            "motion": _dense_metric_difference(
                quality_metrics.motion,
                candidate_metrics.motion,
                source_offset=cast(dict[str, int], candidate["window"])["start_frame"],
            ),
        },
        "exact_selected_equality": {
            category: list(quality_frames) == list(candidate_frames)
            for category, (quality_frames, candidate_frames) in categories.items()
        },
        "exact_top_k_ordering": {
            "dark": _exact_top_k_ordering(ranking.lowest_luminance_top_k),
            "bright": _exact_top_k_ordering(ranking.highest_luminance_top_k),
            "motion": _exact_top_k_ordering(ranking.highest_motion_top_k),
        },
    }


def _category_tolerance(mode: str, category: SelectionCategory) -> int:
    if mode in {QUALITY_PLANESTATS_CANDIDATE_MODE, NVIDIA_CUVID_CANDIDATE_MODE}:
        return 0
    if (
        mode == "performance"
        or mode in PERFORMANCE_DECODER_CANDIDATE_MODES
        or mode in SPARSE_CANDIDATE_MODES
    ):
        return tier_category_tolerance("performance", category)
    raise ValueError(f"Unsupported benchmark comparison mode: {mode}")


def _compare_sparse_tier(*, quality: JsonObject, candidate: JsonObject) -> JsonObject:
    quality_selection = cast(FrameSelection, quality["selection"])
    candidate_selection = cast(FrameSelection, candidate["selection"])
    quality_metrics = cast(FrameMetrics, quality["windowed_metrics"])
    sparse_metrics = cast(SparseMetricSet, candidate["sparse_metrics"])
    mode = cast(str, candidate["mode"])
    quality_offset = cast(dict[str, int], quality["window"])["start_frame"]
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
                tolerance_frames=_category_tolerance(mode, category),
            )
        )
        for category, (quality_frames, candidate_frames) in categories.items()
    }
    return {
        "mode": mode,
        "analyze_seconds": candidate["analyze_seconds"],
        "compute_pipeline_seconds": candidate["compute_pipeline_seconds"],
        "cache_state": candidate["cache_state"],
        "cache_write_state": candidate.get("cache_write_state"),
        "timing_summary": candidate.get("timing_summary"),
        "trials": candidate.get("trials", []),
        "metadata": candidate["metadata"],
        "window": candidate["window"],
        "sampling": candidate["sampling"],
        "timing_comparison": _timing_comparison(
            reference_mode="quality",
            reference=quality,
            candidate_mode=mode,
            candidate=candidate,
        ),
        "selected": _selected_summary(candidate_selection),
        "comparisons": category_comparisons,
        "quality_category_retention": _quality_category_retention(
            quality_metrics=quality_metrics,
            candidate_selection=candidate_selection,
            source_offset=quality_offset,
        ),
        "sampled_metric_fidelity": {
            "luminance": _sampled_metric_fidelity(
                quality_values=quality_metrics.luminance,
                candidate_values=sparse_metrics.luminance,
                sampled_source_frames=sparse_metrics.source_frames,
                quality_source_offset=quality_offset,
            ),
            "motion": _sampled_metric_fidelity(
                quality_values=quality_metrics.motion,
                candidate_values=sparse_metrics.motion,
                sampled_source_frames=sparse_metrics.source_frames,
                quality_source_offset=quality_offset,
            ),
        },
        "sampled_ranking": {
            "dark_luminance": _sampled_ranking_diagnostic(
                quality_values=quality_metrics.luminance,
                candidate_values=sparse_metrics.luminance,
                sampled_source_frames=sparse_metrics.source_frames,
                quality_source_offset=quality_offset,
                top_k=len(quality_selection.breakdown.quantile_dark),
                largest=False,
            ),
            "bright_luminance": _sampled_ranking_diagnostic(
                quality_values=quality_metrics.luminance,
                candidate_values=sparse_metrics.luminance,
                sampled_source_frames=sparse_metrics.source_frames,
                quality_source_offset=quality_offset,
                top_k=len(quality_selection.breakdown.quantile_bright),
                largest=True,
            ),
            "motion": _sampled_ranking_diagnostic(
                quality_values=quality_metrics.motion,
                candidate_values=sparse_metrics.motion,
                sampled_source_frames=sparse_metrics.source_frames,
                quality_source_offset=quality_offset,
                top_k=len(quality_selection.breakdown.motion),
                largest=True,
            ),
        },
        "quality_extreme_coverage": {
            "dark": _quality_extreme_coverage(
                quality_values=quality_metrics.luminance,
                sampled_source_frames=sparse_metrics.source_frames,
                source_offset=quality_offset,
                fraction=0.25,
                largest=False,
            ),
            "bright": _quality_extreme_coverage(
                quality_values=quality_metrics.luminance,
                sampled_source_frames=sparse_metrics.source_frames,
                source_offset=quality_offset,
                fraction=0.25,
                largest=True,
            ),
            "motion": _quality_extreme_coverage(
                quality_values=quality_metrics.motion,
                sampled_source_frames=sparse_metrics.source_frames,
                source_offset=quality_offset,
                fraction=0.20,
                largest=True,
            ),
        },
    }


def _sampled_metric_fidelity(
    *,
    quality_values: Sequence[float],
    candidate_values: Sequence[float],
    sampled_source_frames: Sequence[int],
    quality_source_offset: int,
) -> JsonObject:
    if len(candidate_values) != len(sampled_source_frames):
        raise ValueError("Sparse candidate values do not match the source-frame map")
    errors: list[float] = []
    first_outside_tolerance: int | None = None
    for source_frame, candidate in zip(sampled_source_frames, candidate_values, strict=True):
        quality_index = source_frame - quality_source_offset
        if not 0 <= quality_index < len(quality_values):
            raise ValueError("Sparse sample lies outside the quality metric window")
        quality = float(quality_values[quality_index])
        error = abs(float(candidate) - quality)
        errors.append(error)
        if first_outside_tolerance is None and not math.isclose(
            float(candidate),
            quality,
            rel_tol=DENSE_EQUIVALENCE_RTOL,
            abs_tol=DENSE_EQUIVALENCE_ATOL,
        ):
            first_outside_tolerance = source_frame
    return {
        "sample_count": len(errors),
        "max_absolute_error": max(errors, default=0.0),
        "mean_absolute_error": statistics.fmean(errors) if errors else 0.0,
        "first_outside_tolerance_source_frame": first_outside_tolerance,
        "allclose": first_outside_tolerance is None,
        "tolerance": {"rtol": DENSE_EQUIVALENCE_RTOL, "atol": DENSE_EQUIVALENCE_ATOL},
    }


def _sampled_ranking_diagnostic(
    *,
    quality_values: Sequence[float],
    candidate_values: Sequence[float],
    sampled_source_frames: Sequence[int],
    quality_source_offset: int,
    top_k: int,
    largest: bool,
) -> JsonObject:
    quality_sampled = [
        float(quality_values[source_frame - quality_source_offset])
        for source_frame in sampled_source_frames
    ]
    candidate_sampled = [float(value) for value in candidate_values]
    quality_order = sorted(
        range(len(sampled_source_frames)),
        key=lambda index: quality_sampled[index],
        reverse=largest,
    )
    candidate_order = sorted(
        range(len(sampled_source_frames)),
        key=lambda index: candidate_sampled[index],
        reverse=largest,
    )
    effective_k = min(max(0, top_k), len(sampled_source_frames))
    quality_top = [sampled_source_frames[index] for index in quality_order[:effective_k]]
    candidate_top = [sampled_source_frames[index] for index in candidate_order[:effective_k]]
    overlap = len(set(quality_top) & set(candidate_top))
    return {
        "direction": "highest" if largest else "lowest",
        "spearman": _spearman_correlation(quality_sampled, candidate_sampled),
        "top_k": effective_k,
        "quality_top_source_frames": quality_top,
        "candidate_top_source_frames": candidate_top,
        "top_k_overlap_count": overlap,
        "top_k_overlap_fraction": 1.0 if effective_k == 0 else overlap / effective_k,
    }


def _spearman_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_ranks = _average_ranks(left)
    right_ranks = _average_ranks(right)
    left_mean = statistics.fmean(left_ranks)
    right_mean = statistics.fmean(right_ranks)
    numerator = sum(
        (left_rank - left_mean) * (right_rank - right_mean)
        for left_rank, right_rank in zip(left_ranks, right_ranks, strict=True)
    )
    left_sum = sum((rank - left_mean) ** 2 for rank in left_ranks)
    right_sum = sum((rank - right_mean) ** 2 for rank in right_ranks)
    denominator = math.sqrt(left_sum * right_sum)
    return None if denominator == 0.0 else numerator / denominator


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[position]]:
            end += 1
        average_rank = (position + end - 1) / 2.0
        for ordered_index in ordered[position:end]:
            ranks[ordered_index] = average_rank
        position = end
    return ranks


def _quality_extreme_coverage(
    *,
    quality_values: Sequence[float],
    sampled_source_frames: Sequence[int],
    source_offset: int,
    fraction: float,
    largest: bool,
) -> JsonObject:
    extreme_count = max(1, math.ceil(len(quality_values) * fraction)) if quality_values else 0
    ordered = sorted(range(len(quality_values)), key=lambda index: quality_values[index])
    extreme_indices = ordered[-extreme_count:] if largest else ordered[:extreme_count]
    extreme_frames = [source_offset + index for index in extreme_indices]
    sampled = set(sampled_source_frames)
    covered = sorted(frame for frame in extreme_frames if frame in sampled)
    nearest_distances = [
        min((abs(frame - sampled_frame) for sampled_frame in sampled_source_frames), default=0)
        for frame in extreme_frames
    ]
    return {
        "quality_extreme_frame_count": len(extreme_frames),
        "sampled_extreme_frame_count": len(covered),
        "sampled_extreme_fraction": (
            1.0 if not extreme_frames else len(covered) / len(extreme_frames)
        ),
        "sampled_extreme_source_frames": covered,
        "nearest_sample_distance_frames": _distribution(
            [float(distance) for distance in nearest_distances]
        ),
    }


def _quality_category_retention(
    *,
    quality_metrics: FrameMetrics,
    candidate_selection: FrameSelection,
    source_offset: int,
) -> dict[SelectionCategory, JsonObject]:
    return {
        "dark": _category_retention_diagnostic(
            quality_values=quality_metrics.luminance,
            selected_source_frames=candidate_selection.breakdown.quantile_dark,
            source_offset=source_offset,
            fraction=0.25,
            largest=False,
        ),
        "bright": _category_retention_diagnostic(
            quality_values=quality_metrics.luminance,
            selected_source_frames=candidate_selection.breakdown.quantile_bright,
            source_offset=source_offset,
            fraction=0.25,
            largest=True,
        ),
        "motion": _category_retention_diagnostic(
            quality_values=quality_metrics.motion,
            selected_source_frames=candidate_selection.breakdown.motion,
            source_offset=source_offset,
            fraction=0.20,
            largest=True,
        ),
    }


def _category_retention_diagnostic(
    *,
    quality_values: Sequence[float],
    selected_source_frames: Sequence[int],
    source_offset: int,
    fraction: float,
    largest: bool,
) -> JsonObject:
    selected = list(selected_source_frames)
    threshold = _inclusive_extreme_threshold(
        quality_values,
        fraction=fraction,
        largest=largest,
    )
    passing: list[int] = []
    if threshold is not None:
        for source_frame in selected:
            metric_index = source_frame - source_offset
            if not 0 <= metric_index < len(quality_values):
                continue
            value = float(quality_values[metric_index])
            passes_threshold = value >= threshold if largest else value <= threshold
            if passes_threshold:
                passing.append(source_frame)
    total_count = len(selected)
    passing_count = len(passing)
    return {
        "threshold": threshold,
        "selected_source_frames": selected,
        "passing_source_frames": passing,
        "passing_count": passing_count,
        "passing_fraction": 1.0 if total_count == 0 else passing_count / total_count,
        "total_count": total_count,
        "required_fraction": 1.0,
    }


def _inclusive_extreme_threshold(
    values: Sequence[float],
    *,
    fraction: float,
    largest: bool,
) -> float | None:
    if not values:
        return None
    count = max(1, math.ceil(len(values) * fraction))
    ordered = sorted(float(value) for value in values)
    return ordered[-count] if largest else ordered[count - 1]


def _tier_summary(tier: JsonObject) -> JsonObject:
    selection = cast(FrameSelection, tier["selection"])
    return {
        "analyze_seconds": tier["analyze_seconds"],
        "compute_pipeline_seconds": tier["compute_pipeline_seconds"],
        "cache_state": tier["cache_state"],
        "cache_write_state": tier.get("cache_write_state"),
        "timing_summary": tier.get("timing_summary"),
        "trials": tier.get("trials", []),
        "metadata": tier["metadata"],
        "window": tier["window"],
        "selected": _selected_summary(selection),
        "sampling": tier.get("sampling"),
    }


def _dense_metric_difference(
    quality_values: Sequence[float],
    candidate_values: Sequence[float],
    *,
    source_offset: int,
) -> JsonObject:
    if len(quality_values) != len(candidate_values):
        raise ValueError(
            "dense metric comparison requires matching lengths: "
            f"quality={len(quality_values)}, candidate={len(candidate_values)}"
        )
    absolute_errors = [
        abs(float(candidate) - float(quality))
        for quality, candidate in zip(quality_values, candidate_values, strict=True)
    ]
    first_differing_index = next(
        (
            index
            for index, (quality, candidate) in enumerate(
                zip(quality_values, candidate_values, strict=True)
            )
            if float(quality) != float(candidate)
        ),
        None,
    )
    first_outside_tolerance_index = next(
        (
            index
            for index, (quality, candidate) in enumerate(
                zip(quality_values, candidate_values, strict=True)
            )
            if not math.isclose(
                float(quality),
                float(candidate),
                rel_tol=DENSE_EQUIVALENCE_RTOL,
                abs_tol=DENSE_EQUIVALENCE_ATOL,
            )
        ),
        None,
    )
    return {
        "max_absolute_error": max(absolute_errors, default=0.0),
        "mean_absolute_error": statistics.fmean(absolute_errors) if absolute_errors else 0.0,
        "first_differing_index": first_differing_index,
        "first_differing_source_frame": (
            None if first_differing_index is None else source_offset + first_differing_index
        ),
        "first_outside_tolerance_index": first_outside_tolerance_index,
        "first_outside_tolerance_source_frame": (
            None
            if first_outside_tolerance_index is None
            else source_offset + first_outside_tolerance_index
        ),
        "allclose": first_outside_tolerance_index is None,
    }


def _exact_top_k_ordering(top_k: TopKOverlap) -> JsonObject:
    quality_indices = list(top_k.quality_indices)
    candidate_indices = list(top_k.candidate_indices)
    return {
        "quality_indices": quality_indices,
        "candidate_indices": candidate_indices,
        "equal": quality_indices == candidate_indices,
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
    metadata = metrics.metadata
    requested_end = (
        metadata.metric_source_end_exclusive
        if window_end_exclusive is None
        else window_end_exclusive
    )
    if (
        metadata.metric_source_start == window_start
        and metadata.metric_source_end_exclusive == requested_end
    ):
        return metrics, metadata.metric_source_start
    if window_start < metadata.metric_source_start or requested_end > (
        metadata.metric_source_end_exclusive
    ):
        raise ValueError("Requested benchmark window lies outside the metric source range")
    local_start = window_start - metadata.metric_source_start
    return (
        slice_frame_metrics(
            metrics,
            start_index=local_start,
            frame_count=requested_end - window_start,
        ),
        window_start,
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
