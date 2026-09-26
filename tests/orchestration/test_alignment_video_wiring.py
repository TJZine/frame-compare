"""Focused orchestration proof for the alignment video-loader seam."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from frame_compare.orchestration import phase_alignment
from frame_compare.orchestration.context import ClipActiveRect
from frame_compare.services.types import AlignmentResult
from frame_compare.utils.types import AlignmentRequest
from frame_compare.vs.loader import VSLoader
from tests.orchestration.phase_task_helpers import _clip, _context, _run_align_phase


def test_align_phase_passes_loader_and_active_rect_primitives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison.mkv", label="Comparison")
    ctx = _context(tmp_path, comparisons=[comparison])
    rect = ClipActiveRect(
        x=8,
        y=10,
        width=1920,
        height=1040,
        source="metadata",
        detection_mode="provided",
    )
    ctx.reference = replace(ctx.reference, active_rect=rect)
    ctx.comparisons = [replace(ctx.comparisons[0], active_rect=rect)]
    loader = cast(VSLoader, object())
    captured: dict[str, object] = {}

    def fake_align(
        request: AlignmentRequest,
        _config: object,
        **kwargs: object,
    ) -> list[AlignmentResult]:
        captured["request"] = request
        captured.update(kwargs)
        return [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="comparison.mkv",
                frame_offset=0,
                time_offset_seconds=0.0,
                correlation_score=1.0,
                algorithm="cross_correlation",
                source="computed",
            )
        ]

    monkeypatch.setattr(phase_alignment, "align_clips_from_request", fake_align)

    output = _run_align_phase(ctx, selected_frames=[0], vs_loader=loader)

    request = captured["request"]
    assert isinstance(request, AlignmentRequest)
    assert captured["vs_loader"] is loader
    assert (
        request.reference.active_rect_x,
        request.reference.active_rect_y,
        request.reference.active_rect_width,
        request.reference.active_rect_height,
    ) == (8, 10, 1920, 1040)
    assert (
        request.comparisons[0].active_rect_x,
        request.comparisons[0].active_rect_y,
        request.comparisons[0].active_rect_width,
        request.comparisons[0].active_rect_height,
    ) == (8, 10, 1920, 1040)
    assert output.comparisons[0].alignment is not None


def test_unapplied_result_never_reaches_alignment_trims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison.mkv", label="Comparison")
    ctx = _context(tmp_path, comparisons=[comparison])
    monkeypatch.setattr(
        phase_alignment,
        "align_clips_from_request",
        lambda *_args, **_kwargs: [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="comparison.mkv",
                frame_offset=None,
                time_offset_seconds=None,
                correlation_score=1.0,
                algorithm="cross_correlation",
                source="computed",
                applied=False,
                diagnostic="video_check_inconclusive",
            )
        ],
    )

    output = _run_align_phase(ctx, selected_frames=[0])

    assert output.comparisons[0].alignment is None
    assert output.reference.trim.trim_start_frames == 0
    assert output.comparisons[0].trim.trim_start_frames == 0
