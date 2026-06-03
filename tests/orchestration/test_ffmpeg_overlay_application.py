from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

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
    def __init__(self) -> None:
        self.calls: list[tuple[Path, int, Path]] = []

    def extract_frame(self, video: Path, frame_num: int, output: Path, **_kwargs) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")
        self.calls.append((video, frame_num, output))

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


def test_ffmpeg_extraction_applies_overlay_post_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied: list[Path] = []

    def _record_apply(path: Path, _overlay) -> None:  # type: ignore[no-untyped-def]
        applied.append(path)

    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay_to_file", _record_apply)

    config = ConfigSchema(screenshots={"use_ffmpeg": True})

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
    )

    ctx = RunContext(
        config=config,
        workspace=workspace,
        reference=reference,
        comparisons=[],
        analysis_selection_domain="test-selection-domain",
        reporter=None,
    )

    runner = FakeFFmpegRunner()

    output = run_render_phase(
        ctx=ctx,
        frames=[0, 1],
        runner=runner,
    )

    assert output.render.screenshot_dir == workspace.screenshots_dir
    assert "Reference" in output.render.screenshots_by_label
    assert len(output.render.screenshots_by_label["Reference"]) == 2
    assert applied == output.render.screenshots_by_label["Reference"]
