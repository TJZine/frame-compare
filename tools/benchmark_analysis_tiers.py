#!/usr/bin/env python3
"""Benchmark the production analysis modes on a fixed local source window."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
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
from frame_compare.analysis.sampling import plan_performance_bursts
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.tier_validation import (
    SelectionCategory,
    compare_selection_category,
    tier_category_tolerance,
)
from frame_compare.analysis.timing import (
    AnalysisCacheState,
    AnalysisCacheWriteState,
    AnalysisTimingRecorder,
)
from frame_compare.analysis.types import (
    ActiveRectAlgorithmId,
    ActiveRectDetectionMode,
    ActiveRectSource,
    FrameMetrics,
    FrameSelection,
    MetricActiveRect,
    MetricCacheRequest,
    MetricFrameRange,
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
from frame_compare.orchestration.preflight import resolve_paths
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
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.child_environment import diagnostic_secrets, sanitize_diagnostic
from frame_compare.utils.subproc import SubprocessOutputLimitExceeded, run_subprocess
from frame_compare.vs.errors import SourceLoadError
from frame_compare.vs.loader import DefaultVSLoader
from frame_compare.vs.source_index_cache import ManagedSourceIndexCache

type JsonObject = dict[str, Any]
type MetricCachePolicy = Literal["cold", "reuse"]

FFPROBE_TIMEOUT_SECONDS = 120.0
_GIT_STDOUT_BYTES = 64 * 1024
_VERSION_STDOUT_BYTES = 16 * 1024
_TEXT_STDERR_BYTES = 8 * 1024
_METADATA_STDOUT_BYTES = 256 * 1024
_FFPROBE_STDERR_BYTES = 64 * 1024
# One million frames covers over 4.6 hours at 60 fps. The same cap applies
# to windowed and full-source scans, independent of metadata and requested duration.
_FRAME_SCAN_MAX_ROWS = 1_000_000
_FRAME_ROW_MAX_BYTES = 40  # Excluding LF. Includes the timestamp and empty side-data fields.
_FRAME_SCAN_STDOUT_BYTES = _FRAME_SCAN_MAX_ROWS * (_FRAME_ROW_MAX_BYTES + 1)
_FRAME_ROW = re.compile(rb"([01]),(-?[0-9]+\.[0-9]+|N/A),([IPBSipb?]),*\r?")


class _FramesReadable(Protocol):
    def frames(self, *, close: bool = False) -> Iterator[object]: ...


class _PlaneStatsNamespace(Protocol):
    def PlaneStats(self) -> _FramesReadable: ...


class _PlaneStatsSource(Protocol):
    std: _PlaneStatsNamespace


@dataclass(frozen=True, slots=True)
class BenchmarkActiveRect:
    """Prepared analysis rectangle and its cache provenance."""

    rect: MetricActiveRect | None
    source: ActiveRectSource
    detection_mode: ActiveRectDetectionMode
    algorithm_id: ActiveRectAlgorithmId = ACTIVE_RECT_RESOLUTION_ALGORITHM


@dataclass(frozen=True, slots=True)
class BenchmarkAnalysisSource:
    """Resolved source and prepared facts required by production metric analysis."""

    path: Path
    ordered_paths: tuple[Path, ...]
    effective_fps: Fraction | None
    reference_fps: Fraction | None
    effective_frame_count: int | None
    trim_start_frames: int
    active_rect: BenchmarkActiveRect
    overrides_by_path: Mapping[Path, SourceOverrideConfig]
    source_frame_count: int | None = None
    source_fps: Fraction | None = None

    @property
    def reference_path(self) -> Path:
        return self.ordered_paths[0]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    output_path = args.output if args.output.is_absolute() else root / args.output
    input_paths = tuple(
        path if path.is_absolute() else root / path for path in cast(Sequence[Path], args.inputs)
    )
    _reject_output_collisions(
        output_path=output_path,
        input_paths=input_paths,
        config_path=config_path,
    )
    config = load_config(config_path)
    input_dir = _resolve_config_path(root, config.paths.input_dir)
    cache_dir = args.cache_dir or (
        _resolve_config_path(root, config.paths.generated_dir) / "cache" / "analysis"
    )
    if not cache_dir.is_absolute():
        cache_dir = root / cache_dir

    analysis_source = _resolve_benchmark_analysis_source(
        root=root,
        input_dir=input_dir,
        input_paths=input_paths,
        config=config,
    )
    if analysis_source.source_frame_count is None:
        raise SystemExit(
            "An explicit production benchmark requires the selected source frame count "
            "from generated/clip_probe.toml. Run the normal preparation path first."
        )
    if (
        analysis_source.effective_fps is None
        or analysis_source.reference_fps is None
        or analysis_source.effective_frame_count is None
    ):
        raise SystemExit(
            "An explicit production benchmark requires prepared FPS and trim facts. "
            "Run the normal preparation path first."
        )
    if args.window_end_exclusive > analysis_source.effective_frame_count:
        raise SystemExit(
            "--window-end-exclusive exceeds the selected prepared analysis frame count "
            f"({analysis_source.effective_frame_count})."
        )
    _require_selection_coordinate_compatibility(analysis_source)
    _require_selection_domain_for_analysis_cache_identity(
        selection_domain=args.selection_domain,
        video_paths=input_paths,
        analysis_source=analysis_source,
        active_rect_detection=config.screenshots.active_rect_detection,
    )

    index_cache = ManagedSourceIndexCache(resolve_paths(config, root).generated_root)
    vs_loader = DefaultVSLoader(
        memory_limit_mb=config.runtime.memory_limit_mb, index_cache=index_cache
    )
    source_indexes = _source_index_facts(analysis_source.ordered_paths, index_cache)
    selected_index = source_indexes[analysis_source.path.as_posix()]
    if args.require_warm_source_index:
        if not selected_index["detected"]:
            raise SystemExit(
                "A warm source index was required but no Frame Compare-owned, "
                "runtime-versioned L-SMASH-Works index passed validation for "
                f"{analysis_source.path.as_posix()}"
            )
        try:
            vs_loader.load(analysis_source.path)
        except SourceLoadError as error:
            raise SystemExit(f"The required warm source index is not ready: {error}") from error

    metric_range = MetricFrameRange(
        source_frame_count=analysis_source.source_frame_count,
        start=analysis_source.trim_start_frames + args.window_start,
        end_exclusive=analysis_source.trim_start_frames + args.window_end_exclusive,
    )
    quality, performance = _run_benchmark(
        video_paths=analysis_source.ordered_paths,
        analysis_config=config.analysis,
        cache_dir=cache_dir,
        analysis_source_path=analysis_source.path,
        effective_fps=analysis_source.effective_fps,
        reference_fps=analysis_source.reference_fps,
        active_rect=analysis_source.active_rect,
        selection_domain=args.selection_domain,
        metric_frame_range=metric_range,
        progress_enabled=not args.no_progress,
        repetitions=args.repetitions,
        metric_cache_policy=cast(MetricCachePolicy, args.metric_cache_policy),
        vs_loader=vs_loader,
    )
    comparison = _compare_modes(quality=quality, performance=performance, config=config.analysis)
    source_probe = _probe_source_facts(
        analysis_source.path,
        inspect_frame_types=args.inspect_frame_types,
        timeout_seconds=args.ffprobe_timeout,
        window_start=metric_range.start,
        window_end_exclusive=metric_range.end_exclusive,
        source_fps=analysis_source.source_fps,
    )
    warnings: list[str] = []
    if args.selection_domain is None:
        warnings.append(
            "selection_domain is null; this is fixed-window algorithm evidence, not "
            "complete production cache-domain proof for trims or source overrides."
        )
    if not args.inspect_frame_types:
        warnings.append("Frame-type inspection was not requested.")

    report: JsonObject = {
        "schema_version": 2,
        "provenance": _git_provenance(root),
        "inputs": [path.as_posix() for path in analysis_source.ordered_paths],
        "config": {
            "config_path": config_path.as_posix(),
            "analysis_source": config.sources.analysis_source,
            "analysis_source_path": analysis_source.path.as_posix(),
            "effective_fps": (
                None
                if analysis_source.effective_fps is None
                else str(analysis_source.effective_fps)
            ),
            "metric_active_rect": _metric_active_rect_json(analysis_source.active_rect.rect),
            "active_rect_source": analysis_source.active_rect.source,
            "active_rect_detection_mode": analysis_source.active_rect.detection_mode,
            "active_rect_algorithm_id": analysis_source.active_rect.algorithm_id,
            "selection_window": {
                "start_frame": metric_range.start,
                "end_frame_exclusive": metric_range.end_exclusive,
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
        "source": {"analysis_source": source_probe, "indexes": source_indexes},
        "decode_baseline": (
            None
            if args.skip_decode_baseline
            else _run_decode_baseline(
                analysis_source_path=analysis_source.path, vs_loader=vs_loader
            )
        ),
        "quality": _tier_summary(quality),
        "comparisons": {"performance": comparison},
        "warnings": warnings,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        output_path,
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output_path.as_posix())
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare production performance analysis against quality and write JSON."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Input videos in run order.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Workspace root.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/config.toml"),
        help="Config TOML path, relative to root unless absolute.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path.")
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument(
        "--selection-domain",
        default=None,
        help="Optional prepared orchestration selection-domain token for cache identity.",
    )
    parser.add_argument(
        "--window-start",
        type=int,
        default=0,
        help="Inclusive start in the prepared analysis clip after source trims.",
    )
    parser.add_argument(
        "--window-end-exclusive",
        type=int,
        required=True,
        help=(
            "Exclusive end in the prepared analysis clip after source trims; "
            "reported ranges remain source-frame coordinates."
        ),
    )
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--metric-cache-policy", choices=["cold", "reuse"], default="cold")
    parser.add_argument("--require-warm-source-index", action="store_true")
    parser.add_argument("--skip-decode-baseline", action="store_true")
    parser.add_argument("--inspect-frame-types", action="store_true")
    parser.add_argument("--ffprobe-timeout", type=float, default=FFPROBE_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    if args.window_start < 0:
        parser.error("--window-start must be non-negative")
    if args.window_end_exclusive <= args.window_start:
        parser.error("--window-end-exclusive must be greater than --window-start")
    if args.repetitions <= 0:
        parser.error("--repetitions must be positive")
    if args.ffprobe_timeout <= 0:
        parser.error("--ffprobe-timeout must be positive")
    return args


def _reject_output_collisions(
    *, output_path: Path, input_paths: Sequence[Path], config_path: Path
) -> None:
    """Reject destructive report destinations before preparation or trials."""
    collisions = [
        path for path in (*input_paths, config_path) if _paths_identify_same_file(output_path, path)
    ]
    if collisions:
        output_resolved = output_path.resolve()
        names = ", ".join(path.as_posix() for path in collisions)
        raise SystemExit(
            "--output must not resolve to an input or the selected config: "
            f"{output_resolved.as_posix()} ({names})"
        )


def _paths_identify_same_file(left: Path, right: Path) -> bool:
    """Match lexical aliases and existing-file identities without hiding I/O errors."""
    if left.resolve() == right.resolve():
        return True
    try:
        left_stat = left.stat()
        right_stat = right.stat()
    except FileNotFoundError:
        return False
    return os.path.samestat(left_stat, right_stat)


def _run_benchmark(
    *,
    video_paths: Sequence[Path],
    analysis_config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    reference_fps: Fraction,
    active_rect: BenchmarkActiveRect,
    selection_domain: str | None,
    metric_frame_range: MetricFrameRange,
    progress_enabled: bool,
    repetitions: int,
    metric_cache_policy: MetricCachePolicy,
    vs_loader: DefaultVSLoader,
) -> tuple[JsonObject, JsonObject]:
    trials: dict[str, list[JsonObject]] = {"quality": [], "performance": []}
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=Console(stderr=True),
        disable=not progress_enabled,
    )
    with progress:
        task = progress.add_task("Starting analysis benchmark", total=repetitions * 2)
        for repetition in range(repetitions):
            for order_index, mode in enumerate(_rotated_trial_order(repetition)):
                progress.update(
                    task,
                    description=f"Running {mode} ({repetition + 1}/{repetitions})",
                )
                trials[mode].append(
                    _run_tier(
                        mode=mode,
                        video_paths=video_paths,
                        analysis_config=analysis_config,
                        cache_dir=cache_dir,
                        analysis_source_path=analysis_source_path,
                        effective_fps=effective_fps,
                        reference_fps=reference_fps,
                        active_rect=active_rect,
                        selection_domain=selection_domain,
                        metric_frame_range=metric_frame_range,
                        metric_cache_policy=metric_cache_policy,
                        repetition=repetition,
                        order_index=order_index,
                        vs_loader=vs_loader,
                    )
                )
                progress.advance(task)
        progress.update(task, description="Analysis benchmark complete")
    return _aggregate_tier_trials(trials["quality"]), _aggregate_tier_trials(trials["performance"])


def _rotated_trial_order(repetition: int) -> tuple[str, str]:
    return ("quality", "performance") if repetition % 2 == 0 else ("performance", "quality")


def _run_tier(
    *,
    mode: str,
    video_paths: Sequence[Path],
    analysis_config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    reference_fps: Fraction,
    active_rect: BenchmarkActiveRect,
    selection_domain: str | None,
    metric_frame_range: MetricFrameRange,
    metric_cache_policy: MetricCachePolicy,
    repetition: int,
    order_index: int,
    vs_loader: DefaultVSLoader | None = None,
) -> JsonObject:
    tier_config = analysis_config.model_copy(
        update={"performance_mode": AnalysisPerformanceMode(mode)}
    )
    metric_request = MetricCacheRequest(
        analysis_source_path=analysis_source_path,
        metric_frame_range=metric_frame_range,
        effective_fps=effective_fps,
        metric_active_rect=active_rect.rect,
        active_rect_source=active_rect.source,
        active_rect_detection_mode=active_rect.detection_mode,
        active_rect_algorithm_id=active_rect.algorithm_id,
    )
    if metric_cache_policy == "cold":
        _delete_tier_metrics_cache(
            metric_request,
            video_paths=video_paths,
            config=tier_config,
            cache_dir=cache_dir,
            selection_domain=selection_domain,
        )
    recorder = AnalysisTimingRecorder()
    cpu_started = time.process_time()
    trial_started = time.perf_counter()
    analyze_started = time.perf_counter()
    acquisition = calculate_metrics(
        metric_request,
        selection_domain=selection_domain,
        timing_recorder=recorder,
        video_paths=list(video_paths),
        config=tier_config,
        cache_dir=cache_dir,
        vs_loader=vs_loader,
    )
    metrics = acquisition.metrics
    analyze_seconds = time.perf_counter() - analyze_started
    _require_cache_policy(
        policy=metric_cache_policy,
        mode=mode,
        cache_state=recorder.cache_state,
        cache_write_state=recorder.cache_write_state,
    )
    _require_metric_contract(metrics, mode=mode, expected_range=metric_frame_range)
    selection_started = time.perf_counter()
    selection = select_frames(
        metrics,
        _config_for_window(
            tier_config,
            window_start=metric_frame_range.start,
            window_end=metric_frame_range.end_exclusive,
        ),
        selection_fps=reference_fps,
    )
    selection = _selection_with_offset(selection, metric_frame_range.start)
    selection_seconds = time.perf_counter() - selection_started
    trial_seconds = time.perf_counter() - trial_started
    process_cpu_seconds = time.process_time() - cpu_started
    phase_timings = recorder.as_dict()
    return {
        "mode": mode,
        "analyze_seconds": analyze_seconds,
        "compute_pipeline_seconds": _compute_pipeline_seconds(analyze_seconds, phase_timings),
        "selection_seconds": selection_seconds,
        "trial_seconds": trial_seconds,
        "process_cpu_seconds": process_cpu_seconds,
        "cpu_to_wall_ratio": 0.0 if trial_seconds <= 0 else process_cpu_seconds / trial_seconds,
        "peak_rss_bytes": _peak_rss_bytes(),
        "cache_state": recorder.cache_state,
        "cache_write_state": recorder.cache_write_state,
        "phase_timings_seconds": phase_timings,
        "repetition": repetition,
        "order_index": order_index,
        "metrics": metrics,
        "selection": selection,
        "metadata": _metrics_metadata_json(metrics),
        "sampling": _sampling_json(metrics),
    }


def _require_metric_contract(
    metrics: FrameMetrics, *, mode: str, expected_range: MetricFrameRange
) -> None:
    metadata = metrics.metadata
    if (
        metadata.performance_mode != mode
        or metadata.source_frame_count != expected_range.source_frame_count
        or metadata.metric_source_start != expected_range.start
        or metadata.metric_source_end_exclusive != expected_range.end_exclusive
    ):
        raise RuntimeError(f"{mode} metrics do not match the requested production domain")
    if mode == "quality" and metrics.sampled_source_frames is not None:
        raise RuntimeError("Quality unexpectedly returned sparse metrics")
    if mode == "performance":
        planned = tuple(
            frame
            for burst in plan_performance_bursts(
                window_start=expected_range.start,
                window_end_exclusive=expected_range.end_exclusive,
            )
            for frame in range(burst.start, burst.end_exclusive)
        )
        if tuple(metrics.sampled_source_frames or ()) != planned:
            raise RuntimeError("Performance source-frame map differs from the production plan")


def _require_cache_policy(
    *,
    policy: MetricCachePolicy,
    mode: str,
    cache_state: AnalysisCacheState,
    cache_write_state: AnalysisCacheWriteState,
) -> None:
    if policy == "cold":
        if cache_state != "miss" or cache_write_state != "written":
            raise RuntimeError(
                f"Cold {mode} trial expected cache miss/write, got "
                f"{cache_state}/{cache_write_state}"
            )
        return
    if cache_state != "hit" or cache_write_state != "not_attempted":
        raise RuntimeError(
            f"Reuse {mode} trial expected cache hit/no write attempt, got "
            f"{cache_state}/{cache_write_state}"
        )


def _aggregate_tier_trials(trials: Sequence[JsonObject]) -> JsonObject:
    if not trials:
        raise ValueError("Cannot aggregate an empty trial set")
    aggregate = dict(trials[0])
    summaries = [_trial_result_summary(trial) for trial in trials]
    aggregate["trials"] = summaries
    aggregate["timing_summary"] = _timing_summary(summaries)
    aggregate["analyze_seconds"] = aggregate["timing_summary"]["analyze_seconds"]["median"]
    aggregate["compute_pipeline_seconds"] = aggregate["timing_summary"]["compute_pipeline_seconds"][
        "median"
    ]
    aggregate["cache_state"] = _counts(trial["cache_state"] for trial in trials)
    aggregate["cache_write_state"] = _counts(trial["cache_write_state"] for trial in trials)
    return aggregate


def _trial_result_summary(trial: JsonObject) -> JsonObject:
    return {
        key: trial[key]
        for key in (
            "repetition",
            "order_index",
            "cache_state",
            "cache_write_state",
            "analyze_seconds",
            "compute_pipeline_seconds",
            "selection_seconds",
            "trial_seconds",
            "process_cpu_seconds",
            "cpu_to_wall_ratio",
            "peak_rss_bytes",
            "phase_timings_seconds",
        )
    }


def _timing_summary(trials: Sequence[JsonObject]) -> JsonObject:
    fields = (
        "analyze_seconds",
        "compute_pipeline_seconds",
        "selection_seconds",
        "trial_seconds",
        "process_cpu_seconds",
        "cpu_to_wall_ratio",
    )
    result = {field: _distribution([float(trial[field]) for trial in trials]) for field in fields}
    phase_names = sorted(
        {
            phase
            for trial in trials
            for phase in cast(Mapping[str, float], trial["phase_timings_seconds"])
        }
    )
    result["phase_timings_seconds"] = {
        phase: _distribution(
            [
                float(cast(Mapping[str, float], trial["phase_timings_seconds"]).get(phase, 0.0))
                for trial in trials
            ]
        )
        for phase in phase_names
    }
    return result


def _compare_modes(
    *, quality: JsonObject, performance: JsonObject, config: AnalysisConfig
) -> JsonObject:
    quality_metrics = cast(FrameMetrics, quality["metrics"])
    performance_metrics = cast(FrameMetrics, performance["metrics"])
    quality_selection = cast(FrameSelection, quality["selection"])
    performance_selection = cast(FrameSelection, performance["selection"])
    categories: dict[SelectionCategory, tuple[Sequence[int], Sequence[int]]] = {
        "dark": (
            quality_selection.breakdown.quantile_dark,
            performance_selection.breakdown.quantile_dark,
        ),
        "bright": (
            quality_selection.breakdown.quantile_bright,
            performance_selection.breakdown.quantile_bright,
        ),
        "motion": (
            quality_selection.breakdown.motion,
            performance_selection.breakdown.motion,
        ),
    }
    comparisons = {
        category: asdict(
            compare_selection_category(
                quality_frames=quality_frames,
                candidate_frames=performance_frames,
                tolerance_frames=tier_category_tolerance("performance", category),
            )
        )
        for category, (quality_frames, performance_frames) in categories.items()
    }
    return {
        "mode": "performance",
        "analyze_seconds": performance["analyze_seconds"],
        "compute_pipeline_seconds": performance["compute_pipeline_seconds"],
        "cache_state": performance["cache_state"],
        "cache_write_state": performance["cache_write_state"],
        "timing_summary": performance["timing_summary"],
        "trials": performance["trials"],
        "metadata": performance["metadata"],
        "sampling": performance["sampling"],
        "selected": _selected_summary(performance_selection),
        "comparisons": comparisons,
        "exact_selected_equality": {
            category: list(quality_frames) == list(performance_frames)
            for category, (quality_frames, performance_frames) in categories.items()
        },
        "timing_comparison": _timing_comparison(quality, performance),
        "quality_category_pool_retention": _quality_category_pool_retention(
            quality_metrics=quality_metrics,
            performance_selection=performance_selection,
            config=config,
        ),
        "sampled_metric_fidelity": _sampled_metric_fidelity(
            quality_metrics=quality_metrics,
            performance_metrics=performance_metrics,
        ),
        "sampled_ranking": _sampled_ranking(
            quality_metrics=quality_metrics,
            performance_metrics=performance_metrics,
            config=config,
        ),
    }


def _quality_category_pool_retention(
    *,
    quality_metrics: FrameMetrics,
    performance_selection: FrameSelection,
    config: AnalysisConfig,
) -> JsonObject:
    start = quality_metrics.metadata.metric_source_start
    luminance = list(quality_metrics.luminance)
    motion = list(quality_metrics.motion)
    dark_count = max(1, int(len(luminance) * config.dark_quantile))
    bright_start = min(len(luminance) - 1, int(len(luminance) * config.bright_quantile))
    motion_count = min(len(motion), max(1, config.motion_frame_count, int(len(motion) * 0.20)))
    ordered_luminance = sorted(luminance)
    ordered_motion = sorted(motion, reverse=True)
    dark_threshold = ordered_luminance[dark_count - 1]
    bright_threshold = ordered_luminance[bright_start]
    motion_threshold = ordered_motion[motion_count - 1]
    pools = {
        "dark": {start + index for index, value in enumerate(luminance) if value <= dark_threshold},
        "bright": {
            start + index for index, value in enumerate(luminance) if value >= bright_threshold
        },
        "motion": {
            start + index for index, value in enumerate(motion) if value >= motion_threshold
        },
    }
    selected = {
        "dark": list(performance_selection.breakdown.quantile_dark),
        "bright": list(performance_selection.breakdown.quantile_bright),
        "motion": list(performance_selection.breakdown.motion),
    }
    return {
        category: {
            "selected_count": len(frames),
            "retained_count": sum(frame in pools[category] for frame in frames),
            "retained_fraction": (
                None
                if not frames
                else sum(frame in pools[category] for frame in frames) / len(frames)
            ),
        }
        for category, frames in selected.items()
    }


def _sampled_metric_fidelity(
    *, quality_metrics: FrameMetrics, performance_metrics: FrameMetrics
) -> JsonObject:
    quality_start = quality_metrics.metadata.metric_source_start
    sampled = tuple(performance_metrics.sampled_source_frames or ())
    quality_luminance = [quality_metrics.luminance[frame - quality_start] for frame in sampled]
    quality_motion = [quality_metrics.motion[frame - quality_start] for frame in sampled]
    return {
        "scope": "performance-sampled-source-frames-only",
        "sample_count": len(sampled),
        "luminance": _series_difference(quality_luminance, performance_metrics.luminance),
        "motion": _series_difference(quality_motion, performance_metrics.motion),
    }


def _sampled_ranking(
    *, quality_metrics: FrameMetrics, performance_metrics: FrameMetrics, config: AnalysisConfig
) -> JsonObject:
    start = quality_metrics.metadata.metric_source_start
    sampled = tuple(performance_metrics.sampled_source_frames or ())
    quality_luminance = [quality_metrics.luminance[frame - start] for frame in sampled]
    quality_motion = [quality_metrics.motion[frame - start] for frame in sampled]
    return {
        "scope": "performance-sampled-source-frames-only",
        "dark_luminance": _ranking_diagnostic(
            sampled,
            quality_luminance,
            performance_metrics.luminance,
            config.dark_frame_count,
            False,
        ),
        "bright_luminance": _ranking_diagnostic(
            sampled,
            quality_luminance,
            performance_metrics.luminance,
            config.bright_frame_count,
            True,
        ),
        "motion": _ranking_diagnostic(
            sampled, quality_motion, performance_metrics.motion, config.motion_frame_count, True
        ),
    }


def _ranking_diagnostic(
    frames: Sequence[int],
    quality_values: Sequence[float],
    performance_values: Sequence[float],
    requested_k: int,
    largest: bool,
) -> JsonObject:
    quality_order = sorted(
        range(len(frames)), key=lambda index: quality_values[index], reverse=largest
    )
    performance_order = sorted(
        range(len(frames)), key=lambda index: performance_values[index], reverse=largest
    )
    k = min(max(0, requested_k), len(frames))
    quality_top = [frames[index] for index in quality_order[:k]]
    performance_top = [frames[index] for index in performance_order[:k]]
    overlap = len(set(quality_top) & set(performance_top))
    return {
        "direction": "highest" if largest else "lowest",
        "requested_k": requested_k,
        "effective_k": k,
        "top_k_overlap_count": overlap,
        "top_k_overlap_fraction": None if k == 0 else overlap / k,
        "quality_top_source_frames": quality_top,
        "performance_top_source_frames": performance_top,
        "spearman": _spearman_correlation(quality_values, performance_values),
    }


def _series_difference(left: Sequence[float], right: Sequence[float]) -> JsonObject:
    if len(left) != len(right):
        raise ValueError("Metric series lengths differ")
    errors = [abs(a - b) for a, b in zip(left, right, strict=True)]
    return {
        "max_absolute_error": max(errors, default=0.0),
        "mean_absolute_error": statistics.fmean(errors) if errors else 0.0,
        "allclose_atol_1e_12": all(error <= 1e-12 for error in errors),
    }


def _spearman_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_ranks = _average_ranks(left)
    right_ranks = _average_ranks(right)
    left_mean = statistics.fmean(left_ranks)
    right_mean = statistics.fmean(right_ranks)
    numerator = sum(
        (a - left_mean) * (b - right_mean) for a, b in zip(left_ranks, right_ranks, strict=True)
    )
    left_norm = sum((rank - left_mean) ** 2 for rank in left_ranks) ** 0.5
    right_norm = sum((rank - right_mean) ** 2 for rank in right_ranks) ** 0.5
    return None if left_norm == 0 or right_norm == 0 else numerator / (left_norm * right_norm)


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        average = (position + end - 1) / 2
        for index in order[position:end]:
            ranks[index] = average
        position = end
    return ranks


def _timing_comparison(quality: JsonObject, performance: JsonObject) -> JsonObject:
    q = cast(Mapping[str, float], quality["timing_summary"]["compute_pipeline_seconds"])
    p = cast(Mapping[str, float], performance["timing_summary"]["compute_pipeline_seconds"])
    quality_median = float(q["median"])
    performance_median = float(p["median"])
    delta = quality_median - performance_median
    noise = max(float(q["pstdev"]), float(p["pstdev"]))
    speedup = None if performance_median <= 0 else quality_median / performance_median
    return {
        "reference_mode": "quality",
        "candidate_mode": "performance",
        "speedup": speedup,
        "percent_time_reduction": (None if quality_median <= 0 else delta / quality_median * 100),
        "reference_median_seconds": quality_median,
        "candidate_median_seconds": performance_median,
        "reference_minus_candidate_median_seconds": delta,
        "max_pstdev_noise_band_seconds": noise,
        "outside_noise_band": delta > noise,
        "meets_1_5x_speedup": speedup is not None and speedup >= 1.5,
        "meets_2x_speedup": speedup is not None and speedup >= 2.0,
    }


def _tier_summary(tier: JsonObject) -> JsonObject:
    return {
        "mode": tier["mode"],
        "analyze_seconds": tier["analyze_seconds"],
        "compute_pipeline_seconds": tier["compute_pipeline_seconds"],
        "cache_state": tier["cache_state"],
        "cache_write_state": tier["cache_write_state"],
        "timing_summary": tier["timing_summary"],
        "trials": tier["trials"],
        "metadata": tier["metadata"],
        "sampling": tier["sampling"],
        "selected": _selected_summary(cast(FrameSelection, tier["selection"])),
    }


def _metrics_metadata_json(metrics: FrameMetrics) -> JsonObject:
    metadata = metrics.metadata
    return {
        "frame_count": metadata.frame_count,
        "eligible_frame_count": metrics.eligible_frame_count,
        "source_frame_count": metadata.source_frame_count,
        "metric_source_start": metadata.metric_source_start,
        "metric_source_end_exclusive": metadata.metric_source_end_exclusive,
        "performance_mode": metadata.performance_mode,
        "algorithm_id": metadata.algorithm_id,
        "metric_backend": metadata.metric_backend,
        "algorithm_identity_json": metadata.algorithm_identity_json,
        "cache_version": metadata.version,
    }


def _sampling_json(metrics: FrameMetrics) -> JsonObject | None:
    if metrics.sampled_source_frames is None:
        return None
    bursts = plan_performance_bursts(
        window_start=metrics.metadata.metric_source_start,
        window_end_exclusive=metrics.metadata.metric_source_end_exclusive,
    )
    return {
        "policy": "exact-ceil-quarter-centered-contiguous-bursts",
        "sample_count": len(metrics.sampled_source_frames),
        "eligible_frame_count": metrics.eligible_frame_count,
        "actual_fraction": len(metrics.sampled_source_frames) / metrics.eligible_frame_count,
        "source_frames": list(metrics.sampled_source_frames),
        "bursts": [asdict(burst) for burst in bursts],
    }


def _selected_summary(selection: FrameSelection) -> JsonObject:
    return {
        "frames": list(selection.frames),
        "user": list(selection.breakdown.user),
        "random": list(selection.breakdown.random),
        "dark": list(selection.breakdown.quantile_dark),
        "bright": list(selection.breakdown.quantile_bright),
        "motion": list(selection.breakdown.motion),
    }


def _config_for_window(
    config: AnalysisConfig, *, window_start: int, window_end: int
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


def _selection_with_offset(selection: FrameSelection, offset: int) -> FrameSelection:
    breakdown = selection.breakdown
    return FrameSelection(
        frames=[frame + offset for frame in selection.frames],
        seed=selection.seed,
        breakdown=replace(
            breakdown,
            user=[frame + offset for frame in breakdown.user],
            random=[frame + offset for frame in breakdown.random],
            quantile_dark=[frame + offset for frame in breakdown.quantile_dark],
            quantile_bright=[frame + offset for frame in breakdown.quantile_bright],
            motion=[frame + offset for frame in breakdown.motion],
        ),
        selection_details={},
    )


def _delete_tier_metrics_cache(
    request: MetricCacheRequest,
    *,
    video_paths: Sequence[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    selection_domain: str | None,
) -> None:
    key = compute_cache_key(
        list(video_paths), config, selection_domain=selection_domain, metric_request=request
    )
    delete_metrics_cache_entry(cache_dir, key)


def _compute_pipeline_seconds(analyze_seconds: float, phase_timings: Mapping[str, float]) -> float:
    persistence = phase_timings.get("cache_lookup", 0.0) + phase_timings.get("cache_write", 0.0)
    return max(0.0, analyze_seconds - persistence)


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


def _counts(values: Iterator[object]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value)
        result[key] = result.get(key, 0) + 1
    return result


def _git_provenance(root: Path) -> JsonObject:
    commit = _git_output(root, ["rev-parse", "HEAD"])
    status = _git_output(root, ["status", "--porcelain"])
    if commit is None or status is None:
        return {"available": False, "commit": commit, "dirty": None}
    return {
        "available": True,
        "commit": commit,
        "dirty": bool(status),
        "status_porcelain": status.splitlines(),
    }


def _git_output(root: Path, args: Sequence[str]) -> str | None:
    output = _small_text_command(["git", "-C", str(root), *args], _GIT_STDOUT_BYTES)
    return None if output is None else output.strip()


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
    output = _small_text_command([command, "-version"], _VERSION_STDOUT_BYTES)
    return output.splitlines()[0].rstrip() if output else None


def _small_text_command(argv: Sequence[str], stdout_limit: int) -> str | None:
    try:
        result = run_subprocess(
            argv,
            timeout_seconds=10,
            check=False,
            max_stdout_bytes=stdout_limit,
            max_stderr_bytes=_TEXT_STDERR_BYTES,
        )
    except (OSError, subprocess.TimeoutExpired, SubprocessOutputLimitExceeded):
        return None
    if result.returncode != 0:
        return None
    output = sanitize_diagnostic(result.stdout, diagnostic_secrets())
    return output.decode() if len(output) <= stdout_limit else None


def _source_index_facts(
    paths: Sequence[Path], index_cache: ManagedSourceIndexCache
) -> dict[str, JsonObject]:
    facts: dict[str, JsonObject] = {}
    for path in paths:
        index = index_cache.validated_index(path)
        facts[path.as_posix()] = {
            "detected": index is not None,
            "expected_path": index.as_posix() if index is not None else None,
            "paths": [index.as_posix()] if index is not None else [],
            "sizes_bytes": [index.stat().st_size] if index is not None else [],
        }
    return facts


def _probe_source_facts(
    path: Path,
    *,
    inspect_frame_types: bool,
    timeout_seconds: float,
    window_start: int,
    window_end_exclusive: int,
    source_fps: Fraction | None,
) -> JsonObject:
    stream = _run_ffprobe_json(
        [
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,profile,pix_fmt,width,height,bits_per_raw_sample,avg_frame_rate,nb_frames,duration:format=format_name,duration,size,bit_rate",
        ],
        path=path,
        timeout_seconds=timeout_seconds,
    )
    result: JsonObject = {
        "path": path.as_posix(),
        "size_bytes": path.stat().st_size,
        "stream_and_format": stream,
    }
    if inspect_frame_types:
        options, scope = _frame_type_probe_options(
            window_start=window_start,
            window_end_exclusive=window_end_exclusive,
            source_fps=source_fps,
        )
        started = time.perf_counter()
        result["frame_types"] = _run_ffprobe_frame_scan(
            options, path=path, timeout_seconds=timeout_seconds
        )
        result["frame_type_inspection_seconds"] = time.perf_counter() - started
        result["frame_type_inspection_scope"] = scope
    return result


def _frame_type_probe_options(
    *, window_start: int, window_end_exclusive: int, source_fps: Fraction | None
) -> tuple[list[str], JsonObject]:
    options = ["-select_streams", "v:0"]
    if source_fps is not None:
        start = Fraction(window_start, 1) / source_fps
        duration = Fraction(window_end_exclusive - window_start, 1) / source_fps
        interval = f"{float(start):.6f}%+{float(duration):.6f}"
        options.extend(["-read_intervals", interval])
        scope: JsonObject = {
            "kind": "approximate-benchmark-window",
            "approximate": True,
            "start_frame": window_start,
            "end_frame_exclusive": window_end_exclusive,
            "source_fps": str(source_fps),
            "read_interval": interval,
        }
    else:
        scope = {
            "kind": "full-source",
            "fallback_reason": "source_fps_unavailable",
            "requested_start_frame": window_start,
            "requested_end_frame_exclusive": window_end_exclusive,
        }
    options.extend(
        [
            "-show_frames",
            "-show_entries",
            "frame=key_frame,pict_type,best_effort_timestamp_time:frame_side_data=",
        ]
    )
    return options, scope


def _run_ffprobe_json(options: Sequence[str], *, path: Path, timeout_seconds: float) -> JsonObject:
    try:
        result = run_subprocess(
            ["ffprobe", "-v", "error", *options, "-of", "json", str(path)],
            check=False,
            timeout_seconds=timeout_seconds,
            max_stdout_bytes=_METADATA_STDOUT_BYTES,
            max_stderr_bytes=_FFPROBE_STDERR_BYTES,
        )
    except (OSError, subprocess.TimeoutExpired, SubprocessOutputLimitExceeded) as exc:
        return {"success": False, "error": _probe_error(exc, timeout_seconds)}
    if result.returncode != 0:
        return {
            "success": False,
            "returncode": result.returncode,
            "error": _probe_exit_error(result),
        }
    try:
        payload: object = json.loads(result.stdout)
    except (ValueError, RecursionError):
        return {"success": False, "error": "invalid ffprobe JSON"}
    return (
        {"success": True, "payload": payload}
        if isinstance(payload, dict)
        else {
            "success": False,
            "error": "ffprobe JSON root was not an object",
        }
    )


def _probe_error(
    error: OSError | subprocess.TimeoutExpired | SubprocessOutputLimitExceeded,
    timeout_seconds: float,
) -> str:
    if isinstance(error, subprocess.TimeoutExpired):
        return f"ffprobe timed out after {timeout_seconds}s"
    if isinstance(error, SubprocessOutputLimitExceeded):
        return str(error)
    detail = f"{type(error).__name__}: {error}"
    return sanitize_diagnostic(detail.encode(errors="replace"), diagnostic_secrets()).decode()[
        :1024
    ]


def _probe_exit_error(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stderr.decode("utf-8", errors="replace").strip() or (
        f"ffprobe exited with status {result.returncode}"
    )


class _FrameScanRejected(ValueError):
    """The complete frame summary cannot be trusted."""


@dataclass(slots=True)
class _FrameScan:
    pending: bytes = b""
    frame_count: int = 0
    keyframe_count: int = 0
    previous_keyframe: int | None = None
    types: Counter[str] = field(default_factory=Counter)
    gaps: Counter[int] = field(default_factory=Counter)
    observed_timestamps: list[float] = field(default_factory=list)

    def feed(self, chunk: bytes) -> None:
        rows = (self.pending + chunk).split(b"\n")
        self.pending = rows.pop()
        if len(self.pending) > _FRAME_ROW_MAX_BYTES:
            raise _FrameScanRejected("malformed ffprobe frame row")
        for row in rows:
            match = _FRAME_ROW.fullmatch(row) if len(row) <= _FRAME_ROW_MAX_BYTES else None
            if match is None:
                raise _FrameScanRejected("malformed ffprobe frame row")
            if self.frame_count >= _FRAME_SCAN_MAX_ROWS:
                raise _FrameScanRejected(
                    f"ffprobe frame scan exceeded {_FRAME_SCAN_MAX_ROWS:,} rows"
                )
            # FFprobe emits fields in its own order, independent of -show_entries.
            key_frame, timestamp, pict_type = match.groups()
            if timestamp != b"N/A":
                self.observed_timestamps.append(float(timestamp))
            self.types[pict_type.decode("ascii")] += 1
            if key_frame == b"1":
                if self.previous_keyframe is not None:
                    self.gaps[self.frame_count - self.previous_keyframe] += 1
                self.previous_keyframe = self.frame_count
                self.keyframe_count += 1
            self.frame_count += 1

    def summary(self) -> JsonObject:
        if self.pending:
            raise _FrameScanRejected("incomplete ffprobe frame row")
        return {
            "available": True,
            "frame_count": self.frame_count,
            "type_counts": dict(self.types),
            "keyframe_count": self.keyframe_count,
            "keyframe_gap_frames": _gap_distribution(self.gaps),
            "observed_timestamps_seconds": self.observed_timestamps,
        }


def _gap_distribution(gaps: Counter[int]) -> JsonObject:
    # Keep one counter per distinct gap, not one entry per keyframe.
    # Positive gaps sum to at most the frame cap, so there can be <1,415 keys.
    if not gaps:
        return {"count": 0}
    ordered = sorted(gaps.items())
    count = gaps.total()
    total = sum(gap * frequency for gap, frequency in ordered)
    squares = sum(gap * gap * frequency for gap, frequency in ordered)
    lower_rank, upper_rank = (count - 1) // 2, count // 2
    passed = 0
    lower = upper = ordered[0][0]
    for gap, frequency in ordered:
        if passed <= lower_rank < passed + frequency:
            lower = gap
        passed += frequency
        if passed > upper_rank:
            upper = gap
            break
    return {
        "count": count,
        "min": float(ordered[0][0]),
        "max": float(ordered[-1][0]),
        "mean": total / count,
        "median": (lower + upper) / 2,
        "pstdev": math.sqrt(count * squares - total * total) / count,
    }


def _run_ffprobe_frame_scan(
    options: Sequence[str], *, path: Path, timeout_seconds: float
) -> JsonObject:
    scan = _FrameScan()

    def consume(chunk: bytes) -> None:
        try:
            scan.feed(chunk)
        except _FrameScanRejected:
            raise
        except Exception:
            raise _FrameScanRejected("ffprobe frame output consumer failed") from None

    try:
        result = run_subprocess(
            ["ffprobe", "-v", "error", *options, "-of", "csv=p=0", str(path)],
            check=False,
            timeout_seconds=timeout_seconds,
            stdout_consumer=consume,
            max_stdout_bytes=_FRAME_SCAN_STDOUT_BYTES,
            max_stderr_bytes=_FFPROBE_STDERR_BYTES,
        )
        # At error log level, even a zero exit can accompany a partial decode.
        if result.returncode != 0 or result.stderr:
            return {"available": False, "error": _probe_exit_error(result)}
        return scan.summary()
    except _FrameScanRejected as exc:
        return {"available": False, "error": str(exc)}
    except (OSError, subprocess.TimeoutExpired, SubprocessOutputLimitExceeded) as exc:
        return {"available": False, "error": _probe_error(exc, timeout_seconds)}


def _run_decode_baseline(*, analysis_source_path: Path, vs_loader: DefaultVSLoader) -> JsonObject:
    started = time.perf_counter()
    source = vs_loader.load(analysis_source_path)
    source_load_seconds = time.perf_counter() - started
    try:
        graph_started = time.perf_counter()
        stats = cast(_PlaneStatsSource, source.clip).std.PlaneStats()
        graph_seconds = time.perf_counter() - graph_started
        render_started = time.perf_counter()
        frames = sum(1 for _frame in stats.frames(close=True))
        render_seconds = time.perf_counter() - render_started
    finally:
        del source
    return {
        "operation": "full_source_plane0_planestats_concurrent",
        "frame_count": frames,
        "source_load_seconds": source_load_seconds,
        "graph_build_seconds": graph_seconds,
        "frame_render_seconds": render_seconds,
        "frames_per_second": 0.0 if render_seconds <= 0 else frames / render_seconds,
        "note": "Executed after timed trials so it cannot warm them.",
    }


def _resolve_benchmark_analysis_source_path(
    *, input_dir: Path, input_paths: Sequence[Path], config: ConfigSchema
) -> Path:
    if config.sources.analysis_source == "fastest":
        raise SystemExit("Benchmarking requires an explicit analysis source, not 'fastest'.")
    if config.sources.match_fps != SourceMatchFpsMode.DISABLED:
        raise SystemExit("Benchmarking requires sources.match_fps = 'disabled'.")
    selection = resolve_source_selection(
        input_dir=input_dir, discovered_paths=list(input_paths), config=config.sources
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
    *, root: Path, input_dir: Path, input_paths: Sequence[Path], config: ConfigSchema
) -> BenchmarkAnalysisSource:
    path = _resolve_benchmark_analysis_source_path(
        input_dir=input_dir, input_paths=input_paths, config=config
    )
    selection = resolve_source_selection(
        input_dir=input_dir, discovered_paths=list(input_paths), config=config.sources
    )
    override = selection.overrides_by_path.get(path)
    prepared_clips = _prepared_benchmark_clips(
        root=root,
        input_paths=selection.ordered_paths,
        config=config,
        overrides_by_path=selection.overrides_by_path,
    )
    prepared_analysis = None
    reference_fps = None
    if prepared_clips is not None:
        prepared_analysis = next(clip for clip in prepared_clips if clip.path == path)
        reference_fps = prepared_clips[0].effective_fps
    return BenchmarkAnalysisSource(
        path=path,
        ordered_paths=tuple(selection.ordered_paths),
        effective_fps=None if prepared_analysis is None else prepared_analysis.effective_fps,
        reference_fps=reference_fps,
        effective_frame_count=(
            None if prepared_analysis is None else prepared_analysis.effective_num_frames()
        ),
        trim_start_frames=(
            0 if prepared_analysis is None else prepared_analysis.trim.trim_start_frames
        ),
        active_rect=_benchmark_active_rect_from_prepared_clip(
            source_path=path,
            override=override,
            prepared_clip=prepared_analysis,
            config=config,
        ),
        overrides_by_path=selection.overrides_by_path,
        source_frame_count=(
            None if prepared_analysis is None else prepared_analysis.probe.num_frames
        ),
        source_fps=(None if prepared_analysis is None else prepared_analysis.probe.fps),
    )


def _prepared_benchmark_clips(
    *,
    root: Path,
    input_paths: Sequence[Path],
    config: ConfigSchema,
    overrides_by_path: dict[Path, SourceOverrideConfig],
) -> list[ClipState] | None:
    cache = _resolve_config_path(root, config.paths.generated_dir) / "clip_probe.toml"
    entries = dict(load_clip_probe_cache(cache))
    snapshots: dict[Path, ClipProbeSnapshot] = {}
    for path in input_paths:
        stat = path.stat()
        key = compute_probe_cache_key(
            ClipFingerprint(path=path, size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
        )
        snapshot = entries.get(key)
        if snapshot is None:
            return None
        snapshots[path] = snapshot
    result = build_selection_domain_clips_with_diagnostics(
        ordered_paths=list(input_paths),
        snapshots_by_path=snapshots,
        overrides_by_path=overrides_by_path,
        labels_by_path={path: path.stem for path in input_paths},
        match_fps=config.sources.match_fps,
        active_rect_detection=config.screenshots.active_rect_detection,
    )
    return result.clips


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
            rect=MetricActiveRect(rect.x, rect.y, rect.width, rect.height),
            source="explicit",
            detection_mode=config.screenshots.active_rect_detection.value,
        )
    if prepared_clip is None or prepared_clip.active_rect is None:
        raise SystemExit(
            f"Prepared active-rectangle data for {source_path.name} is missing. "
            "Run the normal preparation path first."
        )
    prepared = prepared_clip.active_rect
    if (
        config.screenshots.active_rect_detection == ScreenshotActiveRectDetection.AUTO
        and prepared.source == "full-frame"
    ):
        raise SystemExit("Auto active-rectangle content refinement is unavailable in this tool.")
    return BenchmarkActiveRect(
        rect=MetricActiveRect(prepared.x, prepared.y, prepared.width, prepared.height),
        source=prepared.source,
        detection_mode=prepared.detection_mode,
        algorithm_id=prepared.algorithm_id,
    )


def _metric_active_rect_json(rect: MetricActiveRect | None) -> JsonObject | None:
    return None if rect is None else asdict(rect)


def _require_selection_domain_for_analysis_cache_identity(
    *,
    selection_domain: str | None,
    video_paths: Sequence[Path],
    analysis_source: BenchmarkAnalysisSource,
    active_rect_detection: ScreenshotActiveRectDetection,
) -> None:
    if selection_domain is not None:
        return
    is_default = (
        bool(video_paths)
        and analysis_source.reference_path == video_paths[0]
        and analysis_source.path == video_paths[0]
        and active_rect_detection == ScreenshotActiveRectDetection.ASPECT_RATIO
        and not any(
            _source_override_affects_selection_domain(value)
            for value in analysis_source.overrides_by_path.values()
        )
    )
    if not is_default:
        raise SystemExit(
            "A prepared --selection-domain token is required for this non-default domain."
        )


def _source_override_affects_selection_domain(override: SourceOverrideConfig) -> bool:
    return bool(
        override.trim_start_frames
        or override.trim_end_frames
        or override.effective_fps is not None
        or override.active_rect is not None
    )


def _require_selection_coordinate_compatibility(source: BenchmarkAnalysisSource) -> None:
    analysis = source.overrides_by_path.get(source.path)
    reference = source.overrides_by_path.get(source.reference_path)
    analysis_start = 0 if analysis is None else analysis.trim_start_frames
    reference_start = 0 if reference is None else reference.trim_start_frames
    if analysis_start != reference_start:
        raise SystemExit(
            "Benchmark selection reporting requires matching reference and analysis trim starts."
        )


def _peak_rss_bytes() -> int | None:
    if sys.platform == "win32":
        return None
    import resource

    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


if __name__ == "__main__":
    raise SystemExit(main())
