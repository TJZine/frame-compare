from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.execution import run_render_phase
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.utils.media_facts import RenderedFrameFacts
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.types import HDRMetadata


def test_ffmpeg_extraction_applies_overlay_post_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    applied: list[tuple[Path, object, RenderedFrameFacts]] = []

    def _record_apply(path: Path, overlay: object, facts: RenderedFrameFacts) -> None:
        applied.append((path, overlay, facts))

    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay_to_file", _record_apply)

    config = ConfigSchema(screenshots={"use_ffmpeg": True})

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
    )

    ctx = RunContext(
        config=config,
        workspace=workspace,
        reference=reference,
        comparisons=[],
        analysis_selection_domain="test-selection-domain",
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
        reporter=None,
    )

    runner = DefaultFFmpegRunner()
    calls: list[tuple[Path, int, Path]] = []
    batch_calls: list[tuple[Path, list[int]]] = []

    def _extract_frame(
        video: Path, frame_num: int, output: Path, **_kwargs: object
    ) -> RenderedFrameFacts:
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")
        calls.append((video, frame_num, output))
        return RenderedFrameFacts(source_frame=frame_num, picture_type="I")

    def _extract_frames(
        video: Path,
        frame_nums: Sequence[int],
        output_dir: Path,
        **_kwargs: object,
    ) -> list[RenderedFrameFacts]:
        batch_calls.append((video, list(frame_nums)))
        for index in range(len(frame_nums)):
            Image.new("RGB", (10, 10), color=(0, 0, 0)).save(
                output_dir / f"{index:09d}.png", format="PNG"
            )
        return [
            RenderedFrameFacts(source_frame=frame_num, picture_type="I") for frame_num in frame_nums
        ]

    def _probe_hdr(video: Path) -> HDRMetadata | None:
        _ = video
        return HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=1,
            transfer=1,
            matrix=1,
        )

    monkeypatch.setattr(runner, "extract_frame", _extract_frame)
    monkeypatch.setattr(runner, "extract_frames", _extract_frames)
    monkeypatch.setattr(runner, "probe_hdr", _probe_hdr)

    output = run_render_phase(
        ctx=ctx,
        frames=[0, 1],
        runner=runner,
    )

    assert output.render.screenshot_dir == workspace.screenshots_dir
    assert "Reference" in output.render.screenshots_by_label
    assert len(output.render.screenshots_by_label["Reference"]) == 2
    assert [path for path, _overlay, _facts in applied] == output.render.screenshots_by_label[
        "Reference"
    ]
    assert [facts for _path, _overlay, facts in applied] == [
        RenderedFrameFacts(source_frame=0, picture_type="I"),
        RenderedFrameFacts(source_frame=1, picture_type="I"),
    ]
    assert batch_calls == [(Path("ref.mkv"), [0, 1])]
    assert calls == []
