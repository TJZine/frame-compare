"""Production-service coverage for held corresponding-channel corroboration."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from frame_compare.services import alignment_audio, alignment_consensus
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.types import AlignmentConfig, AudioAlignmentCollectionRecord
from tests.services.alignment_request_test_support import alignment_request


def _stream(*, layout: str = "5.1") -> alignment_audio.AudioStreamInfo:
    return alignment_audio.AudioStreamInfo(
        audio_stream_index=0,
        absolute_stream_index=0,
        codec_name="pcm_f32le",
        channels=6,
        channel_layout=layout,
        sample_rate=8_000,
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        timeline=alignment_audio.AudioStreamTimeline(
            start_time=Fraction(0),
            duration=Fraction(95),
            time_base=Fraction(1, 8_000),
            duration_basis="stream_duration",
        ),
    )


def _summary(
    role: str,
    windows: tuple[alignment_audio.AudioWindow, ...],
    *,
    phase: str,
) -> AudioAlignmentCollectionRecord:
    horizon = max(
        (
            window.reference_start_sample + window.reference.size
            if role == "reference"
            else window.comparison_start_sample + window.comparison.size
        )
        for window in windows
    )
    retained = sum(
        window.reference.size if role == "reference" else window.comparison.size
        for window in windows
    )
    return AudioAlignmentCollectionRecord(
        phase=phase,  # type: ignore[arg-type]
        role=role,  # type: ignore[arg-type]
        output_rate=8_000,
        requested_horizon=horizon,
        emitted_sample_count=horizon,
        emitted_byte_count=horizon * 4,
        retained_sample_count=retained,
        retained_byte_count=retained * 4,
        status="complete",
        end_category="planned_end_reached",
        observed_eof_sample=None,
        elapsed_seconds=0.01,
        cleanup_failure_count=0,
        failure_count=0,
    )


def _phase(
    specs: tuple[alignment_audio.AudioWindowSpec, ...],
    reference_source: np.ndarray,
    comparison_source: np.ndarray,
    *,
    offset: int,
    phase: str,
) -> alignment_audio.CollectedAudioPhase:
    windows = tuple(
        alignment_audio.AudioWindow(
            reference=reference_source[
                spec.reference_start_sample : spec.reference_start_sample
                + spec.reference_sample_count
            ],
            comparison=comparison_source[
                spec.comparison_start_sample + offset : spec.comparison_start_sample
                + offset
                + spec.comparison_sample_count
            ],
            reference_start_sample=spec.reference_start_sample,
            comparison_start_sample=spec.comparison_start_sample,
        )
        for spec in specs
    )
    return alignment_audio.CollectedAudioPhase(
        windows=windows,
        summaries=(
            _summary("reference", windows, phase=phase),
            _summary("comparison", windows, phase=phase),
        ),
    )


def _offset_timeline(signal: np.ndarray, offset: int) -> np.ndarray:
    shifted = np.zeros_like(signal)
    if offset > 0:
        shifted[:-offset] = signal[offset:]
    elif offset < 0:
        shifted[-offset:] = signal[:offset]
    else:
        shifted[:] = signal
    return shifted


@pytest.mark.parametrize(
    (
        "mono_strength",
        "channel_strategy",
        "expected_decodes",
        "expected_channel",
        "expected_reason",
        "view_case",
        "expected_status",
        "offset",
        "expected_frame",
    ),
    [
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "positive",
            "corroborated",
            0,
            0,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "mixed_support_strict",
            "corroborated",
            0,
            0,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "mixed_support_latch_disabled",
            "corroborated",
            0,
            0,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "mixed_support",
            "corroborated",
            0,
            0,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "mixed_support",
            "corroborated",
            400,
            1,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "mixed_support",
            "corroborated",
            -400,
            -1,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "latch_disabled",
            "corroborated",
            0,
            0,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "positive",
            "corroborated",
            400,
            1,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "positive",
            "corroborated",
            -400,
            -1,
        ),
        (0.55, "mono_downmix", 8, True, "no_voting_windows", "unrelated", "rejected", 0, None),
        (0.55, "mono_downmix", 8, True, "no_voting_windows", "silence", "rejected", 0, None),
        (0.55, "mono_downmix", 8, True, "no_voting_windows", "repeated", "rejected", 0, None),
        (0.55, "mono_downmix", 8, True, "no_voting_windows", "permuted", "rejected", 0, None),
        (0.55, "mono_downmix", 8, True, "no_voting_windows", "conflicting", "rejected", 0, None),
        (0.55, "mono_downmix", 8, True, "no_voting_windows", "localized", "rejected", 0, None),
        (0.55, "mono_downmix", 8, True, "no_voting_windows", "one_window", "rejected", 0, None),
        (0.55, "mono_downmix", 8, True, "no_voting_windows", "two_windows", "rejected", 0, None),
        (
            0.55,
            "mono_downmix",
            2,
            False,
            "no_unique_candidate",
            "mixed_mono_conflict",
            None,
            0,
            None,
        ),
        (
            0.55,
            "mono_downmix",
            8,
            True,
            "channel_corroboration_provisional",
            "strict_user_thresholds",
            "corroborated",
            0,
            0,
        ),
        (1.0, "mono_downmix", 2, False, "accepted", "positive", None, 0, 0),
        (0.55, "best_channel", 2, False, "no_voting_windows", "positive", None, 0, None),
    ],
)
def test_channel_corroboration_is_provisional_only_and_mono_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mono_strength: float,
    channel_strategy: str,
    expected_decodes: int,
    expected_channel: bool,
    expected_reason: str,
    view_case: str,
    expected_status: str | None,
    offset: int,
    expected_frame: int | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference = tmp_path / "reference.mka"
    comparison = tmp_path / "comparison.mka"
    reference.touch()
    comparison.touch()
    config = AlignmentConfig(
        sample_rate=8_000,
        max_offset_seconds=1,
        channel_strategy=channel_strategy,  # type: ignore[arg-type]
        window_length_seconds=2,
        window_stride_seconds=24,
        minimum_valid_windows=3,
        confidence_threshold=1.0 if "strict" in view_case else 0.0,
        ambiguity_peak_ratio=100.0 if "strict" in view_case else 1.0,
        cache_results="latch_disabled" in view_case,
    )
    stream = _stream()
    plan = alignment_audio.plan_audio_analysis(stream, stream, config=config)
    assert isinstance(plan, alignment_audio.AudioAnalysisPlan)
    assert len(plan.windows) >= 5
    sample_count = 96 * config.sample_rate
    rng = np.random.default_rng(6020)
    sources = {
        view: rng.standard_normal(sample_count).astype(np.float32) for view in ("FL", "FR", "FC")
    }
    noise = rng.standard_normal(sample_count).astype(np.float32)
    mono_reference = sources["FL"]
    mono_comparison_unshifted = (
        mono_strength * mono_reference + np.sqrt(max(0.0, 1.0 - mono_strength**2)) * noise
    ).astype(np.float32)
    if view_case.startswith("mixed_support"):
        for spec in plan.windows[:2]:
            start = spec.reference_start_sample
            end = start + spec.reference_sample_count
            mono_comparison_unshifted[start:end] = mono_reference[start:end]
    elif view_case == "mixed_mono_conflict":
        first, second = plan.windows[:2]
        first_end = first.reference_start_sample + first.reference_sample_count
        mono_comparison_unshifted[first.reference_start_sample : first_end] = mono_reference[
            first.reference_start_sample : first_end
        ]
        second_end = second.reference_start_sample + second.reference_sample_count
        mono_comparison_unshifted[second.reference_start_sample : second_end] = mono_reference[
            second.reference_start_sample + 400 : second_end + 400
        ]
    mono_comparison = _offset_timeline(
        mono_comparison_unshifted,
        offset,
    )
    comparison_views = dict(sources)
    if view_case == "unrelated":
        comparison_views = {
            view: rng.standard_normal(sample_count).astype(np.float32) for view in sources
        }
    elif view_case == "silence":
        comparison_views = {view: np.zeros(sample_count, dtype=np.float32) for view in sources}
    elif view_case == "repeated":
        repeated = np.sin(2 * np.pi * 100 * np.arange(sample_count) / 8000).astype(np.float32)
        sources = dict.fromkeys(sources, repeated)
        comparison_views = dict(sources)
    elif view_case == "permuted":
        comparison_views = {
            "FL": sources["FR"],
            "FR": sources["FC"],
            "FC": sources["FL"],
        }
    elif view_case == "conflicting":
        comparison_views["FR"] = _offset_timeline(comparison_views["FR"], 400)
        comparison_views["FC"] = _offset_timeline(comparison_views["FC"], -400)
    elif view_case == "localized":
        comparison_views = {
            view: (0.55 * source + np.sqrt(1 - 0.55**2) * noise).astype(np.float32)
            for view, source in sources.items()
        }
    elif view_case in {"one_window", "two_windows"}:
        comparison_views = {
            view: rng.standard_normal(sample_count).astype(np.float32) for view in sources
        }
        window_count = 1 if view_case == "one_window" else 2
        for spec in plan.windows[:window_count]:
            for view, source in sources.items():
                comparison_views[view][
                    spec.reference_start_sample : spec.reference_start_sample
                    + spec.reference_sample_count
                ] = source[
                    spec.reference_start_sample : spec.reference_start_sample
                    + spec.reference_sample_count
                ]
    comparison_views = {
        view: _offset_timeline(source, offset) for view, source in comparison_views.items()
    }
    decode_count = 0

    monkeypatch.setattr(alignment_audio, "select_reference_audio_stream", lambda *_a, **_k: stream)
    monkeypatch.setattr(alignment_audio, "select_matching_audio_stream", lambda *_a, **_k: stream)
    monkeypatch.setattr(alignment_audio, "plan_audio_analysis", lambda *_a, **_k: plan)

    def discovery(*_args: object, **_kwargs: object) -> alignment_audio.CollectedAudioPhase:
        nonlocal decode_count
        decode_count += 2
        return _phase(
            plan.windows,
            mono_reference,
            mono_comparison,
            offset=0,
            phase="discovery",
        )

    def channel(
        _reference: Path,
        _comparison: Path,
        _reference_stream: alignment_audio.AudioStreamInfo,
        _comparison_stream: alignment_audio.AudioStreamInfo,
        channel_plan: alignment_audio.AudioChannelViewPlan,
        view: str,
        **_kwargs: object,
    ) -> alignment_audio.CollectedAudioPhase:
        nonlocal decode_count
        decode_count += 2
        return _phase(
            channel_plan.windows,
            sources[view],
            comparison_views[view],
            offset=0,
            phase="verification",
        )

    monkeypatch.setattr(alignment_audio, "collect_discovery_phase", discovery)
    monkeypatch.setattr(alignment_audio, "collect_channel_view_phase", channel)
    if "latch_disabled" in view_case:
        monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
        monkeypatch.setattr(
            "frame_compare.services.alignment.save_reusable_offsets",
            lambda *_args, **_kwargs: pytest.fail(
                "channel-only provisional evidence must not authorize a cache write"
            ),
        )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )

    result = asyncio.run(align_clips_from_request(request, config, reference_fps=Fraction(24)))
    presented = capsys.readouterr().err

    assert decode_count == expected_decodes
    if expected_reason == "accepted":
        assert result[0].applied is True
        assert result[0].frame_offset == expected_frame
        assert result[0].time_offset_seconds == pytest.approx(offset / config.sample_rate)
    else:
        assert result[0].applied is False
        assert result[0].frame_offset is None
        assert result[0].time_offset_seconds is None
    assert result[0].audio_attempt is not None
    attempt = result[0].audio_attempt
    assert (attempt.channel_corroboration is not None) is expected_channel
    if expected_channel:
        assert attempt.channel_corroboration is not None
        assert attempt.channel_corroboration.status == expected_status
        assert len(attempt.channel_corroboration.collections) == 6
        if expected_status == "corroborated":
            assert attempt.decision.state == "provisional", attempt.channel_corroboration
            assert attempt.decision.primary_reason == expected_reason
            assert attempt.decision.candidate is not None
            assert attempt.decision.candidate.frame_offset == expected_frame
            assert attempt.channel_corroboration.independent_windows == 3
            if view_case.startswith("mixed_support"):
                corroborated = [
                    window
                    for window in attempt.channel_corroboration.windows
                    if window.corroborated
                ]
                assert len(corroborated) == 3
                assert len(attempt.decision.candidate.supporting_window_ids) == 3
                mono_by_id = {window.logical_id: window for window in attempt.windows}
                channel_ids = {window.logical_id for window in corroborated}
                channel_records = [
                    replace(
                        mono_by_id[window.logical_id],
                        actual_useful_reference_start=window.actual_useful_reference_start,
                        actual_useful_reference_end=window.actual_useful_reference_end,
                    )
                    for window in corroborated
                ]
                _selected, channel_only_count = alignment_consensus._independent_support(
                    channel_records,
                    channel_ids,
                    config=config,
                    sample_rate=config.sample_rate,
                    reference_duration=95 * config.sample_rate,
                    comparison_duration=95 * config.sample_rate,
                    offsets={
                        window.logical_id: window.representative_sample_lag or 0
                        for window in corroborated
                    },
                )
                assert channel_only_count == 0
                mono_ids = {
                    window.logical_id
                    for window in attempt.windows
                    if window.review_qualified and window.actual_coverage == 1.0
                }
                assert mono_ids.isdisjoint(channel_ids)
                assert len(mono_ids | channel_ids) == 5
                assert expected_frame is not None
                assert (
                    alignment_consensus._combined_channel_independent_support(
                        attempt.windows,
                        [*corroborated, corroborated[0]],
                        winning_frame=expected_frame,
                        config=config,
                        reference_duration=95 * config.sample_rate,
                        comparison_duration=95 * config.sample_rate,
                    )
                    == 3
                )
                overlap_start = corroborated[0].actual_useful_reference_start
                overlap_end = corroborated[0].actual_useful_reference_end
                overlapping = [
                    replace(
                        window,
                        actual_useful_reference_start=overlap_start,
                        actual_useful_reference_end=overlap_end,
                    )
                    for window in corroborated
                ]
                assert (
                    alignment_consensus._combined_channel_independent_support(
                        attempt.windows,
                        overlapping,
                        winning_frame=expected_frame,
                        config=config,
                        reference_duration=95 * config.sample_rate,
                        comparison_duration=95 * config.sample_rate,
                    )
                    == 0
                )
            assert "Mono evidence:" in presented
            assert "Channel-view evidence:" in presented
            assert all(
                not window.views[0].contradiction
                for window in attempt.channel_corroboration.windows
            )
        else:
            assert attempt.channel_corroboration.candidate is None
            assert attempt.decision.primary_reason == expected_reason
            if view_case == "conflicting":
                assert attempt.channel_corroboration.reason == "credible_cross_frame_veto"
                assert all(
                    window.reason == "credible_cross_frame_veto"
                    for window in attempt.channel_corroboration.windows
                )
            if view_case in {"one_window", "two_windows"}:
                assert sum(
                    window.corroborated for window in attempt.channel_corroboration.windows
                ) == (1 if view_case == "one_window" else 2)
    else:
        assert attempt.decision.primary_reason == expected_reason
        if view_case == "mixed_mono_conflict":
            assert "credible_contradiction" in attempt.decision.failed_gates
