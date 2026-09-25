"""Unit tests for consolidated FPS reporting helpers."""

import os
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.ansi import AnsiDecoder
from rich.color import Color
from rich.style import Style

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot, ClipState
from frame_compare.orchestration.fps_report import (
    FpsReportClip,
    _length_difference_lines,
    build_consolidated_fps_report,
    emit_consolidated_fps_report,
)
from frame_compare.services.release_identity import ContentIdentity, ReleaseIdentity


@pytest.fixture(autouse=True)
def _stable_report_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "frame_compare.orchestration.presentation.shutil.get_terminal_size",
        lambda **_: os.terminal_size((240, 24)),
    )


def _assert_ansi_text_is_bold_cyan(output: str, label: str) -> None:
    cyan_number = Color.parse("cyan").number
    for line in AnsiDecoder().decode(output):
        for span in line.spans:
            if label not in line.plain[span.start : span.end]:
                continue
            assert isinstance(span.style, Style)
            assert span.style.bold is True
            assert span.style.color is not None
            assert span.style.color.number == cyan_number
            return
    pytest.fail(f"{label!r} was not rendered in bold cyan")


def _make_clip_state(
    path: str,
    label: str,
    fps: Fraction,
    effective_fps: Fraction,
    *,
    width: int = 1920,
    height: int = 1080,
    num_frames: int = 100,
    is_hdr: bool = False,
    size_bytes: int = 123,
    release_identity: ReleaseIdentity | None = None,
    label_is_explicit: bool = False,
) -> ClipState:
    fingerprint = ClipFingerprint(Path(path), size_bytes, 456)
    probe = ClipProbeSnapshot(
        fingerprint=fingerprint,
        width=width,
        height=height,
        num_frames=num_frames,
        fps=fps,
        is_hdr=is_hdr,
    )
    return ClipState(
        path=Path(path),
        label=label,
        probe=probe,
        source_fps=fps,
        effective_fps=effective_fps,
        release_identity=release_identity,
        label_is_explicit=label_is_explicit,
    )


def test_sources_factors_reliable_content_and_keeps_release_file_and_probe_facts_separate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    content = ContentIdentity("Avatar Aang The Last Airbender", year=2026)
    reference = _make_clip_state(
        "Avatar.Aang.PMTP.Kitsune.mkv",
        "Reference label",
        Fraction(24),
        Fraction(24),
        release_identity=ReleaseIdentity(
            content,
            resolution="2160p",
            service="PMTP",
            source_type="WEB-DL",
            dynamic_range_claims=("DV", "HDR10+"),
            release_group="Kitsune",
        ),
        label_is_explicit=True,
    )
    comparison = _make_clip_state(
        "Avatar.Aang.ATV.REPACK.Kitsune.mkv",
        "Generated label",
        Fraction(24),
        Fraction(24),
        release_identity=ReleaseIdentity(
            content,
            resolution="2160p",
            service="ATV",
            source_type="WEB-DL",
            dynamic_range_claims=("DV", "HDR10+"),
            revision_tags=("REPACK",),
            release_group="Kitsune",
        ),
    )

    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=build_consolidated_fps_report(reference, [comparison]),
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
    )

    output = capsys.readouterr().err
    assert "Reference label" in output
    assert "PMTP WEB-DL" not in output
    assert output.count("Avatar Aang The Last Airbender (2026)") == 1
    assert "2160p · ATV WEB-DL · DV HDR10+ · REPACK · Kitsune" in output
    assert output.count("Avatar.Aang.PMTP.Kitsune.mkv") == 1
    assert output.count("Avatar.Aang.ATV.REPACK.Kitsune.mkv") == 1
    assert "1920×1080" in output


def test_sources_standard_name_uses_dot_separator_without_common_content(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference = _make_clip_state(
        "Show.A.S1.mkv",
        "Reference",
        Fraction(24),
        Fraction(24),
        release_identity=ReleaseIdentity(
            ContentIdentity("Show A"),
            resolution="1080p",
            service="AMZN",
            source_type="WEB-DL",
            release_group="SCOPE",
        ),
    )
    comparison = _make_clip_state(
        "Show.B.S1.mkv",
        "Comparison",
        Fraction(24),
        Fraction(24),
        release_identity=ReleaseIdentity(
            ContentIdentity("Show B"),
            resolution="1080p",
            service="AMZN",
            source_type="WEB-DL",
            release_group="SIGMA",
        ),
    )

    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=build_consolidated_fps_report(reference, [comparison]),
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
    )

    output = capsys.readouterr().err
    assert "Show A · 1080p · AMZN WEB-DL · SCOPE" in output
    assert "Show B · 1080p · AMZN WEB-DL · SIGMA" in output
    assert "Show A | 1080p" not in output
    assert "Show B | 1080p" not in output


def test_build_consolidated_fps_report_includes_probe_metadata_and_fps_order() -> None:
    reference = _make_clip_state(
        "ref.mkv",
        "Reference",
        Fraction(24000, 1001),
        Fraction(24000, 1001),
        width=3840,
        height=2160,
        num_frames=2400,
        is_hdr=True,
    )
    comp1 = _make_clip_state(
        "a.mkv",
        "Encode 1",
        Fraction(30000, 1001),
        Fraction(24000, 1001),
        width=1920,
        height=1080,
        num_frames=1200,
        is_hdr=False,
    )
    comp2 = _make_clip_state("b.mkv", "Encode 2", Fraction(24, 1), Fraction(24, 1))

    report = build_consolidated_fps_report(reference, [comp1, comp2])

    assert report[0].label == "Reference"
    assert report[1].label == "Encode 1"
    assert report[2].label == "Encode 2"
    assert report[0].width == 3840
    assert report[0].height == 2160
    assert report[0].num_frames == 2400
    assert report[0].is_hdr is True
    assert report[0].size_bytes == 123
    assert report[1].width == 1920
    assert report[1].height == 1080
    assert report[1].num_frames == 1200
    assert report[1].is_hdr is False
    assert report[1].source_fps == Fraction(30000, 1001)
    assert report[1].effective_fps == Fraction(24000, 1001)
    assert report[1].fps_divergent is True


def test_build_consolidated_fps_report_with_empty_comparisons_returns_reference_only() -> None:
    reference = _make_clip_state("ref.mkv", "Reference", Fraction(24, 1), Fraction(24, 1))

    report = build_consolidated_fps_report(reference, [])

    assert len(report) == 1
    assert report[0].label == "Reference"
    assert report[0].path == reference.path


def test_build_consolidated_fps_report_flags_divergence_when_effective_fps_differs() -> None:
    reference = _make_clip_state("ref.mkv", "Reference", Fraction(24, 1), Fraction(24, 1))
    comp = _make_clip_state("a.mkv", "Encode 1", Fraction(24, 1), Fraction(30000, 1001))

    report = build_consolidated_fps_report(reference, [comp])

    assert report[1].fps_divergent is True


def test_emit_consolidated_fps_report_noop_when_quiet(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clip = FpsReportClip(
        path=Path("ref.mkv"),
        label="Reference",
        width=1920,
        height=1080,
        num_frames=100,
        is_hdr=False,
        source_fps=Fraction(24, 1),
        effective_fps=Fraction(24, 1),
        fps_divergent=False,
        note=None,
    )

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("No logs should be emitted when quiet=True")

    monkeypatch.setattr("frame_compare.orchestration.fps_report.log", SimpleNamespace(info=_fail))

    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=[clip],
        json_output=True,
        quiet=True,
        rich_output=False,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_emit_consolidated_fps_report_json_mode_logs_without_human_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clip = FpsReportClip(
        path=Path("ref.mkv"),
        label="Reference",
        width=1920,
        height=1080,
        num_frames=100,
        is_hdr=False,
        source_fps=Fraction(24, 1),
        effective_fps=Fraction(24, 1),
        fps_divergent=False,
        note=None,
    )

    log_calls: list[tuple[str, str, list[dict[str, object]], list[str]]] = []

    def _record_log(
        event: str, *, stage: str, clips: list[dict[str, object]], diagnostics: list[str]
    ) -> None:
        log_calls.append((event, stage, clips, diagnostics))

    monkeypatch.setattr(
        "frame_compare.orchestration.fps_report.log", SimpleNamespace(info=_record_log)
    )

    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=[clip],
        json_output=True,
        quiet=False,
        rich_output=False,
        diagnostics=["Analysis source: Reference | selected by fastest-source policy"],
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert len(log_calls) == 1
    event, stage, clips, diagnostics = log_calls[0]
    assert event == "fps_report"
    assert stage == "after_load_sources"
    assert diagnostics == ["Analysis source: Reference | selected by fastest-source policy"]
    assert len(clips) == 1
    assert {
        "path",
        "label",
        "width",
        "height",
        "num_frames",
        "is_hdr",
        "source_fps_num",
        "source_fps_den",
        "effective_fps_num",
        "effective_fps_den",
        "fps_divergent",
        "note",
    } <= clips[0].keys()
    assert clips[0]["path"] == "ref.mkv"
    assert clips[0]["label"] == "Reference"
    assert clips[0]["source_fps_num"] == 24
    assert clips[0]["source_fps_den"] == 1
    assert clips[0]["effective_fps_num"] == 24
    assert clips[0]["fps_divergent"] is False
    assert "size_bytes" not in clips[0]


def test_emit_consolidated_fps_report_renders_human_table_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clips = [
        FpsReportClip(
            path=Path("ref.mkv"),
            label="Reference [source]",
            width=3840,
            height=2160,
            num_frames=2400,
            is_hdr=True,
            source_fps=Fraction(24000, 1001),
            effective_fps=Fraction(24000, 1001),
            fps_divergent=False,
            note=None,
            size_bytes=17 * 1024**3,
        ),
        FpsReportClip(
            path=Path("encode.mkv"),
            label="Encode [candidate]",
            width=1920,
            height=1080,
            num_frames=1200,
            is_hdr=False,
            source_fps=Fraction(30000, 1001),
            effective_fps=Fraction(24000, 1001),
            fps_divergent=True,
            note="assumed",
            size_bytes=0,
        ),
    ]

    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=clips,
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
        diagnostics=[
            "Analysis source: Comparison 1 | selected by configured policy",
            "FPS target: 24000/1001 (majority)",
        ],
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Sources · 2 loaded" in captured.err
    assert "Sources" in captured.err
    assert "After Load Sources" not in captured.err
    assert "3840×2160" in captured.err
    assert "1920×1080" in captured.err
    assert "23.976 fps" in captured.err
    assert "2,400 frames" in captured.err
    assert "1,200 frames" in captured.err
    assert "17.00 GiB" in captured.err
    assert "0.00 B" not in captured.err
    assert "ref.mkv" in captured.err
    assert "encode.mkv" in captured.err
    assert "Lengths differ" in captured.err
    assert "1200 frames" in captured.err
    assert "FPS target: 24000/1001 (majority)" in captured.err
    assert "analysis source" in captured.err
    assert "(configured)" in captured.err
    assert "selected by configured policy" not in captured.err
    assert "\x1b[" not in captured.err
    assert "[bold cyan]" not in captured.err
    assert "[dim]" not in captured.err

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("TERM", "xterm-256color")
    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=clips,
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=False,
    )

    colored = capsys.readouterr()
    assert colored.out == ""
    assert "\x1b[" in colored.err
    assert "ref.mkv" in colored.err
    assert "encode.mkv" in colored.err


def test_emit_consolidated_fps_report_uses_relative_input_and_external_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "comparison_videos"
    internal_path = input_dir / "season" / "reference.mkv"
    external_path = tmp_path / "outside" / "comparison.mkv"
    clips = [
        FpsReportClip(
            path=internal_path,
            label="Reference",
            width=1920,
            height=1080,
            num_frames=100,
            is_hdr=False,
            source_fps=Fraction(24, 1),
            effective_fps=Fraction(24, 1),
            fps_divergent=False,
            note=None,
        ),
        FpsReportClip(
            path=external_path,
            label="Comparison",
            width=1920,
            height=1080,
            num_frames=100,
            is_hdr=False,
            source_fps=Fraction(24, 1),
            effective_fps=Fraction(24, 1),
            fps_divergent=False,
            note=None,
        ),
    ]

    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=clips,
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert "reference.mkv" in captured.err
    assert "comparison.mkv" in captured.err
    assert str(internal_path) not in captured.err
    assert str(external_path) not in captured.err

    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=clips,
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
        verbose=True,
    )

    verbose_captured = capsys.readouterr()
    assert str(internal_path.resolve()) in verbose_captured.err
    assert str(external_path.resolve()) in verbose_captured.err


def _length_clip(name: str, num_frames: int, fps: Fraction = Fraction(24, 1)) -> FpsReportClip:
    return FpsReportClip(
        path=Path(f"{name}.mkv"),
        label=name,
        width=1920,
        height=1080,
        num_frames=num_frames,
        is_hdr=False,
        source_fps=fps,
        effective_fps=fps,
        fps_divergent=False,
        note=None,
    )


def test_length_difference_groups_shared_counts_and_marks_shorter() -> None:
    clips = [
        _length_clip("ref", 1000),
        _length_clip("a", 536),
        _length_clip("b", 536),
    ]

    (line,) = _length_difference_lines(clips, ["ref", "a", "b"])

    assert "a and b" in line
    assert "464 frames" in line
    assert "(19.3 s)" in line
    assert "shorter than ref" in line


def test_length_difference_marks_longer_and_formats_minutes() -> None:
    clips = [_length_clip("ref", 1000), _length_clip("a", 1000 + 144 * 24)]

    (line,) = _length_difference_lines(clips, ["ref", "a"])

    assert "3456 frames" in line
    assert "(2m 24s)" in line
    assert "longer than ref" in line


def test_length_difference_joins_three_names_and_singular_frame() -> None:
    clips = [
        _length_clip("ref", 1000),
        _length_clip("a", 999),
        _length_clip("b", 999),
        _length_clip("c", 999),
    ]

    (line,) = _length_difference_lines(clips, ["ref", "a", "b", "c"])

    assert "a, b, and c" in line
    assert "1 frame" in line
    assert "1 frames" not in line
    assert "(0.0 s)" in line


def test_emit_consolidated_fps_report_keeps_after_align_fps_panel(
    capsys: pytest.CaptureFixture[str],
) -> None:
    clip = FpsReportClip(
        path=Path("encode.mkv"),
        label="Encode",
        width=1920,
        height=1080,
        num_frames=1200,
        is_hdr=False,
        source_fps=Fraction(30000, 1001),
        effective_fps=Fraction(24000, 1001),
        fps_divergent=True,
        note="assumed",
    )

    emit_consolidated_fps_report(
        stage="after_align",
        clips=[clip],
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert "Frame rates" in captured.err
    assert "After Alignment" in captured.err
    assert "29.97 fps (30000/1001) -> 23.976 fps (24000/1001)" in captured.err
    assert "adjusted" in captured.err
    assert "assumed" in captured.err
    assert "\x1b[" not in captured.err


def test_emit_consolidated_fps_report_collapses_matching_after_align_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference_path = tmp_path / "reference.mkv"
    comparison_path = tmp_path / "comparison.mkv"
    clips = [
        FpsReportClip(
            path=reference_path,
            label="Reference",
            width=1920,
            height=1080,
            num_frames=100,
            is_hdr=False,
            source_fps=Fraction(24, 1),
            effective_fps=Fraction(24, 1),
            fps_divergent=False,
            note=None,
        ),
        FpsReportClip(
            path=comparison_path,
            label="Comparison",
            width=1920,
            height=1080,
            num_frames=100,
            is_hdr=False,
            source_fps=Fraction(24, 1),
            effective_fps=Fraction(24, 1),
            fps_divergent=False,
            note=None,
        ),
    ]

    emit_consolidated_fps_report(
        stage="after_align",
        clips=clips,
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "frame rates match · 24 fps (24/1)" in captured.err
    assert str(reference_path) not in captured.err


def test_emit_consolidated_fps_report_logs_non_tty_diagnostics_without_rich_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference_path = tmp_path / "reference.mkv"
    clip = FpsReportClip(
        path=reference_path,
        label="Reference",
        width=1920,
        height=1080,
        num_frames=100,
        is_hdr=False,
        source_fps=Fraction(24, 1),
        effective_fps=Fraction(24, 1),
        fps_divergent=False,
        note=None,
    )

    log_calls: list[tuple[str, str, list[dict[str, object]], list[str]]] = []

    def _record_log(
        event: str, *, stage: str, clips: list[dict[str, object]], diagnostics: list[str]
    ) -> None:
        log_calls.append((event, stage, clips, diagnostics))

    monkeypatch.setattr(
        "frame_compare.orchestration.fps_report.log", SimpleNamespace(info=_record_log)
    )

    emit_consolidated_fps_report(
        stage="after_align",
        clips=[clip],
        json_output=False,
        quiet=False,
        rich_output=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert len(log_calls) == 1
    event, stage, clips, diagnostics = log_calls[0]
    assert event == "fps_report"
    assert stage == "after_align"
    assert clips[0]["effective_fps_num"] == 24
    assert clips[0]["effective_fps_den"] == 1
    assert diagnostics == []


def test_emit_consolidated_fps_report_keeps_adjustment_evidence_without_normal_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison_path = tmp_path / "comparison.mkv"
    clip = FpsReportClip(
        path=comparison_path,
        label="Comparison",
        width=1920,
        height=1080,
        num_frames=100,
        is_hdr=False,
        source_fps=Fraction(30000, 1001),
        effective_fps=Fraction(24000, 1001),
        fps_divergent=True,
        note="assumed",
    )

    emit_consolidated_fps_report(
        stage="after_align",
        clips=[clip],
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert "29.97 fps (30000/1001) -> 23.976 fps (24000/1001)" in captured.err
    assert "adjusted" in captured.err
    assert str(comparison_path) not in captured.err


def test_emit_consolidated_fps_report_prioritizes_effective_fps_divergence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference = _make_clip_state("ref.mkv", "Reference", Fraction(24), Fraction(24))
    comparison = _make_clip_state("comp.mkv", "Comparison", Fraction(30), Fraction(25))

    emit_consolidated_fps_report(
        stage="after_align",
        clips=build_consolidated_fps_report(reference, [comparison]),
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert "30 fps (30/1) -> 25 fps (25/1)" in captured.err
    assert "divergent" in captured.err
    assert "adjusted" not in captured.err


@pytest.mark.parametrize("columns", [60, 80, 120, 240])
def test_emit_consolidated_fps_report_wraps_at_narrow_terminal_widths(
    columns: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "frame_compare.orchestration.presentation.shutil.get_terminal_size",
        lambda **_: os.terminal_size((columns, 24)),
    )
    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=[
            FpsReportClip(
                path=Path("/workspace/comparison_videos/a-very-long-source-name.mkv"),
                label="A source with a deliberately long display label",
                width=3840,
                height=2160,
                num_frames=2400,
                is_hdr=True,
                source_fps=Fraction(24000, 1001),
                effective_fps=Fraction(24000, 1001),
                fps_divergent=False,
                note=None,
                size_bytes=17 * 1024**3,
            )
        ],
        json_output=False,
        quiet=False,
        rich_output=True,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Sources · 1 loaded" in captured.err
    assert "a-very-long-source-name.mkv" in captured.err
    assert "3840×2160" in captured.err
    assert "\x1b[" not in captured.err
