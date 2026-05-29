"""Unit tests for consolidated FPS reporting helpers."""

from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot, ClipState
from frame_compare.orchestration.fps_report import (
    FpsReportClip,
    build_consolidated_fps_report,
    emit_consolidated_fps_report,
)


def _make_clip_state(path: str, label: str, fps: Fraction, effective_fps: Fraction) -> ClipState:
    fingerprint = ClipFingerprint(Path(path), 123, 456)
    probe = ClipProbeSnapshot(
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=100,
        fps=fps,
        is_hdr=False,
    )
    return ClipState(
        path=Path(path),
        label=label,
        probe=probe,
        source_fps=fps,
        effective_fps=effective_fps,
    )


def test_build_consolidated_fps_report_orders_reference_then_comparisons() -> None:
    reference = _make_clip_state("ref.mkv", "Reference", Fraction(24, 1), Fraction(24, 1))
    comp1 = _make_clip_state("a.mkv", "Encode 1", Fraction(24, 1), Fraction(24, 1))
    comp2 = _make_clip_state("b.mkv", "Encode 2", Fraction(24, 1), Fraction(24, 1))

    report = build_consolidated_fps_report(reference, [comp1, comp2])

    assert report[0].label == "Reference"
    assert report[1].label == "Encode 1"
    assert report[2].label == "Encode 2"


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


def test_emit_consolidated_fps_report_noop_when_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    clip = FpsReportClip(
        path=Path("ref.mkv"),
        label="Reference",
        source_fps=Fraction(24, 1),
        effective_fps=Fraction(24, 1),
        fps_divergent=False,
        note=None,
    )

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("No output should be emitted when quiet=True")

    monkeypatch.setattr("frame_compare.orchestration.fps_report.log.info", _fail)

    emit_consolidated_fps_report(
        stage="after_load_sources",
        clips=[clip],
        json_output=True,
        quiet=True,
    )


def test_emit_consolidated_fps_report_renders_human_table_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    clips = [
        FpsReportClip(
            path=Path("ref.mkv"),
            label="Reference",
            source_fps=Fraction(24000, 1001),
            effective_fps=Fraction(24000, 1001),
            fps_divergent=False,
            note=None,
        ),
        FpsReportClip(
            path=Path("encode.mkv"),
            label="Encode",
            source_fps=Fraction(30000, 1001),
            effective_fps=Fraction(24000, 1001),
            fps_divergent=True,
            note="assumed",
        ),
    ]

    emit_consolidated_fps_report(
        stage="after_align",
        clips=clips,
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Clip FPS" in captured.err
    assert "After Alignment" in captured.err
    assert "reference" in captured.err
    assert "encode 1" in captured.err
    assert "Reference" in captured.err
    assert "Encode" in captured.err
    assert "24000/1001" in captured.err
    assert "30000/1001 -> 24000/1001" in captured.err
    assert "matched" in captured.err
    assert "adjusted" in captured.err
    assert "\x1b[" not in captured.err
