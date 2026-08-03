from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

import frame_compare.vs.loader as vs_loader_module
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
from frame_compare.vs.types import HDRMetadata, SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs


class FakeVSLoader:
    def load(self, path: Path) -> SourceInfo:
        _ = path
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


class FakeFFmpegRunner:
    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        _, _, _ = video, frame_num, output
        raise AssertionError("FFmpeg extraction path is not exercised in this test")

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


def test_overlay_display_frame_number_matches_aligned_output_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[object] = []

    def _fake_render_frame(request: object) -> Path:
        captured.append(request)
        return cast(Any, request).output_path

    monkeypatch.setattr("frame_compare.render.batch.orchestrator.render_frame", _fake_render_frame)
    monkeypatch.setattr(vs_loader_module, "DefaultVSLoader", FakeVSLoader)

    config = ConfigSchema()

    workspace = WorkspacePaths(
        root=tmp_path.resolve(),
        input_dir=(tmp_path / "comparison_videos").resolve(),
        generated_root=(tmp_path / "generated").resolve(),
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
    )

    output = run_render_phase(
        ctx=ctx,
        frames=[10],
        runner=FakeFFmpegRunner(),
    )

    assert output.render.screenshot_dir == workspace.screenshots_dir
    assert "Reference" in output.render.screenshots_by_label
    assert output.render.screenshots_by_label["Reference"][0].name == "10 - ref.png"

    req = cast(Any, captured[0])
    assert req.frame_number == 20
    assert req.output_path.name == "10 - ref.png"
    assert req.overlay is not None
    assert req.overlay.label == "Reference"
    assert req.overlay.burn_in_label == "ref"
    assert req.overlay.display_frame_number == 10
