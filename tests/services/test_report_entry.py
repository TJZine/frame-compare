"""Direct behavior tests for the report entry module."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from frame_compare.config.schema import ReportConfig
from frame_compare.services.errors import ReportError
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import ClipInfo, ReportData
from frame_compare.services.types import TmdbMetadata


@pytest.fixture
def report_data(tmp_path: Path) -> ReportData:
    clips = [
        ClipInfo(
            name="reference",
            path=tmp_path / "reference.mkv",
            frame_count=100,
            resolution=(1920, 1080),
            fps=24.0,
            hdr=False,
            label="REF",
        ),
        ClipInfo(
            name="encode",
            path=tmp_path / "encode.mkv",
            frame_count=100,
            resolution=(1920, 1080),
            fps=24.0,
            hdr=False,
            label="ENC",
        ),
    ]
    screenshots: dict[str, list[Path]] = {}
    for clip in clips:
        paths: list[Path] = []
        for frame_number in (10, 20):
            path = tmp_path / "screenshots" / clip.name / f"{frame_number}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"image-bytes")
            paths.append(path)
        screenshots[clip.name] = paths

    updated_clips = [replace(clip, screenshots=screenshots[clip.name]) for clip in clips]

    return ReportData(
        clips=updated_clips,
        frames=[10, 20],
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
    explicit_path = tmp_path / "explicit" / "nested" / "comparison.html"

    report_path = generate_report(
        report_data,
        ReportConfig(output_dir=str(configured_dir), embed_images=False),
        output_path=explicit_path,
    )
    html = report_path.read_text(encoding="utf-8")

    assert report_path == explicit_path
    assert explicit_path.exists()
    assert not (configured_dir / "report.html").exists()
    assert "Entry Contract" in html
    assert '"frame_count": 2' in html


def test_generate_report_uses_configured_report_path_when_no_explicit_path(
    report_data: ReportData, tmp_path: Path
) -> None:
    configured_dir = tmp_path / "configured"

    report_path = generate_report(report_data, ReportConfig(output_dir=str(configured_dir)))

    assert report_path == configured_dir / "report.html"
    assert report_path.exists()


def test_generate_report_falls_back_to_first_clip_screenshot_directory(
    report_data: ReportData,
) -> None:
    report_path = generate_report(report_data, ReportConfig(output_dir=None))

    assert report_path == report_data.clips[0].screenshots[0].parent / "report.html"
    assert report_path.exists()


@pytest.mark.parametrize(
    ("data_builder", "message"),
    [
        (
            lambda data: ReportData([], data.frames),
            "no clips provided",
        ),
        (
            lambda data: ReportData(
                data.clips[:1],
                data.frames,
            ),
            "at least 2 clips required for comparison",
        ),
        (
            lambda data: ReportData(data.clips, []),
            "no frames provided",
        ),
        (
            lambda data: ReportData(
                [replace(c, screenshots=[]) for c in data.clips],
                data.frames,
            ),
            "no screenshots provided",
        ),
        (
            lambda data: ReportData(
                [data.clips[0], replace(data.clips[1], screenshots=[])],
                data.frames,
            ),
            "no screenshots for clip: encode",
        ),
    ],
)
def test_generate_report_rejects_invalid_report_data_before_writing(
    report_data: ReportData,
    tmp_path: Path,
    data_builder,
    message: str,
) -> None:
    with pytest.raises(ReportError, match=message):
        generate_report(data_builder(report_data), ReportConfig(output_dir=str(tmp_path)))

    assert not (tmp_path / "report.html").exists()


def test_generate_report_rejects_mismatched_screenshot_counts(report_data: ReportData) -> None:
    clips = [
        replace(report_data.clips[0], screenshots=report_data.clips[0].screenshots[:1]),
        report_data.clips[1],
    ]
    mismatched_data = ReportData(
        clips=clips,
        frames=report_data.frames,
        metadata=report_data.metadata,
        slowpics_url=report_data.slowpics_url,
    )

    with pytest.raises(
        ReportError,
        match="screenshot count mismatch for reference: expected 2, got 1",
    ):
        generate_report(mismatched_data, ReportConfig())


def test_generate_report_wraps_persistence_failures_as_report_error(
    report_data: ReportData, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_write(_path: Path, _content: str, *, encoding: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("frame_compare.services.report.entry.write_text_atomic", fail_write)

    with pytest.raises(ReportError, match="failed to write report: disk full"):
        generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))

    assert not (tmp_path / "report.html").exists()
