"""Tests for geometry and active-rectangle provenance during batch expansion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ConfigSchema
from frame_compare.render.batch.expansion import expand_batch_render_requests
from frame_compare.render.geometry import GeometryMargins, GeometryRect
from frame_compare.render.types import (
    OverlayDiagnosticMetadata,
    OverlayDolbyVisionMetadata,
    OverlayMode,
    ScreenshotBatchRequest,
)


def _dovi_l5_metadata(
    *,
    left: int | None,
    right: int | None,
    top: int | None,
    bottom: int | None,
) -> OverlayDiagnosticMetadata:
    return OverlayDiagnosticMetadata(
        dolby_vision=OverlayDolbyVisionMetadata(
            rpu_present=True,
            l5_left=left,
            l5_right=right,
            l5_top=top,
            l5_bottom=bottom,
        )
    )


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_attaches_aligned_geometry_after_loading_dimensions(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()

    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]

    ref_metadata = OverlayDiagnosticMetadata(
        dolby_vision=OverlayDolbyVisionMetadata(
            rpu_present=True,
            l5_left=240,
            l5_right=240,
            l5_top=0,
            l5_bottom=0,
        )
    )
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=[ref_metadata, ref_metadata],
        diagnostic_metadata_trusted_for_geometry=True,
        probe_width=3840,
        probe_height=2160,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1280,
        probe_height=720,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req1, req2],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    ref_plan = requests[0].geometry_plan
    assert ref_plan is not None
    assert requests[1].geometry_plan is ref_plan
    assert ref_plan.active_rect_source == "metadata"
    assert ref_plan.crop.left == 240
    assert ref_plan.crop.right == 240
    assert ref_plan.final_canvas_size == (1440, 1080)
    assert requests[0].overlay is not None
    assert requests[0].overlay.resolution == (1440, 1080)
    assert (
        requests[0].overlay.resolution_summary == "1920 × 1080 → 1440 × 1080  (original → target)"
    )
    assert requests[0].overlay.origin == ref_plan.overlay_origin

    enc_plan = requests[2].geometry_plan
    assert enc_plan is not None
    assert enc_plan.source.width == 1440
    assert enc_plan.source.height == 1080
    assert enc_plan.final_canvas_size == (1440, 1080)
    assert requests[2].overlay is not None
    assert requests[2].overlay.resolution == (1440, 1080)
    assert requests[2].overlay.resolution_summary == "1440 × 1080  (native)"
    assert requests[2].overlay.origin == enc_plan.overlay_origin


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_maps_aligned_config_to_geometry_options(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(
        screenshots={
            "geometry_mode": "aligned",
            "active_rect_detection": "aspect_ratio",
            "aligned_scale_policy": "smallest_active",
        }
    )
    ffmpeg_runner = MagicMock()
    source_infos = []
    for width, height in ((1920, 800), (1920, 800), (3840, 2160)):
        source_info = MagicMock()
        source_info.width = width
        source_info.height = height
        source_info.num_frames = 100
        source_info.is_hdr = False
        source_infos.append(source_info)
    mock_prepare.side_effect = [
        (MagicMock(name="fhd_a"), None, None, source_infos[0]),
        (MagicMock(name="fhd_b"), None, None, source_infos[1]),
        (MagicMock(name="uhd"), None, None, source_infos[2]),
    ]
    batch_requests = [
        ScreenshotBatchRequest(
            clip_path=Path(f"{label}.mkv"),
            label=label,
            source_frames=[10],
            display_frames=[10],
            selection_labels=[None],
            probe_width=width,
            probe_height=height,
            probe_num_frames=100,
            probe_is_hdr=False,
        )
        for label, width, height in (
            ("FHD A", 1920, 800),
            ("FHD B", 1920, 800),
            ("UHD", 3840, 2160),
        )
    ]

    requests, _ = expand_batch_render_requests(
        batch_requests,
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    plans = [request.geometry_plan for request in requests]
    assert all(plan is not None for plan in plans)
    assert [plan.final_canvas_size for plan in plans if plan is not None] == [(1920, 800)] * 3
    assert plans[2] is not None
    assert plans[2].active_rect_source == "aspect-ratio-derived"
    assert plans[2].active_rect == GeometryRect(0, 280, 3840, 1600)
    assert requests[2].overlay is not None
    assert requests[2].overlay.resolution == (1920, 800)
    assert requests[2].overlay.resolution_summary == "3840 × 2160 → 1920 × 800  (original → target)"


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_marks_same_canvas_aligned_transform_as_target(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(
        screenshots={
            "geometry_mode": "aligned",
            "active_rect_detection": "aspect_ratio",
            "aligned_scale_policy": "explicit_size",
            "aligned_target_width": 3840,
            "aligned_target_height": 2160,
        }
    )
    ffmpeg_runner = MagicMock()
    source_infos = []
    for width, height in ((1920, 800), (1920, 800), (3840, 2160)):
        source_info = MagicMock()
        source_info.width = width
        source_info.height = height
        source_info.num_frames = 100
        source_info.is_hdr = False
        source_infos.append(source_info)
    mock_prepare.side_effect = [
        (MagicMock(name="fhd_a"), None, None, source_infos[0]),
        (MagicMock(name="fhd_b"), None, None, source_infos[1]),
        (MagicMock(name="uhd"), None, None, source_infos[2]),
    ]
    batch_requests = [
        ScreenshotBatchRequest(
            clip_path=Path(f"{label}.mkv"),
            label=label,
            source_frames=[10],
            display_frames=[10],
            selection_labels=[None],
            probe_width=width,
            probe_height=height,
            probe_num_frames=100,
            probe_is_hdr=False,
        )
        for label, width, height in (
            ("FHD A", 1920, 800),
            ("FHD B", 1920, 800),
            ("UHD", 3840, 2160),
        )
    ]

    requests, _ = expand_batch_render_requests(
        batch_requests,
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    uhd_plan = requests[2].geometry_plan
    assert uhd_plan is not None
    assert uhd_plan.final_canvas_size == (3840, 2160)
    assert uhd_plan.crop == GeometryMargins(top=280, bottom=280)
    assert requests[2].overlay is not None
    assert (
        requests[2].overlay.resolution_summary == "3840 × 2160 → 3840 × 2160  (original → target)"
    )


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_aligns_mixed_dimensions_with_explicit_active_rects(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()

    source_infos = []
    for width, height, num_frames in ((1920, 1080, 180), (1440, 800, 160), (1280, 720, 140)):
        source_info = MagicMock()
        source_info.width = width
        source_info.height = height
        source_info.num_frames = num_frames
        source_info.is_hdr = False
        source_infos.append(source_info)
    clips = [MagicMock(name=f"clip_{idx}") for idx in range(3)]
    mock_prepare.side_effect = [
        (clips[0], None, "HDR10", source_infos[0]),
        (clips[1], None, None, source_infos[1]),
        (clips[2], None, None, source_infos[2]),
    ]
    requests_in = [
        ScreenshotBatchRequest(
            clip_path=Path("reference.mkv"),
            label="Reference",
            source_frames=[10],
            display_frames=[0],
            selection_labels=["Dark"],
            probe_width=1920,
            probe_height=1080,
            probe_num_frames=180,
            probe_is_hdr=True,
            active_rect=GeometryRect(240, 140, 1440, 800),
            filename_label="reference",
        ),
        ScreenshotBatchRequest(
            clip_path=Path("encode-a.mkv"),
            label="Encode 1",
            source_frames=[20],
            display_frames=[0],
            selection_labels=["Dark"],
            probe_width=1440,
            probe_height=800,
            probe_num_frames=160,
            probe_is_hdr=False,
            active_rect=GeometryRect(0, 0, 1440, 800),
            filename_label="encode-a",
        ),
        ScreenshotBatchRequest(
            clip_path=Path("encode-b.mkv"),
            label="Encode 2",
            source_frames=[30],
            display_frames=[0],
            selection_labels=["Dark"],
            probe_width=1280,
            probe_height=720,
            probe_num_frames=140,
            probe_is_hdr=False,
            active_rect=GeometryRect(0, 0, 1280, 720),
            filename_label="encode-b",
        ),
    ]

    requests, label_to_range = expand_batch_render_requests(
        requests_in,
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    assert [(request.clip, request.frame_number, request.output_path) for request in requests] == [
        (clips[0], 10, Path("out/0 - reference.png")),
        (clips[1], 20, Path("out/0 - encode-a.png")),
        (clips[2], 30, Path("out/0 - encode-b.png")),
    ]
    assert label_to_range == {
        "Reference": range(0, 1),
        "Encode 1": range(1, 2),
        "Encode 2": range(2, 3),
    }

    plans = [request.geometry_plan for request in requests]
    assert all(plan is not None for plan in plans)
    assert [
        (
            plan.active_rect,
            plan.active_rect_source,
            plan.crop,
            plan.scaled_size,
            plan.pad,
            plan.final_canvas_size,
        )
        for plan in plans
        if plan is not None
    ] == [
        (
            GeometryRect(240, 140, 1440, 800),
            "explicit",
            GeometryMargins(left=240, top=140, right=240, bottom=140),
            (1440, 800),
            GeometryMargins(),
            (1440, 800),
        ),
        (
            GeometryRect(0, 0, 1440, 800),
            "explicit",
            GeometryMargins(),
            (1440, 800),
            GeometryMargins(),
            (1440, 800),
        ),
        (
            GeometryRect(0, 0, 1280, 720),
            "explicit",
            GeometryMargins(),
            (1422, 800),
            GeometryMargins(left=9, right=9),
            (1440, 800),
        ),
    ]
    assert [
        (
            request.overlay.resolution if request.overlay is not None else None,
            request.overlay.resolution_summary if request.overlay is not None else None,
            request.overlay.base_text if request.overlay is not None else None,
            request.overlay.origin if request.overlay is not None else None,
            request.overlay.hdr_info if request.overlay is not None else None,
            request.overlay.num_frames if request.overlay is not None else None,
        )
        for request in requests
    ] == [
        (
            (1440, 800),
            "1920 × 1080 → 1440 × 800  (original → target)",
            None,
            (10, 10),
            "HDR10",
            180,
        ),
        (
            (1440, 800),
            "1440 × 800  (native)",
            None,
            (10, 10),
            None,
            160,
        ),
        (
            (1440, 800),
            "1280 × 720 → 1440 × 800  (original → target)",
            None,
            (19, 10),
            None,
            140,
        ),
    ]


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_ignores_overlay_metadata_for_geometry_without_trust(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=[
            _dovi_l5_metadata(left=160, right=160, top=0, bottom=0),
            _dovi_l5_metadata(left=160, right=160, top=0, bottom=0),
        ],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1440,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req1, req2],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
        warnings=warnings,
    )

    ref_plan = requests[0].geometry_plan
    assert ref_plan is not None
    assert ref_plan.active_rect_source == "dimension-derived"
    assert ref_plan.active_rect == GeometryRect(240, 0, 1440, 1080)
    assert warnings == []


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_uses_prepared_active_rect_provenance_without_redetection(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        active_rect=GeometryRect(0, 140, 1920, 800),
        active_rect_source="content-derived",
        active_rect_detection_mode="auto",
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        active_rect=GeometryRect(0, 0, 1440, 1080),
        active_rect_source="full-frame",
        active_rect_detection_mode="provided",
        probe_width=1440,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req1, req2],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    ref_plan = requests[0].geometry_plan
    enc_plan = requests[1].geometry_plan
    assert ref_plan is not None
    assert enc_plan is not None
    assert ref_plan.active_rect == GeometryRect(0, 140, 1920, 800)
    assert ref_plan.active_rect_source == "content-derived"
    assert enc_plan.active_rect == GeometryRect(0, 0, 1440, 1080)
    assert enc_plan.active_rect_source == "full-frame"


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_explicit_active_rect_beats_metadata_rect(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    source_info = MagicMock()
    source_info.width = 1920
    source_info.height = 1080
    source_info.num_frames = 150
    source_info.is_hdr = False
    mock_prepare.return_value = (MagicMock(name="clip"), None, None, source_info)
    req = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        diagnostic_metadata=[
            _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
        ],
        diagnostic_metadata_trusted_for_geometry=True,
        active_rect=GeometryRect(160, 0, 1600, 1080),
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    plan = requests[0].geometry_plan
    assert plan is not None
    assert plan.active_rect_source == "explicit"
    assert plan.active_rect == GeometryRect(160, 0, 1600, 1080)
    assert plan.crop == GeometryMargins(left=160, right=160)


@pytest.mark.parametrize(
    ("diagnostic_metadata", "expected_reason"),
    [
        (
            [
                _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
                _dovi_l5_metadata(left=120, right=120, top=0, bottom=0),
            ],
            "selected-frame Dolby Vision L5 margins were inconsistent",
        ),
        (
            [
                _dovi_l5_metadata(left=240, right=None, top=0, bottom=0),
                _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
            ],
            "one or more selected-frame entries had partial Dolby Vision L5 margins",
        ),
        (
            [
                _dovi_l5_metadata(left=1200, right=1200, top=0, bottom=0),
                _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
            ],
            "one or more selected-frame entries had invalid Dolby Vision L5 margins",
        ),
        (
            [
                OverlayDiagnosticMetadata(
                    dolby_vision=OverlayDolbyVisionMetadata(rpu_present=True)
                ),
                _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
            ],
            "one or more selected-frame entries had no Dolby Vision L5 margins",
        ),
    ],
)
@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_rejected_trusted_metadata_falls_back_with_warning(
    mock_prepare: MagicMock,
    diagnostic_metadata: list[OverlayDiagnosticMetadata],
    expected_reason: str,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=diagnostic_metadata,
        diagnostic_metadata_trusted_for_geometry=True,
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1440,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req1, req2],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
        warnings=warnings,
    )

    ref_plan = requests[0].geometry_plan
    assert ref_plan is not None
    assert ref_plan.active_rect_source == "dimension-derived"
    assert ref_plan.active_rect == GeometryRect(240, 0, 1440, 1080)
    assert len(warnings) == 1
    assert "Dolby Vision L5 active rect metadata" in warnings[0]
    assert "Reference" in warnings[0]
    assert expected_reason in warnings[0]


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_rejected_trusted_metadata_falls_back_to_explicit_with_warning(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    source_info = MagicMock()
    source_info.width = 1920
    source_info.height = 1080
    source_info.num_frames = 150
    source_info.is_hdr = False
    mock_prepare.return_value = (MagicMock(name="clip"), None, None, source_info)
    req = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=[
            _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
            _dovi_l5_metadata(left=120, right=120, top=0, bottom=0),
        ],
        diagnostic_metadata_trusted_for_geometry=True,
        active_rect=GeometryRect(160, 0, 1600, 1080),
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
        warnings=warnings,
    )

    plan = requests[0].geometry_plan
    assert plan is not None
    assert plan.active_rect_source == "explicit"
    assert plan.active_rect == GeometryRect(160, 0, 1600, 1080)
    assert len(warnings) == 1
    assert "Dolby Vision L5 active rect metadata" in warnings[0]
    assert "Reference" in warnings[0]
    assert "inconsistent" in warnings[0]
    assert "explicit active rect override" in warnings[0]


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_trusted_metadata_without_l5_candidate_falls_back_quietly(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=[
            OverlayDiagnosticMetadata(dolby_vision=OverlayDolbyVisionMetadata(rpu_present=True)),
            OverlayDiagnosticMetadata(max_cll=1000),
        ],
        diagnostic_metadata_trusted_for_geometry=True,
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1440,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req1, req2],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
        warnings=warnings,
    )

    ref_plan = requests[0].geometry_plan
    assert ref_plan is not None
    assert ref_plan.active_rect_source == "dimension-derived"
    assert ref_plan.active_rect == GeometryRect(240, 0, 1440, 1080)
    assert warnings == []


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_attaches_aligned_geometry_for_three_sources(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    source_infos = []
    for width in (1920, 1600, 1440):
        source_info = MagicMock()
        source_info.width = width
        source_info.height = 1080
        source_info.num_frames = 150
        source_info.is_hdr = False
        source_infos.append(source_info)
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, source_infos[0]),
        (MagicMock(name="enc_a_clip"), None, None, source_infos[1]),
        (MagicMock(name="enc_b_clip"), None, None, source_infos[2]),
    ]
    batch_requests = [
        ScreenshotBatchRequest(
            clip_path=Path(f"video-{index}.mkv"),
            label=label,
            source_frames=[10, 20],
            display_frames=[10, 20],
            selection_labels=[None, None],
            probe_width=width,
            probe_height=1080,
            probe_num_frames=100,
            probe_is_hdr=False,
        )
        for index, (label, width) in enumerate(
            (("Reference", 1920), ("Encode 1", 1600), ("Encode 2", 1440))
        )
    ]

    requests, label_to_range = expand_batch_render_requests(
        batch_requests,
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    assert label_to_range == {
        "Reference": range(0, 2),
        "Encode 1": range(2, 4),
        "Encode 2": range(4, 6),
    }
    assert len(requests) == 6
    plans = [request.geometry_plan for request in requests]
    assert plans[0] is plans[1]
    assert plans[2] is plans[3]
    assert plans[4] is plans[5]
    assert [plans[index].active_rect for index in (0, 2, 4) if plans[index] is not None] == [
        GeometryRect(240, 0, 1440, 1080),
        GeometryRect(80, 0, 1440, 1080),
        GeometryRect(0, 0, 1440, 1080),
    ]
    for request in requests:
        assert request.geometry_plan is not None
        assert request.geometry_plan.final_canvas_size == (1440, 1080)
        assert request.overlay is not None
        assert request.overlay.resolution == (1440, 1080)


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_warns_and_uses_native_when_aligned_dimensions_unknown(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    mock_prepare.return_value = (Path("video.mkv"), None, None, None)
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="Reference",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=None,
        probe_height=None,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
        warnings=warnings,
    )

    assert requests[0].geometry_plan is None
    assert requests[0].overlay is not None
    assert requests[0].overlay.origin is None
    assert requests[0].overlay.resolution == (0, 0)
    assert warnings == [
        "Screenshot geometry alignment skipped: source dimensions were unavailable "
        "for Reference; using native screenshot geometry for this batch."
    ]
