"""Shared helpers for orchestration phase task tests."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.loader import load_config
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.utils.types import WorkspacePaths

MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"

[analysis]
frame_count = 3
random_seed = 7

[audio_alignment]
enable = true
sample_rate = 12000
max_offset_seconds = 4.5
use_vspreview = true
force_interactive = false
cache_results = false
correlation_mode = "gcc_phat"
preprocessing_mode = "standard"
channel_strategy = "best_channel"
confidence_threshold = 0.25
ambiguity_peak_ratio = 1.5
window_length_seconds = 8.0
window_stride_seconds = 2.0
minimum_valid_windows = 2
consensus_minimum_ratio = 0.75
refinement_mode = "local"
refinement_sample_rate = 16000
reference_stream = 1
comparison_streams = { encode = 2 }

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


class _RenderRunner:
    pass


def _workspace(tmp_path: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )


def _create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> ConfigSchema:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(content, encoding="utf-8")
    return load_config(config_path)


def _clip(path: Path, *, label: str, num_frames: int = 100) -> ClipState:
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


def _context(tmp_path: Path, *, comparisons: list[ClipState] | None = None) -> RunContext:
    config = _create_config(tmp_path)
    reference_path = tmp_path / "comparison_videos" / "reference.mkv"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(b"reference")
    reference = _clip(reference_path, label="Reference")
    return RunContext(
        config=config,
        workspace=_workspace(tmp_path),
        reference=reference,
        comparisons=[] if comparisons is None else comparisons,
        analysis_selection_domain="test-selection-domain",
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
    )
