from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

from frame_compare.analysis.types import SelectionBreakdown, SelectionDetail
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.execution import run_render_phase
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.types import HDRMetadata


class FakeFFmpegRunner:
    def extract_frame(self, video: Path, frame_num: int, output: Path, **_kwargs) -> None:
        _, _ = video, frame_num
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        _ = video
        return HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=1,
            transfer=1,
            matrix=1,
        )


def test_selection_labels_are_looked_up_in_reference_source_frame_domain_after_trim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_labels: list[str | None] = []

    def _record_apply(_path: Path, overlay) -> None:  # type: ignore[no-untyped-def]
        captured_labels.append(overlay.selection_label)

    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay_to_file", _record_apply)

    config = ConfigSchema(screenshots={"use_ffmpeg": True, "overlay_mode": "standard"})
    workspace = WorkspacePaths(
        root=tmp_path.resolve(),
        input_dir=(tmp_path / "comparison_videos").resolve(),
        run_dir=None,
        screenshots_dir=(tmp_path / "screenshots").resolve(),
        generated_dir=(tmp_path / "generated").resolve(),
        config_dir=(tmp_path / "config").resolve(),
        config_file=None,
    )

    fingerprint = ClipFingerprint(Path("ref.mkv"), 1, 1)
    probe = ClipProbeSnapshot(
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=200,
        fps=Fraction(24, 1),
        is_hdr=False,
    )

    # Reference was trimmed by 10 frames; aligned frame 0 maps to source frame 10.
    reference = ClipState(
        path=Path("ref.mkv"),
        label="Reference",
        probe=probe,
        source_fps=probe.fps,
        effective_fps=probe.fps,
    ).with_trim(trim_start_frames=10, trim_end_frame_inclusive=None)

    ctx = RunContext(
        config=config,
        workspace=workspace,
        reference=reference,
        comparisons=[],
        analysis_selection_domain="test-selection-domain",
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=190),
        reporter=None,
        selection_breakdown=SelectionBreakdown(quantile_dark=[10]),
    )

    run_render_phase(
        ctx=ctx,
        frames=[0],
        runner=FakeFFmpegRunner(),
    )

    assert captured_labels == ["Dark"]


def test_selection_details_are_looked_up_in_reference_source_frame_domain_after_trim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[str | None, str | None]] = []

    def _record_apply(_path: Path, overlay) -> None:  # type: ignore[no-untyped-def]
        detail_label = (
            overlay.selection_detail.label if overlay.selection_detail is not None else None
        )
        captured.append((overlay.selection_label, detail_label))

    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay_to_file", _record_apply)

    config = ConfigSchema(screenshots={"use_ffmpeg": True, "overlay_mode": "standard"})
    workspace = WorkspacePaths(
        root=tmp_path.resolve(),
        input_dir=(tmp_path / "comparison_videos").resolve(),
        run_dir=None,
        screenshots_dir=(tmp_path / "screenshots").resolve(),
        generated_dir=(tmp_path / "generated").resolve(),
        config_dir=(tmp_path / "config").resolve(),
        config_file=None,
    )

    fingerprint = ClipFingerprint(Path("ref.mkv"), 1, 1)
    probe = ClipProbeSnapshot(
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=200,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    reference = ClipState(
        path=Path("ref.mkv"),
        label="Reference",
        probe=probe,
        source_fps=probe.fps,
        effective_fps=probe.fps,
    ).with_trim(trim_start_frames=10, trim_end_frame_inclusive=None)

    ctx = RunContext(
        config=config,
        workspace=workspace,
        reference=reference,
        comparisons=[],
        analysis_selection_domain="test-selection-domain",
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=190),
        reporter=None,
        selection_details_by_source_frame={
            10: SelectionDetail(
                frame_index=10,
                label="User",
                source="analysis",
                timecode="00:00:00.417",
                clip_role="analyze",
                notes="user_override",
            )
        },
    )

    run_render_phase(
        ctx=ctx,
        frames=[0],
        runner=FakeFFmpegRunner(),
    )

    assert captured == [("User", "User")]
