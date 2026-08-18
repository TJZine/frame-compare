"""Tests for the v1.1 report generation service."""

from __future__ import annotations

import base64
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from frame_compare.config.schema import OverlayMode, ReportConfig, ViewerMode
from frame_compare.services.errors import ReportError
from frame_compare.services.report.category_display import (
    humanize_category,
    label_repeats_category,
    normalized_display_token,
)
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    ClipInfo,
    FrameDetail,
    ReportData,
    ReportImageInfo,
    ReportPayload,
    ReportRenderingInfo,
    build_report_payload,
    image_src_for_report,
)
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    ExactFrameDolbyVisionFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.vs.types import TonemapSettings


def _geometry() -> RenderedGeometryFacts:
    active = ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True)
    return RenderedGeometryFacts(
        source_size=(1920, 1080),
        active_picture=active,
        cropped_size=(1920, 1080),
        scaled_size=(1920, 1080),
        final_canvas_size=(1920, 1080),
        is_noop=True,
    )


def _clip(
    tmp_path: Path,
    name: str,
    *,
    image_count: int = 2,
    hdr: bool = False,
    tonemapped: bool = False,
    dolby_vision: bool = False,
) -> ClipInfo:
    images: list[ReportImageInfo] = []
    active = ActivePictureFacts(0, 276, 1920, 804, "dolby_vision_l5", False)
    for index in range(image_count):
        path = tmp_path / "screens" / name / f"{index}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake_png_data")
        source_frame = 10 + index
        dovi = (
            ExactFrameDolbyVisionFacts(source_frame, l1_maximum_nits=1000.0)
            if dolby_vision
            else None
        )
        images.append(
            ReportImageInfo(
                path=path,
                source_frame=source_frame,
                facts=RenderedFrameFacts(source_frame, "B", dovi),
            )
        )
    return ClipInfo(
        name=name,
        path=tmp_path / f"{name}.mkv",
        frame_count=100,
        resolution=(1920, 1080),
        fps=24000 / 1001,
        size_bytes=17 * 1024**3,
        signal=SourceSignalFacts(
            is_hdr=hdr,
            primaries=9 if hdr else 1,
            transfer=16 if hdr else 1,
            matrix=9 if hdr else 1,
            color_range="limited",
            dolby_vision_rpu=dolby_vision,
        ),
        presentation_state=(
            PresentationState.HDR_TONEMAPPED
            if tonemapped
            else PresentationState.HDR_TONEMAP_OFF
            if hdr
            else PresentationState.SDR
        ),
        tonemap_settings=TonemapSettings() if tonemapped else None,
        active_picture=active if dolby_vision else _geometry().active_picture,
        images=images,
        label=name.upper(),
        source_identity=f"source_{name}",
    )


@pytest.fixture
def report_data(tmp_path: Path) -> ReportData:
    clips = [
        _clip(tmp_path, "clip1"),
        _clip(tmp_path, "clip2", hdr=True, tonemapped=True, dolby_vision=True),
    ]
    geometry = _geometry()
    return ReportData(
        clips=clips,
        frames=[10, 20],
        rendering=ReportRenderingInfo(
            overlay_mode=OverlayMode.DIAGNOSTIC,
            include_frame_number=True,
            tonemap_settings=TonemapSettings(),
            geometry_by_label={clip.label or clip.name: geometry for clip in clips},
        ),
        metadata=TmdbMetadata(
            tmdb_id=123,
            title="Test Movie",
            original_title="Test Movie Orig",
            year=2023,
            media_type="movie",
        ),
        slowpics_url="https://slow.pics/c/12345",
    )


def _json_payload_from_report(path: Path) -> ReportPayload:
    content = path.read_text(encoding="utf-8")
    marker = '<script type="application/json" id="report-data">'
    start = content.find(marker) + len(marker)
    end = content.find("</script>", start)
    return json.loads(content[start:end])


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("quantile_bright", "Bright"),
        ("scene-cut", "Scene Cuts"),
        ("selected", "Selected"),
        (None, None),
    ],
)
def test_category_display_helpers(category: str | None, expected: str | None) -> None:
    assert humanize_category(category) == expected


def test_category_tokens_and_duplicate_detection() -> None:
    assert normalized_display_token("  User---Override  ") == "user override"
    assert normalized_display_token("") is None
    assert label_repeats_category("Bright", "quantile_bright")
    assert not label_repeats_category("Frame 42", "quantile_bright")


def test_generate_report_validates_screenshot_boundaries(
    report_data: ReportData, tmp_path: Path
) -> None:
    report_data.clips[0].images[0].path.unlink()
    with pytest.raises(ReportError, match="screenshot not found"):
        generate_report(report_data, ReportConfig(), output_path=tmp_path / "report.html")
    report_data.clips[0].images.clear()
    with pytest.raises(ReportError, match="screenshot count mismatch"):
        build_report_payload(report_data, ReportConfig(), report_dir=tmp_path)


def test_generate_report_encode_failure_raises(
    report_data: ReportData, mocker: MockerFixture, tmp_path: Path
) -> None:
    mocker.patch.object(Path, "read_bytes", side_effect=OSError("Disk error"))
    with pytest.raises(ReportError, match="failed to encode image"):
        generate_report(
            report_data, ReportConfig(embed_images=True), output_path=tmp_path / "report.html"
        )


def test_generate_report_embed_images_and_relative_paths(
    report_data: ReportData, tmp_path: Path
) -> None:
    embedded = generate_report(
        report_data, ReportConfig(embed_images=True), output_path=tmp_path / "report.html"
    )
    content = embedded.read_text(encoding="utf-8")
    assert "data:image/png;base64," in content
    assert base64.b64encode(b"fake_png_data").decode("ascii") in content
    relative = generate_report(
        report_data,
        ReportConfig(embed_images=False),
        output_path=tmp_path / "screens" / "report.html",
    )
    assert 'src="clip1/0.png"' in relative.read_text(encoding="utf-8")


def test_report_payload_v11_raw_values_and_comparison_semantics(
    report_data: ReportData, tmp_path: Path
) -> None:
    payload = build_report_payload(report_data, ReportConfig(), report_dir=tmp_path)
    assert payload["version"] == "1.1"
    assert payload["clips"][0]["size_bytes"] == 17 * 1024**3
    assert payload["clips"][1]["signal"]["primaries"] == 9
    assert payload["clips"][1]["signal"]["dolby_vision_rpu"] is True
    assert payload["clips"][1]["presentation"]["state"] == "hdr_tonemapped"
    assert payload["frames"][0]["number"] == 10
    assert payload["frames"][0]["detail"] == "Selected comparison frame"
    assert payload["frames"][0]["images"][0]["source_frame"] == 10
    assert payload["frames"][0]["images"][0]["picture_type"] == "B"
    assert payload["frames"][0]["images"][1]["dolby_vision"]["source_frame"] == 10
    assert payload["rendering"]["tonemap"]["applied"] is True


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (ViewerMode.SLIDER, "slider"),
        (ViewerMode.OVERLAY, "overlay"),
        (ViewerMode.DIFF, "diff"),
        (ViewerMode.BLINK, "blink"),
    ],
)
def test_payload_propagates_default_mode(
    report_data: ReportData, tmp_path: Path, mode: ViewerMode, expected: str
) -> None:
    payload = build_report_payload(
        report_data, ReportConfig(default_mode=mode), report_dir=tmp_path
    )
    assert payload["default_mode"] == expected


def test_payload_rejects_frame_detail_cardinality(report_data: ReportData, tmp_path: Path) -> None:
    report_data.frame_details.append(FrameDetail(label="only one"))
    with pytest.raises(ReportError, match="frame detail count mismatch"):
        build_report_payload(
            report_data,
            ReportConfig(),
            report_dir=tmp_path,
        )


def test_report_id_identity_excludes_paths_and_timestamps(
    report_data: ReportData, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FirstClock:
        @classmethod
        def now(cls, tz: object) -> datetime:
            return datetime(2026, 5, 22, 12, 0, tzinfo=UTC)

    class SecondClock:
        @classmethod
        def now(cls, tz: object) -> datetime:
            return datetime(2026, 5, 23, 12, 0, tzinfo=UTC)

    monkeypatch.setattr("frame_compare.services.report.payload.datetime", FirstClock)
    first = build_report_payload(report_data, ReportConfig(), report_dir=tmp_path)
    moved = replace(
        report_data,
        clips=[
            replace(clip, path=tmp_path / "moved" / clip.path.name) for clip in report_data.clips
        ],
    )
    monkeypatch.setattr("frame_compare.services.report.payload.datetime", SecondClock)
    second = build_report_payload(moved, ReportConfig(), report_dir=tmp_path)
    assert first["generated_at"] != second["generated_at"]
    assert first["report_id"] == second["report_id"]
    assert str(tmp_path) not in first["report_id"]
    changed = replace(
        report_data,
        rendering=replace(report_data.rendering, tonemap_settings=TonemapSettings(target_nits=203)),
    )
    assert (
        build_report_payload(changed, ReportConfig(), report_dir=tmp_path)["report_id"]
        != first["report_id"]
    )


def test_image_src_for_report_rejects_escape_and_accepts_contained_files(tmp_path: Path) -> None:
    report_dir = tmp_path / "run"
    screenshot = report_dir / "screens" / "safe.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"fake_png_data")
    assert (
        image_src_for_report(screenshot, report_dir=report_dir, embed_images=False)
        == "screens/safe.png"
    )
    assert image_src_for_report(screenshot, report_dir=report_dir, embed_images=True).startswith(
        "data:image/png"
    )
    with pytest.raises(ReportError, match="outside the report directory"):
        image_src_for_report(tmp_path / "outside.png", report_dir=report_dir, embed_images=False)


def test_report_data_and_clip_are_frozen(report_data: ReportData) -> None:
    with pytest.raises(FrozenInstanceError):
        report_data.frames = []  # type: ignore
    with pytest.raises(FrozenInstanceError):
        report_data.clips[0].name = "new"  # type: ignore


def test_generate_report_json_contains_v11_rendering(
    report_data: ReportData, tmp_path: Path
) -> None:
    output = generate_report(report_data, ReportConfig(), output_path=tmp_path / "report.html")
    payload = _json_payload_from_report(output)
    assert payload["version"] == "1.1"
    assert payload["rendering"]["overlay_mode"] == "diagnostic"
    assert payload["frames"][0]["detail"] == "Selected comparison frame"
