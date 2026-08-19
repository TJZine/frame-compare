from pathlib import Path

import pytest

from frame_compare.config.schema import OverlayMode, ReportConfig
from frame_compare.services.report.payload import (
    REPORT_VERSION,
    ClipInfo,
    ReportData,
    ReportImageInfo,
    ReportRenderingInfo,
    build_report_payload,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)


def _geometry() -> RenderedGeometryFacts:
    return RenderedGeometryFacts(
        source_size=(1920, 1080),
        active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
        cropped_size=(1920, 1080),
        scaled_size=(1920, 1080),
        final_canvas_size=(1920, 1080),
        is_noop=True,
    )


def _report_data(image: Path) -> ReportData:
    geometry = _geometry()
    return ReportData(
        clips=[
            ClipInfo(
                name="reference.mkv",
                label="Reference",
                path=Path("reference.mkv"),
                frame_count=100,
                resolution=(1920, 1080),
                fps=24.0,
                size_bytes=1024,
                signal=SourceSignalFacts(is_hdr=False),
                presentation_state=PresentationState.SDR,
                tonemap_settings=None,
                active_picture=geometry.active_picture,
                images=[
                    ReportImageInfo(
                        path=image,
                        source_frame=9,
                        facts=RenderedFrameFacts(source_frame=9, picture_type="B"),
                    )
                ],
            )
        ],
        frames=[7],
        rendering=ReportRenderingInfo(
            overlay_mode=OverlayMode.DIAGNOSTIC,
            include_frame_number=True,
            tonemap_settings=None,
            geometry_by_label={"Reference": geometry},
        ),
    )


def test_report_payload_v11_preserves_comparison_and_source_frame_domains(
    tmp_path: Path,
) -> None:
    image = tmp_path / "reference_7.png"
    image.write_bytes(b"png")

    payload = build_report_payload(_report_data(image), ReportConfig(), report_dir=tmp_path)

    assert payload["version"] == REPORT_VERSION == "1.1"
    assert payload["frames"][0]["number"] == 7
    assert payload["frames"][0]["detail"] == "Selected comparison frame"
    assert payload["frames"][0]["images"][0]["source_frame"] == 9
    assert payload["frames"][0]["images"][0]["picture_type"] == "B"
    assert payload["frames"][0]["images"][0]["dolby_vision_rpu"] is None
    assert payload["rendering"]["overlay_mode"] == "diagnostic"


def test_report_input_rejects_image_fact_frame_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not match"):
        ReportImageInfo(
            path=tmp_path / "frame.png",
            source_frame=9,
            facts=RenderedFrameFacts(source_frame=8),
        )
