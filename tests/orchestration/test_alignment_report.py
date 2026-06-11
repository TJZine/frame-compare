"""Unit tests for frame alignment diagnostics reporting helpers."""

from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.orchestration.alignment_report import (
    AlignmentReportComparison,
    build_frame_alignment_report,
    emit_frame_alignment_report,
)
from frame_compare.orchestration.context import (
    ClipAlignmentState,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)


def _make_clip_state(
    path: str,
    label: str,
    *,
    num_frames: int = 100,
    trim_start_frames: int = 0,
    trim_end_frame_inclusive: int | None = None,
    alignment: ClipAlignmentState | None = None,
) -> ClipState:
    source_fps = Fraction(24, 1)
    probe = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(Path(path), 123, 456),
        width=1920,
        height=1080,
        num_frames=num_frames,
        fps=source_fps,
        is_hdr=False,
    )
    clip = ClipState(
        path=Path(path),
        label=label,
        probe=probe,
        source_fps=source_fps,
        effective_fps=source_fps,
        alignment=alignment,
    )
    return clip.with_trim(
        trim_start_frames=trim_start_frames,
        trim_end_frame_inclusive=trim_end_frame_inclusive,
    )


def test_build_frame_alignment_report_uses_final_normalized_trim_domain() -> None:
    reference = _make_clip_state(
        "ref.mkv",
        "Reference",
        num_frames=1000,
        trim_start_frames=155,
        trim_end_frame_inclusive=999,
    )
    comparison = _make_clip_state(
        "encode.mkv",
        "Encode",
        num_frames=845,
        trim_start_frames=0,
        trim_end_frame_inclusive=844,
        alignment=ClipAlignmentState(
            reference_stem="ref",
            comparison_stem="encode",
            relative_offset_frames=155,
            source="manual",
        ),
    )

    report = build_frame_alignment_report(reference=reference, comparisons=[comparison])

    assert report == (
        AlignmentReportComparison(
            label="Encode",
            alignment_source="manual",
            relative_offset_frames=155,
            reference_row_zero_source_frame=155,
            comparison_row_zero_source_frame=0,
            reference_trim_range=(155, 999),
            comparison_trim_range=(0, 844),
        ),
    )


def test_emit_frame_alignment_report_renders_human_panel_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode [candidate]",
        alignment_source="manual",
        relative_offset_frames=155,
        reference_row_zero_source_frame=155,
        comparison_row_zero_source_frame=0,
        reference_trim_range=(155, 999),
        comparison_trim_range=(0, 844),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[0, 28, 83],
        alignment_warnings=[],
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Frame Alignment" in captured.err
    assert "After Alignment" in captured.err
    assert "comparison" in captured.err
    assert "Encode [candidate]" in captured.err
    assert "manual" in captured.err
    assert "+155f" in captured.err
    for fact in ("155", "999", "0", "844", "28", "83"):
        assert fact in captured.err
    assert "\x1b[" not in captured.err
    assert "[bold cyan]" not in captured.err


def test_emit_frame_alignment_report_noop_without_material_alignment_info(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode",
        alignment_source=None,
        relative_offset_frames=None,
        reference_row_zero_source_frame=0,
        comparison_row_zero_source_frame=0,
        reference_trim_range=(0, 99),
        comparison_trim_range=(0, 99),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[0, 50, 99],
        alignment_warnings=[],
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_emit_frame_alignment_report_noop_for_zero_offset_alignment_without_trim_change(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode",
        alignment_source="manual",
        relative_offset_frames=0,
        reference_row_zero_source_frame=0,
        comparison_row_zero_source_frame=0,
        reference_trim_range=(0, 99),
        comparison_trim_range=(0, 99),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[0, 50, 99],
        alignment_warnings=[],
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_emit_frame_alignment_report_renders_zero_offset_trim_change(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode",
        alignment_source="manual",
        relative_offset_frames=0,
        reference_row_zero_source_frame=12,
        comparison_row_zero_source_frame=8,
        reference_trim_range=(12, 90),
        comparison_trim_range=(8, 86),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[0, 50],
        alignment_warnings=[],
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Frame Alignment" in captured.err
    assert "+0f" in captured.err
    assert "Reference source 12 <-> Encode source 8" in captured.err
    assert "Reference 12..90, Encode 8..86" in captured.err


def test_emit_frame_alignment_report_noop_for_unequal_lengths_without_alignment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode",
        alignment_source=None,
        relative_offset_frames=None,
        reference_row_zero_source_frame=0,
        comparison_row_zero_source_frame=0,
        reference_trim_range=(0, 119),
        comparison_trim_range=(0, 95),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[0, 50],
        alignment_warnings=[],
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_emit_frame_alignment_report_noop_in_quiet_and_json_modes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode",
        alignment_source="computed",
        relative_offset_frames=-4,
        reference_row_zero_source_frame=0,
        comparison_row_zero_source_frame=4,
        reference_trim_range=(0, 95),
        comparison_trim_range=(4, 99),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[0],
        alignment_warnings=[],
        json_output=False,
        quiet=True,
        no_color=True,
    )
    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[0],
        alignment_warnings=[],
        json_output=True,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_emit_frame_alignment_report_caps_selected_frame_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode",
        alignment_source="cached",
        relative_offset_frames=1,
        reference_row_zero_source_frame=1,
        comparison_row_zero_source_frame=0,
        reference_trim_range=(1, 99),
        comparison_trim_range=(0, 98),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=list(range(12)),
        alignment_warnings=[],
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert "aligned 0, 1, 2, 3, 4, 5, 6, 7, ... (12 total)" in captured.err


def test_emit_frame_alignment_report_renders_rejected_alignment_warning_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode",
        alignment_source=None,
        relative_offset_frames=None,
        reference_row_zero_source_frame=0,
        comparison_row_zero_source_frame=0,
        reference_trim_range=(0, 99),
        comparison_trim_range=(0, 99),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[],
        alignment_warnings=["align: encode low confidence; left unapplied and untrimmed"],
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert "Frame Alignment" in captured.err
    assert "Encode" in captured.err
    assert "none" in captured.err
    assert "warnings" in captured.err
    assert "rejected" in captured.err
    assert "align: encode low confidence; left unapplied and untrimmed" in captured.err


def test_emit_frame_alignment_report_preserves_literal_brackets_in_warnings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparison = AlignmentReportComparison(
        label="Encode",
        alignment_source=None,
        relative_offset_frames=None,
        reference_row_zero_source_frame=0,
        comparison_row_zero_source_frame=0,
        reference_trim_range=(0, 99),
        comparison_trim_range=(0, 99),
    )

    emit_frame_alignment_report(
        stage="after_align",
        comparisons=[comparison],
        selected_frames=[],
        alignment_warnings=["align: encode [low] confidence"],
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert "align: encode [low] confidence" in captured.err
    assert "\x1b[" not in captured.err
