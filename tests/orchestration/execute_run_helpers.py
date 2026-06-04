"""Shared helpers for execute_run orchestration tests."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PIL import Image

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot, ClipState
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    save_clip_probe_cache,
)
from frame_compare.orchestration.selection_domain import (
    build_analysis_selection_domain_token,
    build_selection_domain_clips,
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
) -> None:
    cache_inputs = [source_path] if video_paths is None else video_paths
    ordered_cache_inputs = _resolved_cache_inputs(cache_inputs, config)
    if selection_domain is None:
        selection_domain = analysis_selection_domain_for_cache_inputs(ordered_cache_inputs, config)
    write_probe_cache_for_inputs(
        cache_dir.parent.parent / "clip_probe.toml",
        ordered_cache_inputs,
        config,
    )
    fingerprint = cache_io.compute_cache_key(
        ordered_cache_inputs,
        config.analysis,
        selection_domain=selection_domain,
    )
    stats_by_path = {path: path.stat() for path in ordered_cache_inputs}
    metrics = FrameMetrics(
        luminance=[0.1] * 100,
        motion=[0.2] * 100,
        metadata=MetricsMetadata(
            frame_count=100,
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
            version=cache_io.CACHE_VERSION,
        ),
    )
    cache_io.save_metrics_cache(metrics, cache_dir)


def analysis_selection_domain_for_cache_inputs(
    video_paths: list[Path],
    config: ConfigSchema,
) -> str:
    ordered_paths = _resolved_cache_inputs(video_paths, config)
    snapshots_by_path = {path: _clip_probe_snapshot_for_cache_input(path) for path in ordered_paths}
    clips = build_selection_domain_clips(
        ordered_paths=ordered_paths,
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=_resolved_cache_overrides(video_paths, config),
    )
    window = compute_selection_window_for_clips(clips=clips, config=config)
    return build_analysis_selection_domain_token(
        clips=clips,
        config=config,
        selection_window=window,
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
    input_dir = video_paths[0].parent
    return resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=video_paths,
        config=config.sources,
    )


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
