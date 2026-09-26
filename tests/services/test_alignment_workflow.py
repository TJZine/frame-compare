"""Service-path tests for the whole-track audio workflow.

FFmpeg recipes are stubbed with synthetic float32 writers at the recipe
boundary; transport, correlation, decision, attempt construction and result
provenance all run for real.
"""

from __future__ import annotations

import asyncio
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from frame_compare.services import alignment, alignment_audio, alignment_streaming
from frame_compare.services.alignment import _estimate_audio_pair
from frame_compare.services.alignment import (
    align_clips_from_request as _align_clips_from_request,
)
from frame_compare.services.alignment_audio import (
    AudioStreamInfo,
    AudioStreamSelection,
    AudioStreamTimeline,
    VideoStreamStart,
)
from frame_compare.services.alignment_manual_overrides import ManualOverride, save_manual_override
from frame_compare.services.alignment_streaming import (
    CollectionCleanup,
    CollectionFacts,
    PairedAudioCollectionFailure,
)
from frame_compare.services.errors import (
    AudioAlignmentCancellationError,
    AudioAlignmentCleanupError,
)
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.alignment_evidence import MAX_AUDIO_CHUNKS
from tests.services.alignment_request_test_support import alignment_request
from tests.services.alignment_synthetic_audio import (
    insert_program,
    make_program,
    quiet_program,
    shift_signal,
)

SEED = 11
FPS = Fraction(24, 1)
_DURATION_SECONDS = 35.0
_DURATION_SAMPLES = int(_DURATION_SECONDS * 8000)


def run_request(*args: object, **kwargs: object) -> list[AlignmentResult]:
    return asyncio.run(_align_clips_from_request(*args, **kwargs))  # type: ignore[arg-type]


def _payload(values: np.ndarray) -> bytes:
    return np.ascontiguousarray(values, dtype="<f4").tobytes()


def _writer_argv(pcm_path: Path) -> list[str]:
    return [
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(open(sys.argv[1], 'rb').read())",
        str(pcm_path),
    ]


def _selection(*, duration_seconds: float = _DURATION_SECONDS) -> AudioStreamSelection:
    return AudioStreamSelection(
        stream=AudioStreamInfo(
            audio_stream_index=0,
            absolute_stream_index=1,
            codec_name="pcm",
            channels=1,
            channel_layout="mono",
            sample_rate=8000,
            language=None,
            is_default=True,
            is_original=False,
            is_commentary=False,
            timeline=AudioStreamTimeline(
                start_time=Fraction(0),
                duration=Fraction(duration_seconds),
                time_base=Fraction(1, 8000),
                duration_basis="stream_duration",
            ),
        ),
        video_start=VideoStreamStart(start_time=Fraction(0), basis="default_zero"),
    )


def _stub_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    reference_samples: np.ndarray,
    comparison_samples: np.ndarray,
) -> None:
    reference_pcm = tmp_path / "reference.f32"
    comparison_pcm = tmp_path / "comparison.f32"
    reference_pcm.write_bytes(_payload(reference_samples))
    comparison_pcm.write_bytes(_payload(comparison_samples))
    monkeypatch.setattr(
        alignment_audio,
        "select_reference_audio_stream",
        lambda *args, **kwargs: _selection(),
    )
    monkeypatch.setattr(
        alignment_audio,
        "select_matching_audio_stream",
        lambda *args, **kwargs: _selection(),
    )

    def argv(path: Path, stream: object, *, channel_strategy: str) -> list[str]:
        pcm = reference_pcm if Path(path).stem == "reference" else comparison_pcm
        return _writer_argv(pcm)

    monkeypatch.setattr(alignment_audio, "collection_argv", argv)


def _media(tmp_path: Path) -> tuple[Path, Path]:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.write_bytes(b"reference")
    comparison.write_bytes(b"comparison")
    return reference, comparison


def _config(**overrides: Any) -> AlignmentConfig:
    return AlignmentConfig(cache_results=False, **overrides)


def _align(
    reference: Path,
    comparison: Path,
    config: AlignmentConfig,
    tmp_path: Path,
) -> list[AlignmentResult]:
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path / "generated",
        fps_num=FPS.numerator,
        fps_den=FPS.denominator,
    )
    return run_request(request, config, reference_fps=FPS)


def test_agreed_pair_is_provisional_pending_video_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)
    config = _config()

    (result,) = _align(reference, comparison, config, tmp_path)

    assert result.applied is False
    assert result.frame_offset is None
    assert result.time_offset_seconds is None
    assert result.source == "computed"
    assert result.algorithm == "cross_correlation"
    assert result.diagnostic == "video_check_pending"
    assert result.correlation_score == pytest.approx(1.0)
    assert result.stability is not None
    assert result.stability.classification == "stable"
    attempt = result.audio_attempt
    assert attempt is not None
    assert attempt.status == "complete"
    assert attempt.comparison_ordinal == 1
    assert attempt.estimator_policy == "whole-track-chunked-phat-video-check-20260925"
    assert attempt.diagnostic_policy == "retained-audio-evidence-v1"
    assert (attempt.fps_num, attempt.fps_den) == (FPS.numerator, FPS.denominator)
    assert [s.role for s in attempt.selected_streams] == ["reference", "comparison"]
    assert attempt.analysis.planned_chunk_count == len(attempt.chunks.starts) > 0
    assert len(attempt.runs) == 1
    assert attempt.audio.status == "agreed"
    assert attempt.audio.global_lag == 0
    assert attempt.audio.compensation_seconds == pytest.approx(0.0)
    assert attempt.audio.subframe_estimate == pytest.approx(0.0)
    assert attempt.audio.rounded_frame == 0
    assert attempt.collection_observation == "observed"
    assert [facts.role for facts in attempt.collection] == ["reference", "comparison"]
    assert all(facts.returncode == 0 for facts in attempt.collection)
    assert all(facts.cleanup_completed for facts in attempt.collection)
    assert attempt.video_check.observation == "not_observed"
    assert attempt.video_check.scored_offsets == ()
    decision = attempt.decision
    assert decision.state == "provisional"
    assert decision.primary_reason == "video_check_pending"
    assert decision.candidate is not None
    assert decision.candidate.frame_offset == 0
    assert decision.candidate.basis == "audio_only"


def test_shifted_pair_candidate_matches_frame_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, _DURATION_SECONDS)
    shift = 1600  # 0.2 s at 8 kHz -> -4.8 frames at 24 fps
    _stub_transport(
        monkeypatch,
        tmp_path,
        reference_samples=program,
        comparison_samples=shift_signal(program, shift),
    )

    (result,) = _align(reference, comparison, _config(), tmp_path)

    assert result.applied is False
    candidate = result.audio_attempt.decision.candidate if result.audio_attempt else None
    assert candidate is not None
    assert candidate.time_offset_seconds == pytest.approx(-shift / 8000)
    assert candidate.subframe_estimate == pytest.approx(-shift / 8000 * float(FPS))
    assert candidate.frame_offset == -5


def test_insert_gives_no_single_offset_with_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, 70.0)
    _stub_transport(
        monkeypatch,
        tmp_path,
        reference_samples=program,
        comparison_samples=insert_program(SEED, 70.0, 999),
    )
    monkeypatch.setattr(
        alignment_audio,
        "select_reference_audio_stream",
        lambda *args, **kwargs: _selection(duration_seconds=70.0),
    )
    monkeypatch.setattr(
        alignment_audio,
        "select_matching_audio_stream",
        lambda *args, **kwargs: _selection(duration_seconds=74.0),
    )

    (result,) = _align(reference, comparison, _config(), tmp_path)

    assert result.applied is False
    assert result.frame_offset is None
    assert result.diagnostic == "no_single_offset"
    attempt = result.audio_attempt
    assert attempt is not None
    assert attempt.audio.status == "no_single_offset"
    assert len(attempt.runs) >= 2
    assert attempt.decision.state == "unavailable"
    assert attempt.decision.candidate is None


def test_silence_gives_no_usable_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference, comparison = _media(tmp_path)
    program = quiet_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)

    (result,) = _align(reference, comparison, _config(), tmp_path)

    assert result.applied is False
    assert result.diagnostic == "no_usable_audio"
    assert result.correlation_score == 0.0
    assert result.audio_attempt is not None
    assert result.audio_attempt.audio.status == "no_usable_audio"
    assert result.audio_attempt.audio.global_lag is None


def test_unknown_duration_rejected_before_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    selection = _selection()
    unknown = AudioStreamSelection(
        stream=AudioStreamInfo(
            audio_stream_index=selection.stream.audio_stream_index,
            absolute_stream_index=selection.stream.absolute_stream_index,
            codec_name=selection.stream.codec_name,
            channels=selection.stream.channels,
            channel_layout=selection.stream.channel_layout,
            sample_rate=selection.stream.sample_rate,
            language=selection.stream.language,
            is_default=selection.stream.is_default,
            is_original=selection.stream.is_original,
            is_commentary=selection.stream.is_commentary,
            timeline=AudioStreamTimeline(
                start_time=Fraction(0),
                duration=None,
                time_base=None,
                duration_basis="unavailable",
            ),
        ),
        video_start=selection.video_start,
    )
    monkeypatch.setattr(
        alignment_audio, "select_reference_audio_stream", lambda *a, **k: _selection()
    )
    monkeypatch.setattr(alignment_audio, "select_matching_audio_stream", lambda *a, **k: unknown)

    def exploding_collect(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("decode must not run without durations")

    monkeypatch.setattr(alignment, "collect_paired_audio_chunks", exploding_collect)

    (result,) = _align(reference, comparison, _config(), tmp_path)

    assert result.applied is False
    assert result.diagnostic == "selected_audio_timeline_unavailable"
    assert result.audio_attempt is not None
    assert result.audio_attempt.status == "preanalysis_rejection"
    assert result.audio_attempt.collection_observation == "not_observed"


def test_budget_exceeded_rejected_before_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)
    monkeypatch.setattr(
        alignment,
        "collect_paired_audio_chunks",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("decode must not run")),
    )

    (result,) = _align(reference, comparison, _config(max_offset_seconds=3600.0), tmp_path)

    assert result.applied is False
    assert result.diagnostic == "analysis_budget_exceeded"
    assert result.audio_attempt is not None
    assert result.audio_attempt.status == "preanalysis_rejection"


def test_long_reference_short_comparison_budget_rejects_before_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)
    reference_duration = (MAX_AUDIO_CHUNKS + 1) * 5
    monkeypatch.setattr(
        alignment_audio,
        "select_reference_audio_stream",
        lambda *args, **kwargs: _selection(duration_seconds=reference_duration),
    )
    monkeypatch.setattr(
        alignment_audio,
        "select_matching_audio_stream",
        lambda *args, **kwargs: _selection(duration_seconds=10.0),
    )
    decode_calls: list[tuple[object, ...]] = []

    def fail_if_decode_runs(*args: object, **kwargs: object) -> Any:
        del kwargs
        decode_calls.append(args)
        raise AssertionError("decode must not run after the planning budget refusal")

    monkeypatch.setattr(alignment, "collect_paired_audio_chunks", fail_if_decode_runs)

    (result,) = _align(reference, comparison, _config(), tmp_path)

    assert result.applied is False
    assert result.diagnostic == "analysis_budget_exceeded"
    assert result.audio_attempt is not None
    assert result.audio_attempt.status == "preanalysis_rejection"
    assert decode_calls == []


def _failure_facts() -> tuple[CollectionFacts, CollectionFacts]:
    def facts(role: str) -> CollectionFacts:
        return CollectionFacts(
            planned_end_sample=100,
            emitted_sample_count=10,
            emitted_byte_count=40,
            retained_sample_count=10,
            stderr_byte_count=8,
            stderr_retained=b"oops",
            stderr_truncated=False,
            elapsed_seconds=0.5,
            returncode=1 if role == "reference" else None,
        )

    return facts("reference"), facts("comparison")


def _cleanup(*, completed: bool = True) -> CollectionCleanup:
    return CollectionCleanup(
        process_exited=True,
        stdout_reader_joined=True,
        stderr_reader_joined=True,
        stdout_pipe_closed=True,
        stderr_pipe_closed=True,
        termination_requested=True,
        kill_requested=False,
        failure=None if completed else "injected leftover reader",
    )


def test_collection_failure_is_aborted_with_category(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    monkeypatch.setattr(
        alignment_audio, "select_reference_audio_stream", lambda *a, **k: _selection()
    )
    monkeypatch.setattr(
        alignment_audio, "select_matching_audio_stream", lambda *a, **k: _selection()
    )
    reference_facts, comparison_facts = _failure_facts()
    failure = PairedAudioCollectionFailure(
        category="timeout",
        side=None,
        message="paired audio collection exceeded its total timeout",
        reference_facts=reference_facts,
        comparison_facts=comparison_facts,
        reference_cleanup=_cleanup(),
        comparison_cleanup=_cleanup(),
    )
    monkeypatch.setattr(alignment, "collect_paired_audio_chunks", lambda *a, **k: failure)

    (result,) = _align(reference, comparison, _config(), tmp_path)

    assert result.applied is False
    assert result.diagnostic == "timeout"
    attempt = result.audio_attempt
    assert attempt is not None
    assert attempt.status == "aborted"
    assert attempt.decision.state == "unavailable"
    assert attempt.decision.primary_reason == "timeout"
    assert attempt.chunks.starts == ()
    assert attempt.collection_observation == "observed"
    assert attempt.collection_failure is not None
    assert attempt.collection_failure.category == "timeout"
    assert attempt.collection_failure.side is None
    assert attempt.collection[0].emitted_samples == 10
    assert attempt.audio.compensation_seconds is not None


def test_cleanup_failure_is_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference, comparison = _media(tmp_path)
    monkeypatch.setattr(
        alignment_audio, "select_reference_audio_stream", lambda *a, **k: _selection()
    )
    monkeypatch.setattr(
        alignment_audio, "select_matching_audio_stream", lambda *a, **k: _selection()
    )
    reference_facts, comparison_facts = _failure_facts()
    failure = PairedAudioCollectionFailure(
        category="timeout",
        side=None,
        message="timeout with broken cleanup",
        reference_facts=reference_facts,
        comparison_facts=comparison_facts,
        reference_cleanup=_cleanup(completed=False),
        comparison_cleanup=_cleanup(),
    )
    monkeypatch.setattr(alignment, "collect_paired_audio_chunks", lambda *a, **k: failure)

    with pytest.raises(AudioAlignmentCleanupError):
        _align(reference, comparison, _config(), tmp_path)


def test_identity_change_mid_collection_is_aborted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)
    real_collect = alignment_streaming.collect_paired_audio_chunks

    def touching_collect(*args: Any, **kwargs: Any) -> Any:
        with open(comparison, "ab") as handle:
            handle.write(b"mutated")
        return real_collect(*args, **kwargs)

    monkeypatch.setattr(alignment, "collect_paired_audio_chunks", touching_collect)

    (result,) = _align(reference, comparison, _config(), tmp_path)

    assert result.applied is False
    assert result.diagnostic == "source_identity_changed"
    assert result.audio_attempt is not None
    assert result.audio_attempt.status == "aborted"


def test_pre_collection_identity_change_is_aborted_per_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = tmp_path / "reference.mkv"
    ok = tmp_path / "ok.mkv"
    mutated = tmp_path / "mutated.mkv"
    manual = tmp_path / "manual.mkv"
    for path in (reference, ok, mutated, manual):
        path.write_bytes(b"media-" + path.stem.encode())
    program = make_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)

    def mutating_select(path: Path, *args: Any, **kwargs: Any) -> AudioStreamSelection:
        if Path(path) == mutated:
            with open(mutated, "ab") as handle:
                handle.write(b"mutated")
        return _selection()

    monkeypatch.setattr(alignment_audio, "select_matching_audio_stream", mutating_select)
    generated = tmp_path / "generated"
    generated.mkdir(parents=True)
    save_manual_override(
        generated,
        ManualOverride(
            reference_clip=reference.stem,
            comparison_clip=manual.stem,
            frame_offset=3,
            timestamp="2026-09-25T00:00:00Z",
            confirmed=True,
        ),
    )
    config = _config()
    request = alignment_request(
        reference=reference,
        comparisons=[ok, mutated, manual],
        config=config,
        generated_dir=generated,
        fps_num=FPS.numerator,
        fps_den=FPS.denominator,
    )
    results = run_request(request, config, reference_fps=FPS)
    by_name = {result.comparison_clip: result for result in results}

    changed = by_name[mutated.name]
    assert changed.applied is False
    assert changed.diagnostic == "source_identity_changed"
    assert changed.audio_attempt is not None
    assert changed.audio_attempt.status == "aborted"
    assert changed.audio_attempt.collection_observation == "not_observed"
    assert changed.audio_attempt.collection == ()
    assert changed.audio_attempt.decision.state == "unavailable"
    assert changed.audio_attempt.decision.primary_reason == "source_identity_changed"

    untouched = by_name[ok.name]
    assert untouched.applied is False
    assert untouched.diagnostic == "video_check_pending"
    assert untouched.audio_attempt is not None
    assert untouched.audio_attempt.status == "complete"

    overridden = by_name[manual.name]
    assert overridden.applied is True
    assert overridden.source == "manual"
    assert overridden.frame_offset == 3


def test_no_computed_cache_write_in_u3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)
    generated = tmp_path / "generated"
    config = AlignmentConfig(cache_results=True)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=generated,
        shared_alignment_cache_dir=generated / "shared",
        fps_num=FPS.numerator,
        fps_den=FPS.denominator,
    )
    (result,) = run_request(request, config, reference_fps=FPS)

    assert result.applied is False
    assert not (generated / "shared" / "alignment_reuse.toml").exists()


def test_manual_override_wins_without_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    generated = tmp_path / "generated"
    generated.mkdir(parents=True)
    save_manual_override(
        generated,
        ManualOverride(
            reference_clip=reference.stem,
            comparison_clip=comparison.stem,
            frame_offset=3,
            timestamp="2026-09-25T00:00:00Z",
            confirmed=True,
        ),
    )
    monkeypatch.setattr(
        alignment,
        "collect_paired_audio_chunks",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("manual wins; no decode")),
    )
    config = _config()

    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=generated,
        fps_num=FPS.numerator,
        fps_den=FPS.denominator,
    )
    (result,) = run_request(request, config, reference_fps=FPS)

    assert result.applied is True
    assert result.source == "manual"
    assert result.frame_offset == 3
    assert result.time_offset_seconds == pytest.approx(3 / float(FPS))


def test_entry_identity_mismatch_has_no_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)
    config = _config()
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path / "generated",
        fps_num=FPS.numerator,
        fps_den=FPS.denominator,
    )
    comparison.write_bytes(b"comparison-mutated")

    (result,) = run_request(request, config, reference_fps=FPS)

    assert result.applied is False
    assert result.diagnostic == "source_identity_changed"
    assert result.audio_attempt is None


def test_cancelled_collection_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(SEED, _DURATION_SECONDS)
    _stub_transport(monkeypatch, tmp_path, reference_samples=program, comparison_samples=program)
    reference_facts, comparison_facts = _failure_facts()
    failure = PairedAudioCollectionFailure(
        category="cancelled",
        side=None,
        message="paired audio collection was cancelled",
        reference_facts=reference_facts,
        comparison_facts=comparison_facts,
        reference_cleanup=_cleanup(),
        comparison_cleanup=_cleanup(),
    )
    monkeypatch.setattr(alignment, "collect_paired_audio_chunks", lambda *a, **k: failure)
    config = _config()
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path / "generated",
        fps_num=FPS.numerator,
        fps_den=FPS.denominator,
    )

    with pytest.raises(AudioAlignmentCancellationError):
        _estimate_audio_pair(
            reference,
            comparison,
            config=config,
            fps_reference=FPS,
            reference_request=request.reference,
            comparison_request=request.comparisons[0],
        )
