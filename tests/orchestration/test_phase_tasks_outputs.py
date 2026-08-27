"""Render-phase canonical metadata and source-frame mapping tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.types import FrameMetrics, MetricsMetadata, SelectionBreakdown
from frame_compare.config.schema import OverlayMode
from frame_compare.orchestration import phase_alignment, phase_render
from frame_compare.orchestration.context import ClipActiveRect
from frame_compare.render.types import (
    RenderedBatchResult,
    RenderedClipFacts,
    ScreenshotBatchRequest,
)
from frame_compare.services.release_identity import ContentIdentity, ReleaseIdentity
from frame_compare.services.types import AlignmentResult
from frame_compare.utils.media_facts import (
    PictureType,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
)
from frame_compare.vs.types import HDRMetadata
from tests.orchestration.phase_task_helpers import _clip, _context, _RenderRunner


def _result_for_requests(
    requests: list[ScreenshotBatchRequest],
    tmp_path: Path,
    *,
    picture_types: dict[str, list[PictureType | None]] | None = None,
) -> RenderedBatchResult:
    screenshots: dict[str, list[Path]] = {}
    frame_facts: dict[str, list[RenderedFrameFacts]] = {}
    clip_facts: dict[str, RenderedClipFacts] = {}
    for request in requests:
        screenshots[request.label] = [
            tmp_path / f"{request.clip_path.stem}-{frame}.png"
            for frame in request.comparison_frames
        ]
        values = (
            picture_types[request.label]
            if picture_types is not None and request.label in picture_types
            else ["I"] * len(request.source_frames)
        )
        frame_facts[request.label] = [
            RenderedFrameFacts(source_frame=frame, picture_type=picture_type)
            for frame, picture_type in zip(request.source_frames, values, strict=True)
        ]
        active = request.active_picture
        geometry = RenderedGeometryFacts(
            source_size=request.source_resolution,
            active_picture=active,
            cropped_size=(active.width, active.height),
            scaled_size=(active.width, active.height),
            final_canvas_size=(active.width, active.height),
            is_noop=active.is_full_frame,
        )
        clip_facts[request.label] = RenderedClipFacts(
            size_bytes=request.size_bytes,
            source_resolution=request.source_resolution,
            source_total_frames=request.source_total_frames,
            signal=request.signal,
            presentation_state=PresentationState.SDR,
            tonemap_settings=None,
            geometry=geometry,
        )
    return RenderedBatchResult(screenshots, frame_facts, clip_facts)


def _capture_detailed_render(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    picture_types: dict[str, list[PictureType | None]] | None = None,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def _fake(**kwargs: Any) -> RenderedBatchResult:
        captured.update(kwargs)
        return _result_for_requests(kwargs["batch_requests"], tmp_path, picture_types=picture_types)

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch_detailed",
        _fake,
    )
    return captured


def test_run_render_phase_maps_comparison_and_source_frames_and_preserves_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.screenshots.overlay_mode = OverlayMode.NONE
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.comparisons = [comparison.with_trim(trim_start_frames=1, trim_end_frame_inclusive=18)]
    ctx.selection_breakdown = SelectionBreakdown(quantile_dark=[4])
    captured = _capture_detailed_render(
        monkeypatch,
        tmp_path,
        picture_types={"Reference": ["B"], "Encode 1": ["P"]},
    )

    output = phase_render.run_render_phase(ctx, frames=[1], runner=cast(Any, _RenderRunner()))

    requests = captured["batch_requests"]
    assert [
        (request.label, request.comparison_frames, request.source_frames) for request in requests
    ] == [
        ("Reference", [1], [4]),
        ("Encode 1", [1], [2]),
    ]
    assert requests[0].selection_labels == ["Dark"]
    assert requests[0].filename_label == "reference"
    assert captured["output_dir"] == ctx.workspace.screenshots_dir
    assert captured["options"].overlay_mode == OverlayMode.NONE
    assert captured["options"].parallelism == 2
    assert output.render.frame_facts_by_label["Reference"] == [
        RenderedFrameFacts(source_frame=4, picture_type="B")
    ]
    assert output.render.warnings == []


def test_run_render_phase_maps_multiple_clips_in_stable_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comp_a = _clip(tmp_path / "comparison_videos" / "a.mkv", label="Encode A")
    comp_b = _clip(tmp_path / "comparison_videos" / "b.mkv", label="Encode B")
    ctx = _context(tmp_path, comparisons=[comp_a, comp_b])
    ctx.reference = ctx.reference.with_trim(trim_start_frames=3, trim_end_frame_inclusive=20)
    ctx.comparisons = [
        comp_a.with_trim(trim_start_frames=1, trim_end_frame_inclusive=18),
        comp_b.with_trim(trim_start_frames=5, trim_end_frame_inclusive=30),
    ]
    captured = _capture_detailed_render(monkeypatch, tmp_path)

    phase_render.run_render_phase(ctx, frames=[1, 2], runner=cast(Any, _RenderRunner()))

    requests = captured["batch_requests"]
    assert [(request.label, request.source_frames) for request in requests] == [
        ("Reference", [4, 5]),
        ("Encode A", [2, 3]),
        ("Encode B", [6, 7]),
    ]
    assert [request.comparison_frames for request in requests] == [[1, 2], [1, 2], [1, 2]]


def test_run_render_phase_adds_unique_progress_labels_without_changing_canonical_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = ReleaseIdentity(
        ContentIdentity("Example", year=2026),
        service="ATV",
        source_type="WEB-DL",
        dynamic_range_claims=("DV", "HDR10+"),
        release_group="Kitsune",
    )
    comparison = _clip(
        tmp_path / "comparison_videos" / "comparison.mkv",
        label="Canonical comparison",
        release_identity=identity,
    )
    generated_progress_label = "Comparison 1 | ATV WEB-DL | DV HDR10+ | Kitsune"
    explicit = _clip(
        tmp_path / "comparison_videos" / "explicit.mkv",
        label=generated_progress_label,
        release_identity=identity,
        label_is_explicit=True,
    )
    ctx = _context(tmp_path, comparisons=[comparison, explicit])
    ctx.reference = replace(ctx.reference, release_identity=identity)
    captured = _capture_detailed_render(monkeypatch, tmp_path)

    phase_render.run_render_phase(ctx, frames=[1], runner=cast(Any, _RenderRunner()))

    requests = captured["batch_requests"]
    assert [request.label for request in requests] == [
        "Reference",
        "Canonical comparison",
        generated_progress_label,
    ]
    assert [request.progress_label for request in requests] == [
        "Reference | ATV WEB-DL | DV HDR10+ | Kitsune",
        f"{generated_progress_label} (2)",
        generated_progress_label,
    ]


def test_run_render_phase_maps_canonical_clip_facts_without_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = replace(
        ctx.reference,
        active_rect=ClipActiveRect(0, 140, 1920, 800, "metadata", "provided"),
        probe=replace(
            ctx.reference.probe,
            fingerprint=replace(ctx.reference.probe.fingerprint, size_bytes=5_368_709_120),
            is_hdr=True,
            hdr_metadata=HDRMetadata(
                mastering_display="G(13250,34500)B(7500,3000)R(34000,16000)"
                "WP(15635,16450)L(10000000,50)",
                max_cll=982,
                max_fall=244,
                color_primaries=9,
                transfer=16,
                matrix=9,
            ),
            preserved_frame_props={
                "_Primaries": 9,
                "_Transfer": 16,
                "_Matrix": 9,
                "_Range": 0,
                "DolbyVisionRPU": 1,
                "DolbyVision_L1_Maximum": 450.0,
            },
        ),
    )
    captured = _capture_detailed_render(monkeypatch, tmp_path)

    phase_render.run_render_phase(ctx, frames=[2], runner=cast(Any, _RenderRunner()))

    request = captured["batch_requests"][0]
    assert request.size_bytes == 5_368_709_120
    assert request.source_resolution == (1920, 1080)
    assert request.source_total_frames == 100
    assert request.signal.is_hdr is True
    assert (request.signal.primaries, request.signal.transfer, request.signal.matrix) == (9, 16, 9)
    assert request.signal.color_range == "limited"
    assert request.signal.dolby_vision_rpu is True
    assert request.signal.hdr_static is not None
    assert request.signal.hdr_static.mastering_min_nits == pytest.approx(0.005)
    assert request.signal.hdr_static.mastering_max_nits == pytest.approx(1000)
    assert request.active_picture.provenance == "dolby_vision_l5"
    assert request.active_picture.is_full_frame is False


@pytest.mark.parametrize(
    ("preserved_frame_props", "expected"),
    [
        ({}, (9, 16, 9)),
        ({"_Primaries": 2, "_Transfer": 2, "_Matrix": 2}, (9, 16, 9)),
        ({"_Primaries": 1, "_Transfer": 17, "_Matrix": 0}, (1, 17, 0)),
    ],
)
def test_run_render_phase_uses_observed_signal_then_hdr_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    preserved_frame_props: dict[str, int],
    expected: tuple[int, int, int],
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.reference = replace(
        ctx.reference,
        probe=replace(
            ctx.reference.probe,
            is_hdr=True,
            hdr_metadata=HDRMetadata(None, None, None, 9, 16, 9),
            preserved_frame_props=preserved_frame_props,
        ),
    )
    captured = _capture_detailed_render(monkeypatch, tmp_path)

    phase_render.run_render_phase(ctx, frames=[2], runner=cast(Any, _RenderRunner()))

    request = captured["batch_requests"][0]
    assert (request.signal.primaries, request.signal.transfer, request.signal.matrix) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("G(13250,34500)L(10000000,50)", (0.005, 1000.0)),
        ("L(1000.0,0.0050)", (0.005, 1000.0)),
        ("L(1000,invalid)", (None, None)),
    ],
)
def test_mastering_luminance_accepts_known_encodings(
    value: str, expected: tuple[float | None, float | None]
) -> None:
    actual = phase_render._mastering_luminance(value)
    if expected[0] is None or expected[1] is None:
        assert actual == expected
    else:
        assert actual == pytest.approx(expected)


def test_run_render_phase_aggregates_missing_picture_type_once_per_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode")
    ctx = _context(tmp_path, comparisons=[comparison])
    _capture_detailed_render(
        monkeypatch,
        tmp_path,
        picture_types={"Reference": [None, None], "Encode": ["I", None]},
    )

    output = phase_render.run_render_phase(ctx, frames=[1, 2], runner=cast(Any, _RenderRunner()))

    assert output.render.warnings == [
        "render: picture type unavailable for 2 selected frame(s) in Reference; "
        "screenshots were rendered without picture-type metadata",
        "render: picture type unavailable for 1 selected frame(s) in Encode; "
        "screenshots were rendered without picture-type metadata",
    ]


def test_run_render_phase_rejects_backend_source_frame_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)

    def _fake(**kwargs: Any) -> RenderedBatchResult:
        result = _result_for_requests(kwargs["batch_requests"], tmp_path)
        return RenderedBatchResult(
            result.screenshots_by_label,
            {"Reference": [RenderedFrameFacts(source_frame=99, picture_type="I")]},
            result.clip_facts_by_label,
        )

    monkeypatch.setattr(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch_detailed",
        _fake,
    )

    with pytest.raises(ValueError, match="do not match source mapping"):
        phase_render.run_render_phase(ctx, frames=[1], runner=cast(Any, _RenderRunner()))


def test_run_render_phase_rejects_analysis_fallback_when_overlap_is_smaller_than_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison = _clip(tmp_path / "comparison_videos" / "encode.mkv", label="Encode 1")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.config.analysis = ctx.config.analysis.model_copy(
        update={"random_frame_count": 0, "dark_frame_count": 2, "bright_frame_count": 2}
    )
    ctx.analysis_metrics = FrameMetrics(
        luminance=[float(frame) / 99.0 for frame in range(100)],
        motion=[0.0 for _ in range(100)],
        metadata=MetricsMetadata(
            frame_count=100,
            fps=ctx.reference.effective_fps,
            config_fingerprint="test",
            clips=[],
        ),
    )

    monkeypatch.setattr(
        phase_alignment,
        "align_clips_from_request",
        lambda *_args, **_kwargs: [
            AlignmentResult(
                reference_clip="reference.mkv",
                comparison_clip="encode.mkv",
                frame_offset=98,
                time_offset_seconds=4.08,
                correlation_score=0.9,
                algorithm="cross_correlation",
                source="computed",
            )
        ],
    )

    with pytest.raises(SelectionError) as exc_info:
        phase_alignment.run_align_phase(ctx, selected_frames=[0, 1, 2, 3])

    assert exc_info.value.context.details == {
        "reason": "insufficient generated candidates after alignment",
        "requested": 4,
        "found": 2,
    }
