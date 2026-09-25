"""Exact-match tests for frozen B4 audio-alignment terminal strings.

The Align summary fragments, the VSView review-result message, and the
manual-review invitation lines are user-visible contracts: they must be
reproduced verbatim. These tests assert the exact text through the real
render paths (not copies of the literals).
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.services.alignment import align_clips_from_request as _align_async
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.alignment_vsview import format_vsview_review_message
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from tests.services.alignment_request_test_support import alignment_request
from tests.services.test_alignment_diagnostics import audio_attempt


def _alignment_key(reference: Path, comparison: Path) -> str:
    from frame_compare.services.alignment import _alignment_key as real_key

    return real_key(reference, comparison)


def test_align_pre_review_summary_uses_frozen_fragments(tmp_path: Path, capsys) -> None:
    from frame_compare.services.alignment import _print_pre_review_summary
    from frame_compare.utils.progress import RichProgressReporter

    reference, alpha, beta = (tmp_path / name for name in ("ref.mkv", "alpha.mkv", "beta.mkv"))
    for path in (reference, alpha, beta):
        path.touch()
    request = alignment_request(
        reference=reference,
        comparisons=[alpha, beta],
        config=AlignmentConfig(),
        generated_dir=tmp_path,
    )
    request = replace(
        request,
        comparisons=[
            replace(comparison, short_name=short_name)
            for comparison, short_name in zip(request.comparisons, ("Alpha", "Beta"), strict=True)
        ],
    )
    results_map = {
        _alignment_key(reference, comparison): AlignmentResult(
            reference.name,
            comparison.name,
            None,
            None,
            0.0,
            None,
            "computed",
            applied=applied,
        )
        for comparison, applied in ((alpha, True), (beta, False))
    }

    _print_pre_review_summary(
        request=request,
        results_map=results_map,
        progress=RichProgressReporter(no_color=True),
        no_color=True,
    )

    err = capsys.readouterr().err
    assert "Align" in err
    assert "Alpha audio applied · Beta needs visual confirmation" in err


def test_vsview_review_message_singular_pair_and_kept() -> None:
    assert (
        format_vsview_review_message(1, 1)
        == "Accepted 1 confirmed pair; 1 comparison kept its current offset."
    )


def test_vsview_review_message_plural_pairs_and_kept() -> None:
    assert (
        format_vsview_review_message(2, 1)
        == "Accepted 2 confirmed pairs; 1 comparison kept its current offset."
    )


def test_vsview_review_message_plural_kept() -> None:
    assert (
        format_vsview_review_message(2, 3)
        == "Accepted 2 confirmed pairs; 3 comparisons kept their current offset."
    )


def test_vsview_review_message_omits_kept_clause_when_zero() -> None:
    assert format_vsview_review_message(2, 0) == "Accepted 2 confirmed pairs."


@pytest.mark.parametrize(
    ("has_candidate", "expected"),
    [
        (
            True,
            "Opening VSView for manual review. The candidate is a hint, not a confirmed alignment.",
        ),
        (
            False,
            "Opening VSView for manual review. No automatic candidate is available; "
            "align the sources manually.",
        ),
    ],
)
def test_opening_vsview_review_lines_frozen_verbatim(
    has_candidate: bool,
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True, use_vsview=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        lambda: VSViewAvailability(
            status=VSViewAvailabilityStatus.MISSING_RUNTIME, message="missing"
        ),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=False, stdout=True, stderr=False),
    )
    attempt = audio_attempt()
    if not has_candidate:
        attempt = replace(
            attempt,
            windows=tuple(
                replace(window, terminal_category="insufficient_signal")
                for window in attempt.windows
            ),
            decision=replace(
                attempt.decision,
                state="unavailable",
                candidate=None,
                primary_reason="no_usable_windows",
                raw_correlated_windows=0,
                consensus_windows=0,
                consensus_ratio=None,
                aggregate_score=None,
                minimum_peak_ratio=None,
            ),
        )
    consensus = AlignmentConsensus(
        None,
        0.99,
        False,
        "insufficient_consensus",
        5,
        4,
        0.8,
        2.0,
        window_records=attempt.windows,
        decision=attempt.decision,
        audio_attempt=attempt,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: consensus,
    )
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    asyncio.run(
        _align_async(
            request,
            config,
            reference_fps=Fraction(24),
        )
    )

    err = capsys.readouterr().err
    assert expected in err
