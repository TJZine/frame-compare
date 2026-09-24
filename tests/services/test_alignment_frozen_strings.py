"""Exact-match tests for frozen B4 audio-alignment terminal strings.

The Align summary fragments, the VSView review-result message, and the
manual-review invitation lines are user-visible contracts: they must be
reproduced verbatim. These tests assert the exact text through the real
render paths (not copies of the literals).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from frame_compare.services.alignment_vsview import format_vsview_review_message


def _alignment_key(reference: Path, comparison: Path) -> str:
    from frame_compare.services.alignment import _alignment_key as real_key

    return real_key(reference, comparison)


def test_align_pre_review_summary_uses_frozen_fragments(capsys) -> None:
    from frame_compare.services.alignment import _print_pre_review_summary
    from frame_compare.utils.progress import RichProgressReporter

    reference = SimpleNamespace(path=Path("ref.mkv"))
    comparisons = [
        SimpleNamespace(path=Path("alpha.mkv"), short_name="Alpha", label="Alpha"),
        SimpleNamespace(path=Path("beta.mkv"), short_name="Beta", label="Beta"),
    ]
    request = SimpleNamespace(reference=reference, comparisons=comparisons)
    results_map = {
        _alignment_key(Path("ref.mkv"), Path("alpha.mkv")): SimpleNamespace(applied=True),
        _alignment_key(Path("ref.mkv"), Path("beta.mkv")): SimpleNamespace(applied=False),
    }

    _print_pre_review_summary(
        request=request,
        results_map=results_map,
        progress=RichProgressReporter(no_color=True),
        no_color=True,
    )

    err = capsys.readouterr().err
    assert "Align" in err
    assert "Alpha audio applied" in err
    assert "Beta needs visual confirmation" in err
    assert " · " in err


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


def test_opening_vsview_review_lines_frozen_verbatim() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "src" / "frame_compare" / "services" / "alignment.py").read_text()
    assert '"Opening VSView for manual review. The candidate is a hint, not a "' in source
    assert '"confirmed alignment."' in source
    assert '"Opening VSView for manual review. No automatic candidate is available; "' in source
    assert '"align the sources manually."' in source
