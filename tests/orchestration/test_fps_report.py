"""Unit tests for consolidated FPS reporting helpers."""

import os
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot, ClipState
from frame_compare.orchestration.fps_report import (
    FpsReportClip,
    build_consolidated_fps_report,
    emit_consolidated_fps_report,
)
from frame_compare.services.release_identity import ContentIdentity, ReleaseIdentity


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
    assert output.count("Avatar Aang The Last Airbender (2026)") == 1
    assert "Reference label" in output
    assert "2160p | PMTP WEB-DL | DV HDR10+ | Kitsune" in output
    assert "2160p | ATV WEB-DL | DV HDR10+ | REPACK | Kitsune" in output
    assert output.count("Avatar.Aang.PMTP.Kitsune.mkv") == 1
    assert output.count("Avatar.Aang.ATV.REPACK.Kitsune.mkv") == 1
    assert "1920x1080" in output


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
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert len(log_calls) == 1
    event, stage, clips, diagnostics = log_calls[0]
    assert event == "fps_report"
    assert stage == "after_load_sources"
    assert diagnostics == []
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
            size_bytes=6 * 1024**3,
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
    assert "[OK] Sources — 2 loaded" in captured.err
    assert "Sources" in captured.err
    assert "After Load Sources" not in captured.err
    assert "Reference" in captured.err
    assert "Comparison 1" in captured.err
    assert "Reference [source]" in captured.err
    assert "Encode [candidate]" in captured.err
    assert "3840x2160" in captured.err
    assert "1920x1080" in captured.err
    assert "24000/1001" in captured.err
    assert "30000/1001 -> 24000/1001" in captured.err
    assert "2,400 frames" in captured.err
    assert "1,200 frames" in captured.err
    assert "HDR" in captured.err
    assert "SDR" in captured.err
    assert "17.0 GiB" in captured.err
    assert "6.0 GiB" in captured.err
    assert "ref.mkv" in captured.err
    assert "encode.mkv" in captured.err
    assert "Analysis source: Comparison 1 | selected by configured policy" in captured.err
    assert "FPS target: 24000/1001 (majority)" in captured.err
    assert "\x1b[" not in captured.err
    assert "[bold cyan]" not in captured.err
    assert "[dim]" not in captured.err


def test_emit_consolidated_fps_report_uses_relative_input_and_external_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "frame_compare.orchestration.presentation.shutil.get_terminal_size",
        lambda **_: os.terminal_size((240, 24)),
    )
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
        input_dir=input_dir,
    )

    captured = capsys.readouterr()
    assert str(Path("season") / "reference.mkv") in captured.err
    assert str(external_path) in captured.err
    assert str(internal_path) not in captured.err


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
    assert "30000/1001 -> 24000/1001" in captured.err
    assert "adjusted" in captured.err
    assert "assumed" in captured.err
    assert "\x1b[" not in captured.err
    assert "[yellow]" not in captured.err
    assert "[dim]" not in captured.err


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
    assert captured.err == "  [OK] Frame rates match: 24/1\n"
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
    assert "30000/1001 -> 24000/1001" in captured.err
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
    assert "30/1 -> 25/1" in captured.err
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
        input_dir=Path("/workspace/comparison_videos"),
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[OK] Sources — 1 loaded" in captured.err
    assert "A source with" in captured.err
    assert "deliberately" in captured.err
    assert "\x1b[" not in captured.err
    assert all(len(line) <= columns for line in captured.err.splitlines())
