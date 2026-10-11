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
    RunContext,
)
from frame_compare.orchestration.execution import run_render_phase
from frame_compare.render.types import OverlayConfig
from frame_compare.utils.media_facts import RenderedFrameFacts
from frame_compare.vs.types import HDRMetadata

from .execute_run_helpers import clip_state
from .phase_task_helpers import _workspace


class FakeFFmpegRunner:
    def extract_frame(
        self, video: Path, frame_num: int, output: Path, **_kwargs: object
    ) -> RenderedFrameFacts:
        _, _ = video, frame_num
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")
        return RenderedFrameFacts(source_frame=frame_num, picture_type="I")

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

    def _record_apply(_path: Path, overlay: OverlayConfig, _facts: RenderedFrameFacts) -> None:
        captured_labels.append(overlay.selection_label)

    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay_to_file", _record_apply)

    config = ConfigSchema.model_validate(
        {"screenshots": {"use_ffmpeg": True, "overlay_mode": "standard"}}
    )
    workspace = _workspace(
        tmp_path.resolve(),
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
        config_filename=None,
    )

    fingerprint = ClipFingerprint(Path("ref.mkv"), 1, 1)

    # Reference was trimmed by 10 frames; aligned frame 0 maps to source frame 10.
    reference = clip_state(
        fingerprint.path,
        label="Reference",
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=200,
        fps=Fraction(24, 1),
        is_hdr=False,
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


def test_selection_detail_label_is_looked_up_in_reference_source_frame_domain_after_trim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[str | None] = []

    def _record_apply(_path: Path, overlay: OverlayConfig, _facts: RenderedFrameFacts) -> None:
        captured.append(overlay.selection_label)

    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay_to_file", _record_apply)

    config = ConfigSchema.model_validate(
        {"screenshots": {"use_ffmpeg": True, "overlay_mode": "standard"}}
    )
    workspace = _workspace(
        tmp_path.resolve(),
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
        config_filename=None,
    )

    fingerprint = ClipFingerprint(Path("ref.mkv"), 1, 1)
    reference = clip_state(
        fingerprint.path,
        label="Reference",
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=200,
        fps=Fraction(24, 1),
        is_hdr=False,
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

    assert captured == ["User"]
