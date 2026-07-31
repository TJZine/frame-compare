"""Shared helpers for execute_run orchestration tests."""

from __future__ import annotations

import os
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PIL import Image

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.analysis.sampling import plan_performance_bursts
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    MetricCacheRequest,
    MetricsMetadata,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.active_rect import metric_cache_request_for_clip
from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot, ClipState
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    save_clip_probe_cache,
)
from frame_compare.orchestration.selection_domain import (
    build_analysis_selection_domain_token,
    build_selection_domain_clips_with_diagnostics,
    compute_selection_window_for_clips,
)
from frame_compare.orchestration.source_selection import SourceSelection, resolve_source_selection
from frame_compare.vs.types import HDRMetadata, SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs


MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""

RUN_FOLDERS_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    """Create a config file in the standard location."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(content, encoding="utf-8")
    return config_file


def create_video_files(input_dir: Path, *filenames: str) -> None:
    """Create empty video files for testing."""
    input_dir.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (input_dir / name).touch()


def write_metrics_cache(
    cache_dir: Path,
    *,
    source_path: Path,
    config: ConfigSchema,
    video_paths: list[Path] | None = None,
    selection_domain: str | None = None,
    analysis_source_path: Path | None = None,
) -> None:
    cache_inputs = [source_path] if video_paths is None else video_paths
    ordered_cache_inputs = _resolved_cache_inputs(cache_inputs, config)
    resolved_analysis_source_path = (
        ordered_cache_inputs[0] if analysis_source_path is None else analysis_source_path
    )
    if selection_domain is None:
        selection_domain = analysis_selection_domain_for_cache_inputs(
            ordered_cache_inputs,
            config,
            analysis_source_path=resolved_analysis_source_path,
        )
    metric_request = metric_cache_request_for_cache_inputs(
        ordered_cache_inputs,
        config,
        analysis_source_path=resolved_analysis_source_path,
    )
    metric_range = metric_request.metric_frame_range
    if metric_range is None:
        raise AssertionError("Prepared cache request must include an exact metric range")
    write_probe_cache_for_inputs(
        cache_dir.parent.parent / "clip_probe.toml",
        ordered_cache_inputs,
        config,
    )
    fingerprint = cache_io.compute_cache_key(
        ordered_cache_inputs,
        config.analysis,
        selection_domain=selection_domain,
        metric_request=metric_request,
    )
    stats_by_path = {path: path.stat() for path in ordered_cache_inputs}
    sampled_source_frames = None
    metric_frames: tuple[int, ...] = tuple(range(metric_range.start, metric_range.end_exclusive))
    if config.analysis.performance_mode.value == "performance":
        sampled_source_frames = tuple(
            frame
            for burst in plan_performance_bursts(
                window_start=metric_range.start,
                window_end_exclusive=metric_range.end_exclusive,
            )
            for frame in range(burst.start, burst.end_exclusive)
        )
        metric_frames = sampled_source_frames
    metrics = FrameMetrics(
        luminance=[0.1] * len(metric_frames),
        motion=[0.0 if frame == 0 else 0.2 for frame in metric_frames],
        metadata=MetricsMetadata(
            frame_count=len(metric_frames),
            fps=Fraction(24, 1),
            config_fingerprint=fingerprint,
            clips=[
                ClipIdentity(
                    path=str(path),
                    size=stats_by_path[path].st_size,
                    mtime=stats_by_path[path].st_mtime,
                )
                for path in ordered_cache_inputs
            ],
            source_frame_count=metric_range.source_frame_count,
            metric_source_start=metric_range.start,
            metric_source_end_exclusive=metric_range.end_exclusive,
            analysis_source_path=str(resolved_analysis_source_path),
            performance_mode=config.analysis.performance_mode.value,
            algorithm_id=metric_algorithm_id(config.analysis),
            metric_backend=metric_backend(config.analysis),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config.analysis),
            metric_active_rect=metric_request.metric_active_rect,
            active_rect_source=metric_request.active_rect_source,
            active_rect_detection_mode=metric_request.active_rect_detection_mode,
            active_rect_algorithm_id=metric_request.active_rect_algorithm_id,
            version=cache_io.CACHE_VERSION,
        ),
        sampled_source_frames=sampled_source_frames,
    )
    cache_io.save_metrics_cache(metrics, cache_dir)


def analysis_selection_domain_for_cache_inputs(
    video_paths: list[Path],
    config: ConfigSchema,
    *,
    analysis_source_path: Path | None = None,
) -> str:
    ordered_paths = _resolved_cache_inputs(video_paths, config)
    snapshots_by_path = {path: _clip_probe_snapshot_for_cache_input(path) for path in ordered_paths}
    clips = build_selection_domain_clips_with_diagnostics(
        ordered_paths=ordered_paths,
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=_resolved_cache_overrides(video_paths, config),
        labels_by_path={
            path: "Reference" if index == 0 else f"Encode {index}"
            for index, path in enumerate(ordered_paths)
        },
        match_fps=config.sources.match_fps,
        active_rect_detection=config.screenshots.active_rect_detection,
    ).clips
    window = compute_selection_window_for_clips(clips=clips, config=config)
    analysis_clip = clips[0]
    if analysis_source_path is not None:
        analysis_clip = next(clip for clip in clips if clip.path == analysis_source_path)
    return build_analysis_selection_domain_token(
        clips=clips,
        analysis_clip=analysis_clip,
        config=config,
        selection_window=window,
    )


def metric_cache_request_for_cache_inputs(
    video_paths: list[Path],
    config: ConfigSchema,
    *,
    analysis_source_path: Path | None = None,
) -> MetricCacheRequest:
    ordered_paths = _resolved_cache_inputs(video_paths, config)
    snapshots_by_path = {path: _clip_probe_snapshot_for_cache_input(path) for path in ordered_paths}
    clips = build_selection_domain_clips_with_diagnostics(
        ordered_paths=ordered_paths,
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=_resolved_cache_overrides(video_paths, config),
        labels_by_path={
            path: "Reference" if index == 0 else f"Encode {index}"
            for index, path in enumerate(ordered_paths)
        },
        match_fps=config.sources.match_fps,
        active_rect_detection=config.screenshots.active_rect_detection,
    ).clips
    analysis_clip = clips[0]
    if analysis_source_path is not None:
        analysis_clip = next(clip for clip in clips if clip.path == analysis_source_path)
    selection_window = compute_selection_window_for_clips(clips=clips, config=config)
    return metric_cache_request_for_clip(
        analysis_clip,
        selection_window=selection_window,
        fallback_detection_mode=config.screenshots.active_rect_detection.value,
    )


def write_probe_cache_for_inputs(
    cache_path: Path,
    video_paths: list[Path],
    config: ConfigSchema,
) -> None:
    del config
    entries = {}
    for path in video_paths:
        fingerprint = _clip_fingerprint_for_path(path)
        entries[compute_probe_cache_key(fingerprint)] = ClipProbeSnapshot(
            fingerprint=fingerprint,
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24, 1),
            is_hdr=False,
        )
    save_clip_probe_cache(cache_path, entries)


def _clip_probe_snapshot_for_cache_input(path: Path) -> ClipProbeSnapshot:
    return ClipProbeSnapshot(
        fingerprint=_clip_fingerprint_for_path(path),
        width=1920,
        height=1080,
        num_frames=100,
        fps=Fraction(24, 1),
        is_hdr=False,
    )


def _resolved_cache_inputs(video_paths: list[Path], config: ConfigSchema) -> list[Path]:
    return _resolve_cache_source_selection(video_paths, config).ordered_paths


def _resolved_cache_overrides(
    video_paths: list[Path],
    config: ConfigSchema,
) -> dict[Path, SourceOverrideConfig]:
    return dict(_resolve_cache_source_selection(video_paths, config).overrides_by_path)


def _resolve_cache_source_selection(
    video_paths: list[Path],
    config: ConfigSchema,
) -> SourceSelection:
    input_dir = _resolve_cache_input_dir(video_paths, config)
    return resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=video_paths,
        config=config.sources,
    )


def _resolve_cache_input_dir(video_paths: list[Path], config: ConfigSchema) -> Path:
    common_path = Path(os.path.commonpath([str(path) for path in video_paths]))
    configured_input_dir = Path(config.paths.input_dir)
    if configured_input_dir.is_absolute():
        return configured_input_dir

    candidates = [common_path, *common_path.parents]
    configured_parts = configured_input_dir.parts
    for candidate in candidates:
        if candidate.parts[-len(configured_parts) :] != configured_parts:
            continue
        if all(_is_relative_to(path, candidate) for path in video_paths):
            return candidate
    return common_path


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _clip_fingerprint_for_path(path: Path) -> ClipFingerprint:
    stat = path.stat()
    return ClipFingerprint(path=path, size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)


def clip_state(path: Path, *, label: str, num_frames: int = 100) -> ClipState:
    probe = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(path=path, size_bytes=0, mtime_ns=0),
        width=1920,
        height=1080,
        num_frames=num_frames,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    return ClipState(
        path=path,
        label=label,
        probe=probe,
        source_fps=probe.fps,
        effective_fps=probe.fps,
    )


class FakeVSLoader:
    def load(self, path: Path) -> SourceInfo:
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24, 1),
            format=cast(Any, object()),
            frame_props={},
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self) -> vs.Core:
        raise RuntimeError("ensure_core should not be called in tests")


class FakeHDRVSLoader(FakeVSLoader):
    def load(self, path: Path) -> SourceInfo:
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24, 1),
            format=cast(Any, object()),
            frame_props={},
            is_hdr=True,
            hdr_metadata=HDRMetadata(
                mastering_display="G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)",
                max_cll=1000,
                max_fall=400,
                color_primaries=9,
                transfer=16,
                matrix=9,
            ),
        )


class FakeFFmpegRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")
        self.calls.append((video.name, frame_num, output.name))

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        return HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=1,
            transfer=1,
            matrix=1,
        )
