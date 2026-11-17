from dataclasses import replace
from pathlib import Path

import pytest

from frame_compare.config.schema import OverlayMode, ReportConfig
from frame_compare.services.metadata_parsing import parse_filename_with_release_identity
from frame_compare.services.report.payload import (
    REPORT_VERSION,
    ClipInfo,
    ReportClipDisplayInfo,
    ReportData,
    ReportImageInfo,
    ReportRenderingInfo,
    build_report_payload,
)
from frame_compare.services.types import TmdbMetadata
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
                tonemap=None,
                active_picture=geometry.active_picture,
                images=[
                    ReportImageInfo(
                        path=image,
                        source_frame=9,
                        facts=RenderedFrameFacts(source_frame=9, picture_type="B"),
                    )
                ],
                display=ReportClipDisplayInfo(
                    primary="Reference Primary",
                    release="Reference Release",
                    control="Reference Control",
                    micro="Reference Micro",
                    filename="reference.mkv",
                ),
            )
        ],
        frames=[7],
        rendering=ReportRenderingInfo(
            overlay_mode=OverlayMode.DIAGNOSTIC,
            include_frame_number=True,
            geometry_by_label={"Reference": geometry},
        ),
    )


def test_report_payload_v14_preserves_comparison_and_source_frame_domains(
    tmp_path: Path,
) -> None:
    image = tmp_path / "reference_7.png"
    image.write_bytes(b"png")

    payload = build_report_payload(_report_data(image), ReportConfig(), report_dir=tmp_path)

    assert payload["version"] == REPORT_VERSION == "1.4"
    assert payload["clips"][0]["display"] == {
        "primary": "Reference Primary",
        "release": "Reference Release",
        "control": "Reference Control",
        "micro": "Reference Micro",
        "filename": "reference.mkv",
    }
    assert payload["frames"][0]["number"] == 7
    assert payload["frames"][0]["detail"] == "Selected comparison frame"
    assert payload["frames"][0]["images"][0]["source_frame"] == 9
    assert payload["frames"][0]["images"][0]["picture_type"] == "B"
    assert payload["frames"][0]["images"][0]["dolby_vision_rpu"] is None
    assert payload["rendering"]["overlay_mode"] == "diagnostic"


_EBP = "Black.Sails.S01E08.1080p.Bluray.DD5.1.x264-EbP.mkv"
_GNOME = "Black.Sails.S01E08.VIII.1080p.AMZN.WEB-DL.DDP.5.1.H.264-GNOME.mkv"
_DUB = "Constructed.DemonSlayer-Kitsune.english-dub-only.mkv"


@pytest.mark.parametrize(
    ("filenames", "tmdb_title", "expected"),
    [
        ([_EBP, _GNOME], "Les Voiles Noires", "Les Voiles Noires S01E08"),
        ([_EBP, _GNOME], None, "Black Sails S01E08"),
        ([_EBP, _DUB], None, "EbP vs english-dub-only"),
        ([_EBP, _DUB, _GNOME], None, "EbP vs english-dub-only +1 more"),
    ],
    ids=["tmdb-with-episode", "common-content", "mixed-content", "mixed-content-with-more"],
)
def test_report_payload_title(
    tmp_path: Path, filenames: list[str], tmdb_title: str | None, expected: str
) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"png")
    base = _report_data(image)
    clips = [
        replace(
            base.clips[0],
            name=Path(filename).stem,
            path=Path(filename),
            label=filename,
            release_identity=parse_filename_with_release_identity(filename)[1],
            display=replace(base.clips[0].display, filename=filename),
        )
        for filename in filenames
    ]
    data = replace(
        base,
        clips=clips,
        rendering=replace(
            base.rendering, geometry_by_label={filename: _geometry() for filename in filenames}
        ),
        metadata=(
            TmdbMetadata(123, tmdb_title, "Black Sails", 2014, "tv")
            if tmdb_title is not None
            else None
        ),
    )

    payload = build_report_payload(data, ReportConfig(), report_dir=tmp_path)

    assert payload["title"] == expected
    assert [clip["display"]["filename"] for clip in payload["clips"]] == filenames


def test_report_input_rejects_image_fact_frame_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not match"):
        ReportImageInfo(
            path=tmp_path / "frame.png",
            source_frame=9,
            facts=RenderedFrameFacts(source_frame=8),
        )
