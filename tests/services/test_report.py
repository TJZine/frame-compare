"Tests for the Report Generation Service."

import base64
import json
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from frame_compare.config.schema import ReportConfig, ViewerMode
from frame_compare.services.errors import ReportError
from frame_compare.services.report.display import (
    SourceFrameSelectionDetail,
    frame_detail_for_source_frame,
)
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    ClipInfo,
    FrameDetail,
    ReportData,
    ReportPayload,
    build_report_payload,
    clip_info_from_state,
    image_src_for_report,
)
from frame_compare.services.types import TmdbMetadata


@pytest.fixture
def mock_clips(tmp_path: Path) -> list[ClipInfo]:
    return [
        ClipInfo(
            name="clip1",
            path=tmp_path / "clip1.mkv",
            frame_count=100,
            resolution=(1920, 1080),
            fps=24.0,
            hdr=False,
            label="REF",
        ),
        ClipInfo(
            name="clip2",
            path=tmp_path / "clip2.mkv",
            frame_count=100,
            resolution=(1920, 1080),
            fps=24.0,
            hdr=False,
            label="ENC",
        ),
    ]


@pytest.fixture
def mock_screenshots(tmp_path: Path, mock_clips: list[ClipInfo]) -> dict[str, list[Path]]:
    screenshots = {}
    for clip in mock_clips:
        clip_screens = []
        for i in range(2):
            p = tmp_path / "screens" / clip.name / f"{i}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"fake_png_data")
            clip_screens.append(p)
        screenshots[clip.name] = clip_screens
    return screenshots


@pytest.fixture
def report_data(mock_clips: list[ClipInfo], mock_screenshots: dict[str, list[Path]]) -> ReportData:
    updated_clips = [replace(clip, screenshots=mock_screenshots[clip.name]) for clip in mock_clips]
    return ReportData(
        clips=updated_clips,
        frames=[10, 20],
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


def test_generate_report_creates_html_file(report_data: ReportData, tmp_path: Path) -> None:
    config = ReportConfig(output_dir=str(tmp_path / "out"))
    out_path = generate_report(report_data, config)
    assert out_path.exists()
    assert out_path.suffix == ".html"
    assert out_path.parent == tmp_path / "out"


def test_generate_report_custom_output_path(report_data: ReportData, tmp_path: Path) -> None:
    config = ReportConfig()
    custom_path = tmp_path / "custom" / "my_report.html"
    out_path = generate_report(report_data, config, output_path=custom_path)
    assert out_path == custom_path
    assert out_path.exists()


def test_generate_report_config_output_dir(report_data: ReportData, tmp_path: Path) -> None:
    config = ReportConfig(output_dir=str(tmp_path / "config_out"))
    out_path = generate_report(report_data, config)
    assert out_path.parent == tmp_path / "config_out"


def test_generate_report_default_output_path(report_data: ReportData, tmp_path: Path) -> None:
    config = ReportConfig(output_dir=None)
    # Default is first clip's first screenshot's parent / report.html
    # In fixture: tmp_path / "screens" / "clip1" / "report.html"
    expected = report_data.clips[0].screenshots[0].parent / "report.html"
    out_path = generate_report(report_data, config)
    assert out_path == expected


def test_generate_report_no_clips_raises(report_data: ReportData) -> None:
    empty_data = ReportData([], [])
    with pytest.raises(ReportError, match="no clips provided"):
        generate_report(empty_data, ReportConfig())


def test_generate_report_single_clip_raises(
    report_data: ReportData, mock_clips: list[ClipInfo]
) -> None:
    single_data = ReportData([mock_clips[0]], [])
    with pytest.raises(ReportError, match="at least 2 clips required"):
        generate_report(single_data, ReportConfig())


def test_generate_report_empty_frames_raises(report_data: ReportData) -> None:
    data = ReportData(report_data.clips, [])
    with pytest.raises(ReportError, match="no frames provided"):
        generate_report(data, ReportConfig())


def test_generate_report_empty_screenshots_dict_raises(report_data: ReportData) -> None:
    clips_no_screenshots = [replace(clip, screenshots=[]) for clip in report_data.clips]
    data = ReportData(clips_no_screenshots, report_data.frames)
    with pytest.raises(ReportError, match="no screenshots provided"):
        generate_report(data, ReportConfig())


def test_generate_report_missing_clip_key_raises(report_data: ReportData) -> None:
    clips_missing_screenshots = [
        report_data.clips[0],
        replace(report_data.clips[1], screenshots=[]),
    ]
    data = ReportData(clips_missing_screenshots, report_data.frames)
    with pytest.raises(ReportError, match="no screenshots for clip: clip2"):
        generate_report(data, ReportConfig())


def test_generate_report_empty_clip_list_raises(report_data: ReportData) -> None:
    clips = [
        replace(report_data.clips[0], screenshots=[]),
        report_data.clips[1],
    ]
    data = ReportData(clips, report_data.frames)
    with pytest.raises(ReportError, match="no screenshots for clip: clip1"):
        generate_report(data, ReportConfig())


def test_generate_report_length_mismatch_raises(report_data: ReportData) -> None:
    clips = [
        replace(report_data.clips[0], screenshots=report_data.clips[0].screenshots[:-1]),
        report_data.clips[1],
    ]
    data = ReportData(clips, report_data.frames)
    with pytest.raises(ReportError, match="screenshot count mismatch for clip1"):
        generate_report(data, ReportConfig())


def test_generate_report_screenshot_not_found_raises(
    report_data: ReportData, tmp_path: Path
) -> None:
    # Delete a file
    p = report_data.clips[0].screenshots[0]
    p.unlink()
    with pytest.raises(ReportError, match="screenshot not found"):
        generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))


def test_generate_report_encode_failure_raises(
    report_data: ReportData, mocker: MockerFixture, tmp_path: Path
) -> None:
    mocker.patch.object(Path, "read_bytes", side_effect=OSError("Disk error"))
    with pytest.raises(ReportError, match="failed to encode image"):
        generate_report(report_data, ReportConfig(embed_images=True, output_dir=str(tmp_path)))


def test_generate_report_write_failure_raises(
    report_data: ReportData, mocker: MockerFixture, tmp_path: Path
) -> None:
    mocker.patch(
        "frame_compare.services.report.entry.write_text_atomic",
        side_effect=OSError("Disk full"),
    )
    with pytest.raises(ReportError, match="failed to write report"):
        generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))


def test_generate_report_keeps_existing_output_when_atomic_replace_fails(
    report_data: ReportData, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report_path = tmp_path / "report.html"
    report_path.write_text("old report", encoding="utf-8")

    def _boom(_src: str, _dst: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.replace", _boom)

    with pytest.raises(ReportError, match="failed to write report"):
        generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))

    assert report_path.read_text(encoding="utf-8") == "old report"
    assert list(tmp_path.glob(".report.html.*")) == []


def test_generate_report_preserves_existing_report_permissions(
    report_data: ReportData, tmp_path: Path
) -> None:
    report_path = tmp_path / "report.html"
    report_path.write_text("old report", encoding="utf-8")
    report_path.chmod(0o640)
    expected_mode = report_path.stat().st_mode & 0o777

    generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))

    assert (report_path.stat().st_mode & 0o777) == expected_mode


def test_generate_report_embed_images_base64(report_data: ReportData, tmp_path: Path) -> None:
    config = ReportConfig(embed_images=True, output_dir=str(tmp_path))
    out_path = generate_report(report_data, config)
    content = out_path.read_text(encoding="utf-8")
    assert "data:image/png;base64," in content
    # Our fake data is b"fake_png_data"
    expected_b64 = base64.b64encode(b"fake_png_data").decode("ascii")
    assert expected_b64 in content


def test_generate_report_relative_paths(report_data: ReportData, tmp_path: Path) -> None:
    # Set output dir near screenshots to ensure relative paths work
    output_dir = tmp_path / "screens"
    config = ReportConfig(embed_images=False, output_dir=str(output_dir))
    out_path = generate_report(report_data, config)
    content = out_path.read_text(encoding="utf-8")

    # Clip1 is at tmp_path/screens/clip1/0.png
    # Report is at tmp_path/screens/report.html
    # Rel path should be clip1/0.png
    assert 'src="clip1/0.png"' in content or 'src="clip1\\0.png"' in content
    assert "data:image/png;base64," not in content


def test_generate_report_includes_metadata(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")
    assert "Test Movie" in content


def test_generate_report_includes_slowpics_url(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")
    assert "https://slow.pics/c/12345" in content


def test_generate_report_without_slowpics_url_omits_external_link(
    report_data: ReportData, tmp_path: Path
) -> None:
    data_without_upload = ReportData(
        clips=report_data.clips,
        frames=report_data.frames,
        metadata=report_data.metadata,
        slowpics_url=None,
    )

    out_path = generate_report(data_without_upload, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")

    assert "View on slow.pics" not in content
    assert 'class="rv-link"' not in content
    assert '"slowpics_url": null' in content


def test_generate_report_filmstrip_included(report_data: ReportData, tmp_path: Path) -> None:
    config = ReportConfig(include_filmstrip=True, output_dir=str(tmp_path))
    out_path = generate_report(report_data, config)
    content = out_path.read_text(encoding="utf-8")
    assert 'class="rv-filmstrip"' in content


def test_generate_report_escapes_dynamic_html_and_hardens_json_script_tag(tmp_path: Path) -> None:
    clips = []
    for name, label in [
        ("clip1", "<b>REF</b>"),
        ("clip2", 'ENC"></option><script>alert(2)</script>'),
    ]:
        p = tmp_path / "screens" / name / "0.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fake_png_data")
        clips.append(
            ClipInfo(
                name=name,
                path=tmp_path / f"{name}.mkv",
                frame_count=100,
                resolution=(1920, 1080),
                fps=24.0,
                hdr=False,
                label=label,
                screenshots=[p],
            )
        )

    title = "</script><script>alert(1)</script>"
    report_data = ReportData(
        clips=clips,
        frames=[10],
        metadata=TmdbMetadata(
            tmdb_id=1,
            title=title,
            original_title="x",
            year=2023,
            media_type="movie",
        ),
        slowpics_url="https://slow.pics/c/12345",
    )

    out_path = generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")

    # Title and labels should be escaped in HTML.
    assert "</script><script>alert(1)</script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
    assert "&lt;b&gt;REF&lt;/b&gt;" in content
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in content

    # Embedded JSON should not contain raw '<' / '</script>' sequences.
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert(1)\\u003c/script\\u003e" in content


def test_generate_report_filmstrip_excluded(report_data: ReportData, tmp_path: Path) -> None:
    config = ReportConfig(include_filmstrip=False, output_dir=str(tmp_path))
    out_path = generate_report(report_data, config)
    content = out_path.read_text(encoding="utf-8")
    assert 'class="rv-filmstrip rv-filmstrip--hidden"' in content
    assert 'aria-hidden="true"' in content
    assert 'class="rv-filmstrip-item"' not in content


def test_image_src_for_report_uses_file_uri_for_cross_drive_fallback(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    screenshot_path = tmp_path / "shot.png"
    screenshot_path.write_bytes(b"fake_png_data")
    mocker.patch("frame_compare.services.report.payload.os.path.relpath", side_effect=ValueError)

    src = image_src_for_report(
        screenshot_path,
        report_dir=tmp_path / "report",
        embed_images=False,
    )

    assert src == screenshot_path.resolve().as_uri()


def test_generate_report_mode_slider(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(
        report_data,
        ReportConfig(default_mode=ViewerMode.SLIDER, output_dir=str(tmp_path)),
    )
    content = out_path.read_text(encoding="utf-8")
    assert "clip-path" in content
    assert '"default_mode": "slider"' in content


def test_generate_report_mode_overlay(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(
        report_data,
        ReportConfig(default_mode=ViewerMode.OVERLAY, output_dir=str(tmp_path)),
    )
    content = out_path.read_text(encoding="utf-8")
    assert '"default_mode": "overlay"' in content


def test_generate_report_mode_diff(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(
        report_data,
        ReportConfig(default_mode=ViewerMode.DIFF, output_dir=str(tmp_path)),
    )
    content = out_path.read_text(encoding="utf-8")
    assert "mix-blend-mode: difference" in content
    assert '"default_mode": "diff"' in content


def test_generate_report_mode_blink(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(
        report_data,
        ReportConfig(default_mode=ViewerMode.BLINK, output_dir=str(tmp_path)),
    )
    content = out_path.read_text(encoding="utf-8")
    assert "setInterval" in content
    assert '"default_mode": "blink"' in content


def test_generate_report_creates_parent_dirs(report_data: ReportData, tmp_path: Path) -> None:
    deep_path = tmp_path / "deep" / "nested" / "report.html"
    generate_report(report_data, ReportConfig(), output_path=deep_path)
    assert deep_path.exists()


def test_generate_report_dark_theme(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")
    assert "--bg-primary: #0f1115" in content


def test_generate_report_keyboard_shortcuts(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")
    assert "ArrowLeft" in content
    assert "ArrowRight" in content


def test_generate_report_accessibility(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")
    assert "aria-label=" in content


def test_generate_report_json_payload_structure(report_data: ReportData, tmp_path: Path) -> None:
    out_path = generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))

    data = _json_payload_from_report(out_path)
    assert data["version"] == "1.0"
    assert isinstance(data["report_id"], str)
    assert data["report_id"].startswith("report_")
    assert len(data["report_id"]) == len("report_") + 32
    assert "generated_at" in data
    assert data["default_selection"] == {"left_clip_index": 0, "right_clip_index": 1}
    assert len(data["clips"]) == 2
    assert len(data["frames"]) == 2
    clips = data["clips"]
    frames = data["frames"]
    assert isinstance(clips, list)
    assert isinstance(frames, list)
    assert clips[0]["name"] == "clip1"
    assert clips[0]["frame_count"] == 100
    assert frames[0]["number"] == 10
    assert frames[0]["label"] == "Frame 10"
    assert frames[0]["detail"] == "Source frame 10"
    assert frames[0]["category"] == "selected"
    assert len(frames[0]["images"]) == 2


def test_build_report_payload_accepts_frame_display_metadata(
    report_data: ReportData, tmp_path: Path
) -> None:
    data = replace(
        report_data,
        frame_details=[
            FrameDetail(label="Opening comparison", detail="Scene cut", category="chapter"),
            FrameDetail(),
        ],
    )

    payload = build_report_payload(
        data, ReportConfig(output_dir=str(tmp_path)), report_dir=tmp_path
    )

    assert payload["frames"][0]["label"] == "Opening comparison"
    assert payload["frames"][0]["detail"] == "Scene cut"
    assert payload["frames"][0]["category"] == "chapter"
    assert payload["frames"][1]["label"] == "Frame 20"
    assert payload["frames"][1]["detail"] == "Source frame 20"
    assert payload["frames"][1]["category"] == "selected"


def test_build_report_payload_rejects_mismatched_frame_display_metadata(
    report_data: ReportData, tmp_path: Path
) -> None:
    data = replace(report_data, frame_details=[FrameDetail(label="only one")])

    with pytest.raises(ReportError, match="frame detail count mismatch"):
        build_report_payload(data, ReportConfig(output_dir=str(tmp_path)), report_dir=tmp_path)


def test_frame_detail_for_source_frame_uses_explicit_selection_detail() -> None:
    detail = frame_detail_for_source_frame(
        source_frame=42,
        selection_detail=SourceFrameSelectionDetail(
            label="Opening comparison",
            timecode="00:00:01.750",
            notes="chapter",
        ),
        selection_label="Bright",
    )

    assert detail == FrameDetail(
        label="Opening comparison",
        detail="Source frame 42",
        category="chapter",
    )


def test_frame_detail_for_source_frame_uses_frame_number_label_when_detail_absent() -> None:
    detail = frame_detail_for_source_frame(
        source_frame=42,
        selection_detail=None,
        selection_label="Bright",
    )

    assert detail == FrameDetail(
        label="Frame 42",
        detail="Source frame 42",
        category="quantile_bright",
    )


def test_frame_detail_for_source_frame_uses_frame_number_label_when_detail_label_absent() -> None:
    detail = frame_detail_for_source_frame(
        source_frame=42,
        selection_detail=SourceFrameSelectionDetail(
            label=None,
            timecode="00:00:01.750",
            notes=None,
        ),
        selection_label="Bright",
    )

    assert detail == FrameDetail(
        label="Frame 42",
        detail="Source frame 42",
        category="quantile_bright",
    )


def test_frame_detail_for_source_frame_uses_frame_number_when_label_matches_category() -> None:
    detail = frame_detail_for_source_frame(
        source_frame=42,
        selection_detail=SourceFrameSelectionDetail(
            label="Motion",
            timecode="00:00:01.750",
            notes="motion",
        ),
        selection_label="Motion",
    )

    assert detail == FrameDetail(
        label="Frame 42",
        detail="Source frame 42",
        category="motion",
    )


@pytest.mark.parametrize(
    ("selection_label", "category"),
    [
        ("Dark", "quantile_dark"),
        ("Bright", "quantile_bright"),
        ("Motion", "motion"),
        ("Random", "random"),
    ],
)
def test_frame_detail_for_source_frame_maps_known_selection_labels(
    selection_label: str,
    category: str,
) -> None:
    detail = frame_detail_for_source_frame(
        source_frame=7,
        selection_detail=None,
        selection_label=selection_label,
    )

    assert detail.category == category


@pytest.mark.parametrize("selection_label", ["Other", None])
def test_frame_detail_for_source_frame_leaves_unknown_selection_label_uncategorized(
    selection_label: str | None,
) -> None:
    detail = frame_detail_for_source_frame(
        source_frame=7,
        selection_detail=None,
        selection_label=selection_label,
    )

    assert detail.category is None


def test_report_id_ignores_generated_at_source_paths_and_image_sources(
    report_data: ReportData,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FirstClock:
        @classmethod
        def now(cls, tz: object) -> datetime:
            return datetime(2026, 5, 22, 12, 0, tzinfo=UTC)

    class SecondClock:
        @classmethod
        def now(cls, tz: object) -> datetime:
            return datetime(2026, 5, 23, 12, 0, tzinfo=UTC)

    clips_with_source_identities = [
        replace(clip, source_identity=f"source_identity_{clip.name}") for clip in report_data.clips
    ]
    stable_source_data = replace(report_data, clips=clips_with_source_identities)

    config = ReportConfig(output_dir=str(tmp_path), embed_images=False)
    monkeypatch.setattr("frame_compare.services.report.payload.datetime", FirstClock)
    first_payload = build_report_payload(
        stable_source_data, config, report_dir=tmp_path / "report-a"
    )

    clips_with_other_source_paths = [
        replace(clip, path=tmp_path / "different-root" / f"{clip.name}.mkv")
        for clip in stable_source_data.clips
    ]
    same_report_local_data = replace(stable_source_data, clips=clips_with_other_source_paths)

    monkeypatch.setattr("frame_compare.services.report.payload.datetime", SecondClock)
    second_payload = build_report_payload(
        same_report_local_data,
        config,
        report_dir=tmp_path / "different" / "report-b",
    )

    assert first_payload["generated_at"] != second_payload["generated_at"]
    first_src = first_payload["frames"][0]["images"][0]["src"]
    second_src = second_payload["frames"][0]["images"][0]["src"]
    assert first_src != second_src
    assert first_payload["report_id"] == second_payload["report_id"]

    embedded_payload = build_report_payload(
        same_report_local_data,
        ReportConfig(output_dir=str(tmp_path), embed_images=True),
        report_dir=tmp_path,
    )
    assert embedded_payload["frames"][0]["images"][0]["src"].startswith("data:image/png;base64,")
    assert embedded_payload["report_id"] == first_payload["report_id"]

    changed_source_identity_payload = build_report_payload(
        replace(
            same_report_local_data,
            clips=[
                same_report_local_data.clips[0],
                replace(same_report_local_data.clips[1], source_identity="source_identity_other"),
            ],
        ),
        config,
        report_dir=tmp_path,
    )
    assert changed_source_identity_payload["report_id"] != first_payload["report_id"]

    changed_frame_payload = build_report_payload(
        replace(same_report_local_data, frames=[11, 20]),
        config,
        report_dir=tmp_path,
    )
    assert changed_frame_payload["report_id"] != first_payload["report_id"]


@dataclass(frozen=True)
class _Fingerprint:
    path: Path
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class _Probe:
    fingerprint: _Fingerprint
    num_frames: int = 100
    width: int = 1920
    height: int = 1080
    is_hdr: bool = False


@dataclass(frozen=True)
class _ClipState:
    label: str
    path: Path
    probe: _Probe
    effective_fps: Fraction


def test_clip_info_from_state_sets_safe_source_identity(tmp_path: Path) -> None:
    source_path = tmp_path / "source-root" / "reference.mkv"
    state = _ClipState(
        label="Reference",
        path=source_path,
        probe=_Probe(
            fingerprint=_Fingerprint(
                path=source_path,
                size_bytes=123456,
                mtime_ns=987654321,
            )
        ),
        effective_fps=Fraction(24000, 1001),
    )

    clip = clip_info_from_state(state, screenshots=[])

    assert clip.source_identity is not None
    assert clip.source_identity.startswith("source_")
    assert len(clip.source_identity) == len("source_") + 32
    assert str(tmp_path) not in clip.source_identity
    assert "reference.mkv" not in clip.source_identity


def test_clip_info_frozen() -> None:
    c = ClipInfo("n", Path("p"), 100, (1920, 1080), 24.0, False)
    with pytest.raises(FrozenInstanceError):
        c.name = "new"  # type: ignore


def test_report_data_frozen(report_data: ReportData) -> None:
    with pytest.raises(FrozenInstanceError):
        report_data.frames = []  # type: ignore


def test_generate_report_slowpics_url_sanitization(report_data: ReportData, tmp_path: Path) -> None:
    # Test valid https scheme
    report_data_valid = ReportData(
        clips=report_data.clips,
        frames=report_data.frames,
        slowpics_url="https://slow.pics/c/123",
    )
    out_path = generate_report(report_data_valid, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")
    assert "https://slow.pics/c/123" in content
    assert "View on slow.pics" in content

    # Test invalid scheme (e.g., javascript or ftp)
    report_data_invalid = ReportData(
        clips=report_data.clips,
        frames=report_data.frames,
        slowpics_url="javascript:alert(1)",
    )
    out_path = generate_report(report_data_invalid, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")
    assert "View on slow.pics" not in content


def test_renderer_clip_options_rendering(report_data: ReportData, tmp_path: Path) -> None:
    # Verify that left and right clip options are rendered with correct values/labels
    # and selected index is respected
    out_path = generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))
    content = out_path.read_text(encoding="utf-8")
    # Left and right clip controls use the report payload's default selection.
    assert '<select id="left-select" aria-label="Left clip">' in content
    assert '<option value="0" selected>REF</option>' in content
    assert '<option value="1">ENC</option>' in content

    assert '<select id="right-select" aria-label="Right clip">' in content
    assert '<option value="1" selected>ENC</option>' in content

    assert '<select id="active-select" aria-label="Overlay clip">' in content
