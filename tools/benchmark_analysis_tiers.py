#!/usr/bin/env python3
"""Benchmark analysis performance mode against quality on local clips."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import asdict, replace
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from frame_compare.analysis.metrics import calculate_metrics
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.tier_validation import (
    SelectionCategory,
    compare_rankings,
    compare_selection_category,
    tier_category_tolerance,
)
from frame_compare.analysis.types import FrameMetrics, FrameSelection, MetricActiveRect
from frame_compare.config.loader import load_config
from frame_compare.config.schema import AnalysisConfig, ConfigSchema
from frame_compare.config.schema_enums import AnalysisPerformanceMode, SourceMatchFpsMode
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.source_selection import (
    resolve_source_selection,
    resolve_source_selector,
)

type JsonObject = dict[str, Any]


def main() -> int:
    args = _parse_args()
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    output_path = args.output if args.output.is_absolute() else root / args.output
    input_paths = [
        path if path.is_absolute() else root / path for path in cast(Sequence[Path], args.inputs)
    ]
    config = load_config(config_path)
    input_dir = _resolve_config_path(root, config.paths.input_dir)
    cache_dir = (
        args.cache_dir
        if args.cache_dir is not None
        else _resolve_config_path(root, config.paths.generated_dir) / "cache" / "analysis"
    )
    if not cache_dir.is_absolute():
        cache_dir = root / cache_dir
    analysis_source_path, effective_fps, metric_active_rect = _resolve_benchmark_analysis_source(
        input_dir=input_dir,
        input_paths=input_paths,
        config=config,
    )
    _require_selection_domain_for_analysis_cache_identity(
        selection_domain=args.selection_domain,
        video_paths=input_paths,
        analysis_source_path=analysis_source_path,
    )
    warnings = [
        "Per-subphase luminance and motion timings are unavailable; only total analysis wall-clock is recorded.",
        "Cache hit/miss state is not exposed by calculate_metrics; benchmark output records cache_state as unknown.",
    ]

    quality, comparisons = _run_benchmark_tiers(
        candidate_modes=cast(Sequence[str], args.modes),
        video_paths=input_paths,
        analysis_config=config.analysis,
        cache_dir=cache_dir,
        analysis_source_path=analysis_source_path,
        effective_fps=effective_fps,
        metric_active_rect=metric_active_rect,
        selection_domain=args.selection_domain,
        window_start=args.window_start,
        window_end_exclusive=args.window_end_exclusive,
        progress_enabled=not args.no_progress,
    )

    if args.window_end_exclusive is None:
        warnings.append(
            "No explicit --window-end-exclusive was provided; comparisons use the full analysis metric domain."
        )
    if args.selection_domain is None:
        warnings.append(
            "No orchestration selection-domain token was provided; cache identity may differ from a full run with trims or source overrides."
        )

    report: JsonObject = {
        "inputs": [path.as_posix() for path in input_paths],
        "config": {
            "config_path": config_path.as_posix(),
            "analysis_source": config.sources.analysis_source,
            "analysis_source_path": analysis_source_path.as_posix(),
            "effective_fps": str(effective_fps) if effective_fps is not None else None,
            "metric_active_rect": _metric_active_rect_json(metric_active_rect),
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
        },
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
    input_dir: Path,
    input_paths: Sequence[Path],
    config: ConfigSchema,
) -> tuple[Path, Fraction | None, MetricActiveRect | None]:
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
    return source_path, effective_fps, _metric_active_rect_from_override(override)


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


def _metric_active_rect_from_override(
    override: SourceOverrideConfig | None,
) -> MetricActiveRect | None:
    if override is None or override.active_rect is None:
        return None
    rect = override.active_rect
    return MetricActiveRect(
        x=rect.x,
        y=rect.y,
        width=rect.width,
        height=rect.height,
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
    analysis_source_path: Path,
) -> None:
    if selection_domain is not None:
        return
    if video_paths and analysis_source_path == video_paths[0]:
        return
    raise SystemExit(
        "A benchmark selection-domain token is required when the resolved analysis source "
        "is not the first input path, because analysis cache identity otherwise cannot "
        "distinguish the selected analysis source. Pass --selection-domain from a prepared "
        "run or benchmark with the analysis source as the first input."
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
    args = parser.parse_args()
    if args.modes is None:
        args.modes = ["performance"]
    if args.window_start < 0:
        parser.error("--window-start must be non-negative")
    if args.window_end_exclusive is not None and args.window_end_exclusive <= args.window_start:
        parser.error("--window-end-exclusive must be greater than --window-start")
    return args


def _run_benchmark_tiers(
    *,
    candidate_modes: Sequence[str],
    video_paths: Sequence[Path],
    analysis_config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    metric_active_rect: MetricActiveRect | None,
    selection_domain: str | None,
    window_start: int,
    window_end_exclusive: int | None,
    progress_enabled: bool,
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
    total = 1 + len(candidate_modes)
    comparisons: dict[str, JsonObject] = {}

    with progress:
        task_id = progress.add_task("Starting analysis benchmark", total=total)
        progress.update(task_id, description="Running quality analysis")
        quality = _run_tier(
            mode="quality",
            video_paths=video_paths,
            analysis_config=analysis_config,
            cache_dir=cache_dir,
            analysis_source_path=analysis_source_path,
            effective_fps=effective_fps,
            metric_active_rect=metric_active_rect,
            selection_domain=selection_domain,
            window_start=window_start,
            window_end_exclusive=window_end_exclusive,
        )
        progress.advance(task_id)

        for mode in candidate_modes:
            progress.update(task_id, description=f"Running {mode} analysis")
            tier = _run_tier(
                mode=mode,
                video_paths=video_paths,
                analysis_config=analysis_config,
                cache_dir=cache_dir,
                analysis_source_path=analysis_source_path,
                effective_fps=effective_fps,
                metric_active_rect=metric_active_rect,
                selection_domain=selection_domain,
                window_start=window_start,
                window_end_exclusive=window_end_exclusive,
            )
            comparisons[mode] = _compare_tier(quality=quality, candidate=tier)
            progress.advance(task_id)

        progress.update(task_id, description="Analysis benchmark complete")

    return quality, comparisons


def _run_tier(
    *,
    mode: str,
    video_paths: Sequence[Path],
    analysis_config: AnalysisConfig,
    cache_dir: Path,
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    metric_active_rect: MetricActiveRect | None,
    selection_domain: str | None,
    window_start: int,
    window_end_exclusive: int | None,
) -> JsonObject:
    tier_config = analysis_config.model_copy(
        update={"performance_mode": AnalysisPerformanceMode(mode)}
    )
    started = time.perf_counter()
    metrics = calculate_metrics(
        list(video_paths),
        tier_config,
        cache_dir,
        analysis_source_path=analysis_source_path,
        effective_fps=effective_fps,
        metric_active_rect=metric_active_rect,
        selection_domain=selection_domain,
    )
    analyze_seconds = time.perf_counter() - started
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
    return {
        "mode": mode,
        "analyze_seconds": analyze_seconds,
        "cache_state": "unknown",
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
