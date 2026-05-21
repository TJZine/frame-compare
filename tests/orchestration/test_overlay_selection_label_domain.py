from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

from frame_compare.analysis.types import SelectionBreakdown
from frame_compare.config import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.execution import run_render_phase
from frame_compare.orchestration.types import RunArtifacts
from frame_compare.utils.types import WorkspacePaths


class FakeFFmpegRunner:
    def extract_frame(self, _video: Path, _frame_num: int, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")

    def probe_hdr(self, _video: Path):  # type: ignore[override]
        from frame_compare.vs.types import HDRMetadata

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
        reporter=None,
        selection_breakdown=SelectionBreakdown(quantile_dark=[10]),
    )

    artifacts = RunArtifacts()

    run_render_phase(
        ctx=ctx,
        frames=[0],
        runner=FakeFFmpegRunner(),
        artifacts=artifacts,
    )

    assert captured_labels == ["Dark"]
