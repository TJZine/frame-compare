"""Shared helpers for orchestration phase task tests."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from PIL import Image

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.loader import load_config
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.execution_types import RenderArtifacts
from frame_compare.render.types import RenderedClipFacts
from frame_compare.services.release_identity import ReleaseIdentity
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.utils.types import WorkspacePaths

MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[analysis]
random_frame_count = 3
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
    def extract_frame(
        self, _video: Path, frame_num: int, output: Path, **_kwargs: object
    ) -> RenderedFrameFacts:
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")
        return RenderedFrameFacts(source_frame=frame_num, picture_type="I")


def _render_artifacts(
    *,
    screenshots_by_label: dict[str, list[Path]],
    screenshot_dir: Path | None,
    source_frames_by_label: dict[str, list[int]] | None = None,
) -> RenderArtifacts:
    """Build explicit, invariant-valid render artifacts for orchestration tests."""
    geometry = RenderedGeometryFacts(
        source_size=(1920, 1080),
        active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
        cropped_size=(1920, 1080),
        scaled_size=(1920, 1080),
        final_canvas_size=(1920, 1080),
        is_noop=True,
    )
    frames = (
        {label: list(range(len(paths))) for label, paths in screenshots_by_label.items()}
        if source_frames_by_label is None
        else source_frames_by_label
    )
    return RenderArtifacts(
        screenshots_by_label=screenshots_by_label,
        frame_facts_by_label={
            label: [RenderedFrameFacts(source_frame=frame, picture_type="I") for frame in values]
            for label, values in frames.items()
        },
        clip_facts_by_label={
            label: RenderedClipFacts(
                size_bytes=0,
                source_resolution=(1920, 1080),
                source_total_frames=100,
                signal=SourceSignalFacts(is_hdr=False),
                presentation_state=PresentationState.SDR,
                tonemap_settings=None,
                geometry=geometry,
            )
            for label in screenshots_by_label
        },
        screenshot_dir=screenshot_dir,
    )


def _workspace(tmp_path: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        generated_root=tmp_path / "generated",
        run_dir=tmp_path / "run",
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


def _clip(
    path: Path,
    *,
    label: str,
    num_frames: int = 100,
    release_identity: ReleaseIdentity | None = None,
    label_is_explicit: bool = False,
) -> ClipState:
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
        release_identity=release_identity,
        label_is_explicit=label_is_explicit,
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
        analysis_clip=reference,
    )
