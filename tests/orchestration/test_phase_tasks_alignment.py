"""Direct tests for orchestration phase task behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from frame_compare.orchestration import phase_tasks
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentResult
from tests.orchestration.phase_task_helpers import (
    _clip,
    _context,
)


def test_run_align_phase_applies_offsets_and_normalizes_selected_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    selected_frames = [0, 2, 50, 99]
    captured: dict[str, Any] = {}

    def _fake_align_clips(**kwargs: object) -> list[AlignmentResult]:
        captured.update(kwargs)
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=2,
                time_offset_seconds=0.08,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    output = phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)

    assert captured["reference"] == ctx.reference.path
    assert captured["comparisons"] == [comparison.path]
    assert captured["cache_dir"] == ctx.workspace.generated_dir
    assert captured["config"].sample_rate == 12000
    assert captured["config"].max_offset_seconds == 4.5
    assert captured["config"].use_vspreview is True
    assert captured["config"].cache_results is False
    assert output.reference.trim.trim_start_frames == 2
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert output.comparisons[0].alignment is not None
    assert output.comparisons[0].alignment.relative_offset_frames == 2
    assert output.selected_frames == [0, 48, 97]
    assert ctx.reference.trim.trim_start_frames == 0
    assert ctx.comparisons[0].alignment is None
    assert selected_frames == [0, 2, 50, 99]


def test_run_align_phase_raises_when_alignment_leaves_no_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(
        tmp_path / "comparison_videos" / "encode.mkv",
        label="Encode 1",
        num_frames=2,
    )
    ctx = _context(tmp_path, comparisons=[comparison])
    selected_frames = [0, 1]

    def _fake_align_clips(**_kwargs: object) -> list[AlignmentResult]:
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=100,
                time_offset_seconds=4.0,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_tasks, "align_clips", _fake_align_clips)

    with pytest.raises(AudioAlignmentError, match="No overlapping frames"):
        phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)


def test_run_align_phase_no_comparisons_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    selected_frames = [2, 4]

    def _unexpected_align(**_kwargs: object) -> list[AlignmentResult]:
        raise AssertionError("No comparisons should skip alignment work")

    monkeypatch.setattr(phase_tasks, "align_clips", _unexpected_align)

    output = phase_tasks.run_align_phase(ctx, selected_frames=selected_frames)

    assert output.selected_frames == [2, 4]
    assert output.comparisons == []
    assert selected_frames == [2, 4]
    assert ctx.comparisons == []
