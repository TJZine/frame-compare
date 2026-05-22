"Tests for the Report Generation Service."

import base64
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from frame_compare.config.schema import ReportConfig, ViewerMode
from frame_compare.errors import ReportError
from frame_compare.services import report as report_module
from frame_compare.services.report import ClipInfo, ReportData, generate_report
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
    return ReportData(
        clips=mock_clips,
        frames=[10, 20],
        screenshots=mock_screenshots,
        metadata=TmdbMetadata(
            tmdb_id=123,
            title="Test Movie",
            original_title="Test Movie Orig",
            year=2023,
            media_type="movie",
        ),
        slowpics_url="https://slow.pics/c/12345",
    )


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
    expected = report_data.screenshots["clip1"][0].parent / "report.html"
    out_path = generate_report(report_data, config)
    assert out_path == expected


def test_generate_report_no_clips_raises(report_data: ReportData) -> None:
    empty_data = ReportData([], [], {})
    with pytest.raises(ReportError, match="no clips provided"):
        generate_report(empty_data, ReportConfig())


def test_generate_report_single_clip_raises(
    report_data: ReportData, mock_clips: list[ClipInfo]
) -> None:
    single_data = ReportData([mock_clips[0]], [], {})
    with pytest.raises(ReportError, match="at least 2 clips required"):
        generate_report(single_data, ReportConfig())


def test_generate_report_empty_frames_raises(report_data: ReportData) -> None:
    data = ReportData(report_data.clips, [], report_data.screenshots)
    with pytest.raises(ReportError, match="no frames provided"):
        generate_report(data, ReportConfig())


def test_generate_report_empty_screenshots_dict_raises(report_data: ReportData) -> None:
    data = ReportData(report_data.clips, report_data.frames, {})
    with pytest.raises(ReportError, match="no screenshots provided"):
        generate_report(data, ReportConfig())


def test_generate_report_missing_clip_key_raises(report_data: ReportData) -> None:
    bad_screens = report_data.screenshots.copy()
    del bad_screens["clip1"]
    data = ReportData(report_data.clips, report_data.frames, bad_screens)
    with pytest.raises(ReportError, match="no screenshots for clip: clip1"):
        generate_report(data, ReportConfig())


def test_generate_report_empty_clip_list_raises(report_data: ReportData) -> None:
    bad_screens = report_data.screenshots.copy()
    bad_screens["clip1"] = []
    data = ReportData(report_data.clips, report_data.frames, bad_screens)
    with pytest.raises(ReportError, match="no screenshots for clip: clip1"):
        generate_report(data, ReportConfig())


def test_generate_report_length_mismatch_raises(report_data: ReportData) -> None:
    bad_screens = report_data.screenshots.copy()
    bad_screens["clip1"] = bad_screens["clip1"][:-1]  # Remove one
    data = ReportData(report_data.clips, report_data.frames, bad_screens)
    with pytest.raises(ReportError, match="screenshot count mismatch for clip1"):
        generate_report(data, ReportConfig())


def test_generate_report_screenshot_not_found_raises(
    report_data: ReportData, tmp_path: Path
) -> None:
    # Delete a file
    p = report_data.screenshots["clip1"][0]
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
    mocker.patch.object(Path, "write_text", side_effect=OSError("Disk full"))
    with pytest.raises(ReportError, match="failed to write report"):
        generate_report(report_data, ReportConfig(output_dir=str(tmp_path)))


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


def test_generate_report_filmstrip_included(report_data: ReportData, tmp_path: Path) -> None:
    config = ReportConfig(include_filmstrip=True, output_dir=str(tmp_path))
    out_path = generate_report(report_data, config)
    content = out_path.read_text(encoding="utf-8")
    assert 'class="rv-filmstrip"' in content


def test_generate_report_escapes_dynamic_html_and_hardens_json_script_tag(tmp_path: Path) -> None:
    clips = [
        ClipInfo(
            name="clip1",
            path=tmp_path / "clip1.mkv",
            frame_count=100,
            resolution=(1920, 1080),
            fps=24.0,
            hdr=False,
            label="<b>REF</b>",
        ),
        ClipInfo(
            name="clip2",
            path=tmp_path / "clip2.mkv",
            frame_count=100,
            resolution=(1920, 1080),
            fps=24.0,
            hdr=False,
            label='ENC"></option><script>alert(2)</script>',
        ),
    ]

    screenshots: dict[str, list[Path]] = {}
    for clip in clips:
        p = tmp_path / "screens" / clip.name / "0.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fake_png_data")
        screenshots[clip.name] = [p]

    title = "</script><script>alert(1)</script>"
    report_data = ReportData(
        clips=clips,
        frames=[10],
        screenshots=screenshots,
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
    mocker.patch.object(report_module, "os_path_relpath", side_effect=ValueError)

    src = report_module._image_src_for_report(
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
    content = out_path.read_text(encoding="utf-8")

    # Extract JSON from script tag
    start = content.find('<script type="application/json" id="report-data">') + len(
        '<script type="application/json" id="report-data">'
    )
    end = content.find("</script>", start)
    json_str = content[start:end]

    data = json.loads(json_str)
    assert data["version"] == "1.0"
    assert "generated_at" in data
    assert len(data["clips"]) == 2
    assert len(data["frames"]) == 2
    assert data["clips"][0]["name"] == "clip1"
    assert data["frames"][0]["number"] == 10
    assert len(data["frames"][0]["images"]) == 2


def test_clip_info_frozen() -> None:
    c = ClipInfo("n", Path("p"), 100, (1920, 1080), 24.0, False)
    with pytest.raises(FrozenInstanceError):
        c.name = "new"  # type: ignore


def test_report_data_frozen(report_data: ReportData) -> None:
    with pytest.raises(FrozenInstanceError):
        report_data.frames = []  # type: ignore
