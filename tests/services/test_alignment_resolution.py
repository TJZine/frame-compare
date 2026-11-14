"""Comparison authority invariants, pure confirmation, and publication admission."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.services.alignment_diagnostics import original_attempt_digest
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_resolution import (
    confirm_manual,
    ordered_results,
    resolution_from_computation,
    resolution_from_override,
    resolution_from_reuse,
)
from frame_compare.services.alignment_reuse_cache import (
    comparison_cache_key,
    prepare_reusable_source_set,
    save_reusable_offsets,
)
from frame_compare.services.types import AlignmentResult, ComparisonResolution
from frame_compare.utils.alignment_evidence import AudioAlignmentAttempt
from frame_compare.utils.types import AlignmentRequest
from tests.alignment_review_test_support import (
    provisional_audio_attempt,
    trusted_audio_attempt,
    unavailable_audio_attempt,
)
from tests.services.alignment_request_test_support import alignment_request


def _computed(attempt: AudioAlignmentAttempt) -> AlignmentResult:
    accepted = attempt.decision.state == "trusted_automatic"
    candidate = attempt.decision.candidate
    return AlignmentResult(
        "ref.mkv",
        "comp.mkv",
        candidate.frame_offset if accepted and candidate else None,
        candidate.time_offset_seconds if accepted and candidate else None,
        0.99,
        "cross_correlation",
        "computed",
        applied=accepted,
        stability=attempt.stability,
        audio_attempt=attempt,
    )


@pytest.mark.parametrize(
    "attempt, confirmed, has_fallback",
    [
        (provisional_audio_attempt(frame_offset=12), 0, False),
        (trusted_audio_attempt(frame_offset=42), 47, True),
        (unavailable_audio_attempt(), 0, False),
    ],
)
def test_confirmation_replaces_authority_and_retains_original_attempt(
    attempt: AudioAlignmentAttempt, confirmed: int, has_fallback: bool
) -> None:
    original = resolution_from_computation(_computed(attempt), comparison_cache_key="comp")
    digest = original_attempt_digest(attempt)
    confirmed_resolution = confirm_manual(
        original,
        frame_offset=confirmed,
        fps_reference=Fraction(24),
        reference_clip=Path("ref.mkv"),
        comparison_clip=Path("comp.mkv"),
    )
    assert confirmed_resolution.origin == "interactive_confirmed_this_run"
    assert confirmed_resolution.accepted_offset == confirmed
    assert confirmed_resolution.result.time_offset_seconds == confirmed / 24
    assert confirmed_resolution.result.audio_attempt is attempt
    assert confirmed_resolution.result.stability is original.result.stability
    assert original_attempt_digest(confirmed_resolution.result.audio_attempt) == digest
    assert (confirmed_resolution.computed_fallback is original.result) is has_fallback
    assert original.result.source == "computed"
    assert original.result.audio_attempt is attempt


def test_historical_resolution_derives_evidence_and_preserves_zero() -> None:
    computed = _computed(trusted_audio_attempt())
    historical = replace(computed, source="cached", audio_attempt=None)
    reused = resolution_from_reuse(historical, comparison_cache_key="comp", computed=True)
    assert reused.evidence_availability == "historical_details_unavailable"
    assert reused.origin == "shared_computed_offsets"
    assert reused.accepted_offset == 0
    manual = replace(historical, source="manual", algorithm=None)
    assert (
        resolution_from_override(manual, comparison_cache_key="comp").origin
        == "preexisting_manual_override"
    )
    assert (
        resolution_from_reuse(manual, comparison_cache_key="comp", computed=False).origin
        == "shared_previous_offsets"
    )
    unavailable = resolution_from_computation(
        _computed(unavailable_audio_attempt()), comparison_cache_key="comp"
    )
    assert unavailable.accepted_offset is None
    assert unavailable.evidence_availability == "current_attempt"


@pytest.mark.parametrize(
    "origin",
    [
        "shared_computed_offsets",
        "shared_previous_offsets",
        "preexisting_manual_override",
        "interactive_confirmed_this_run",
    ],
)
def test_only_current_computation_may_be_unapplied(origin: str) -> None:
    with pytest.raises(ValueError, match="must be applied"):
        ComparisonResolution(_computed(provisional_audio_attempt()), "comp", origin)  # type: ignore[arg-type]


@pytest.mark.parametrize("fault", ["origin", "unapplied", "algorithm"])
def test_fallback_requires_confirmed_applied_computation(fault: str) -> None:
    result = _computed(trusted_audio_attempt())
    fallback = result
    origin = "interactive_confirmed_this_run"
    if fault == "origin":
        origin = "computed_this_run"
    elif fault == "unapplied":
        fallback = _computed(provisional_audio_attempt())
    else:
        fallback = replace(result, algorithm=None)
    with pytest.raises(ValueError, match="computed fallback"):
        ComparisonResolution(result, "comp", origin, fallback)


@pytest.fixture
def alignment_case(tmp_path: Path) -> AlignmentRequest:
    paths = [tmp_path / name for name in ("ref.mkv", "a.mkv", "b.mkv")]
    for path in paths:
        path.touch()
    return alignment_request(
        reference=paths[0], comparisons=paths[1:], generated_dir=tmp_path / "generated"
    )


def _resolutions(alignment_case: AlignmentRequest) -> dict[str, ComparisonResolution]:
    return {
        alignment_key(alignment_case.reference.path, clip.path): resolution_from_computation(
            replace(_computed(trusted_audio_attempt()), comparison_clip=clip.path.name),
            comparison_cache_key=comparison_cache_key(clip),
        )
        for clip in alignment_case.comparisons
    }


@pytest.mark.parametrize(
    "fault",
    [
        "empty-alignment_case",
        "missing",
        "wrong-key",
        "wrong-identity",
        "previous",
        "override",
        "unapplied",
        "no-attempt",
        "no-stability",
        "shared-no-stability",
        "all-historical",
        "fallback-no-stability",
    ],
)
def test_candidate_refuses_each_ineligible_source_set(
    alignment_case: AlignmentRequest, fault: str
) -> None:
    records = _resolutions(alignment_case)
    key = next(iter(records))
    item = records[key]
    if fault == "empty-alignment_case":
        alignment_case = replace(alignment_case, comparisons=[])
    elif fault == "missing":
        del records[key]
    elif fault == "wrong-key":
        records["foreign"] = records.pop(key)
    elif fault == "wrong-identity":
        records[key] = replace(item, comparison_cache_key="foreign")
    elif fault in {"previous", "override"}:
        records[key] = replace(
            item,
            origin="shared_previous_offsets"
            if fault == "previous"
            else "preexisting_manual_override",
        )
    elif fault == "unapplied":
        records[key] = replace(item, result=_computed(provisional_audio_attempt()))
    elif fault == "no-attempt":
        records[key] = replace(item, result=replace(item.result, audio_attempt=None))
    elif fault in {"no-stability", "shared-no-stability"}:
        records[key] = replace(
            item,
            result=replace(item.result, stability=None),
            origin="shared_computed_offsets" if fault.startswith("shared") else "computed_this_run",
        )
    elif fault == "all-historical":
        records = {
            key: replace(item, origin="shared_computed_offsets") for key, item in records.items()
        }
    else:
        records[key] = replace(
            item,
            origin="interactive_confirmed_this_run",
            computed_fallback=replace(item.result, stability=None),
        )
    assert prepare_reusable_source_set(alignment_case, records) is None
    assert not (alignment_case.shared_alignment_cache_dir / "alignment_reuse.toml").exists()


def test_candidate_orders_requested_records_and_ignores_unrelated(
    alignment_case: AlignmentRequest,
) -> None:
    records = _resolutions(alignment_case)
    keys = list(records)
    records[keys[1]] = replace(records[keys[1]], origin="shared_computed_offsets")
    records["unrelated"] = replace(records[keys[0]], origin="preexisting_manual_override")
    candidate = prepare_reusable_source_set(alignment_case, dict(reversed(list(records.items()))))
    assert candidate is not None
    assert tuple(item.result for item in candidate.resolutions) == ordered_results(
        alignment_case, records
    )
    assert len(candidate.resolutions) == 2


def test_prepared_candidate_cannot_be_published_for_different_request(
    alignment_case: AlignmentRequest,
) -> None:
    candidate = prepare_reusable_source_set(alignment_case, _resolutions(alignment_case))
    assert candidate is not None
    changed = replace(
        alignment_case, settings=replace(alignment_case.settings, max_offset_seconds=20.0)
    )
    with pytest.raises(ValueError, match="different source set"):
        save_reusable_offsets(changed, candidate)
    assert not (alignment_case.shared_alignment_cache_dir / "alignment_reuse.toml").exists()
