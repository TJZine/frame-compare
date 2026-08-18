"""Direct behavior tests for the report entry module."""

from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.config.schema import OverlayMode, ReportConfig
from frame_compare.services.errors import ReportError
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    ClipInfo,
    ReportData,
    ReportImageInfo,
    ReportRenderingInfo,
)
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)


@pytest.fixture
def report_data(tmp_path: Path) -> ReportData:
    geometry = RenderedGeometryFacts(
        source_size=(1920, 1080),
        active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
        cropped_size=(1920, 1080),
        scaled_size=(1920, 1080),
        final_canvas_size=(1920, 1080),
        is_noop=True,
    )
    clips: list[ClipInfo] = []
    for name, label in (("reference", "REF"), ("encode", "ENC")):
        images: list[ReportImageInfo] = []
        for frame_number in (10, 20):
            path = tmp_path / "screenshots" / name / f"{frame_number}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"image-bytes")
            images.append(
                ReportImageInfo(path, frame_number, RenderedFrameFacts(frame_number, "I"))
            )
        clips.append(
            ClipInfo(
                name=name,
                path=tmp_path / f"{name}.mkv",
                frame_count=100,
                resolution=(1920, 1080),
                fps=24.0,
                size_bytes=1024**3,
                signal=SourceSignalFacts(is_hdr=False),
                presentation_state=PresentationState.SDR,
                tonemap_settings=None,
                active_picture=geometry.active_picture,
                images=images,
                label=label,
            )
        )

    return ReportData(
        clips=clips,
        frames=[10, 20],
        rendering=ReportRenderingInfo(
            overlay_mode=OverlayMode.STANDARD,
            include_frame_number=True,
            tonemap_settings=None,
            geometry_by_label={clip.label or clip.name: geometry for clip in clips},
        ),
        metadata=TmdbMetadata(
            tmdb_id=42,
            title="Entry Contract",
            original_title="Entry Contract",
            year=2026,
            media_type="movie",
        ),
        slowpics_url="https://slow.pics/c/entry",
    )


def test_generate_report_persists_to_explicit_output_path_over_config_dir(
    report_data: ReportData, tmp_path: Path
) -> None:
    configured_dir = tmp_path / "configured"
    explicit_path = tmp_path / "comparison.html"

    report_path = generate_report(
        report_data,
        ReportConfig(embed_images=False),
        output_path=explicit_path,
    )
    html = report_path.read_text(encoding="utf-8")

    assert report_path == explicit_path
    assert explicit_path.exists()
    assert not (configured_dir / "report.html").exists()
    assert "Entry Contract" in html
    assert '"frame_count": 2' in html


def test_generate_report_requires_explicit_output_path(report_data: ReportData) -> None:
    with pytest.raises(ReportError, match="report output path is required"):
        generate_report(report_data, ReportConfig())


def _clear_clips(data: ReportData) -> ReportData:
    data.clips.clear()
    return data


def _remove_one_clip(data: ReportData) -> ReportData:
    data.clips.pop()
    return data


def _clear_frames(data: ReportData) -> ReportData:
    data.frames.clear()
    return data


def _clear_all_images(data: ReportData) -> ReportData:
    for clip in data.clips:
        clip.images.clear()
    return data


def _clear_encode_images(data: ReportData) -> ReportData:
    data.clips[1].images.clear()
    return data


@pytest.mark.parametrize(
    ("data_builder", "message"),
    [
        (_clear_clips, "no clips provided"),
        (_remove_one_clip, "at least 2 clips required for comparison"),
        (_clear_frames, "no frames provided"),
        (_clear_all_images, "no screenshots provided"),
        (_clear_encode_images, "no screenshots for clip: encode"),
    ],
)
def test_generate_report_rejects_invalid_report_data_before_writing(
    report_data: ReportData,
    tmp_path: Path,
    data_builder,
    message: str,
) -> None:
    with pytest.raises(ReportError, match=message):
        generate_report(
            data_builder(report_data),
            ReportConfig(),
            output_path=tmp_path / "report.html",
        )

    assert not (tmp_path / "report.html").exists()


def test_generate_report_rejects_mismatched_screenshot_counts(report_data: ReportData) -> None:
    report_data.clips[0].images.pop()

    with pytest.raises(
        ReportError,
        match="screenshot count mismatch for reference: expected 2, got 1",
    ):
        generate_report(
            report_data,
            ReportConfig(),
            output_path=report_data.clips[0].path.parent / "report.html",
        )


def test_generate_report_wraps_persistence_failures_as_report_error(
    report_data: ReportData, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_write(_path: Path, _content: str, *, encoding: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("frame_compare.services.report.entry.write_text_atomic", fail_write)

    with pytest.raises(ReportError, match="failed to write report: disk full"):
        generate_report(
            report_data,
            ReportConfig(),
            output_path=tmp_path / "report.html",
        )

    assert not (tmp_path / "report.html").exists()
