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
    RunContext,
)
from frame_compare.orchestration.execution import run_render_phase
from frame_compare.render.geometry import RenderGeometryPlan
from frame_compare.render.types import RenderedFrameResult
from frame_compare.utils.media_facts import RenderedFrameFacts
from frame_compare.vs.types import HDRMetadata, SourceInfo

from .execute_run_helpers import clip_state
from .phase_task_helpers import _workspace

if TYPE_CHECKING:
    import vapoursynth as vs


class FakeVSLoader:
    def __init__(self, memory_limit_mb: int | None = None) -> None:
        assert memory_limit_mb is None

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
    def extract_frame(
        self,
        video: Path,
        frame_num: int,
        output: Path,
        *,
        geometry_plan: RenderGeometryPlan | None = None,
    ) -> RenderedFrameFacts:
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

    def _fake_render_frame(request: object) -> RenderedFrameResult:
        captured.append(request)
        typed_request = cast(Any, request)
        return RenderedFrameResult(
            path=typed_request.output_path,
            facts=RenderedFrameFacts(source_frame=typed_request.frame_number, picture_type="I"),
        )

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_frame_detailed", _fake_render_frame
    )
    monkeypatch.setattr(vs_loader_module, "DefaultVSLoader", FakeVSLoader)

    config = ConfigSchema()

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
    assert req.overlay.comparison_frame == 10
    assert req.overlay.source_frame == 20
