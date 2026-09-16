"""Production service proof for staged continuous audio alignment."""

from __future__ import annotations

import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from frame_compare.services import alignment_audio
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_streaming import ContinuousAudioCollection
from frame_compare.services.types import AlignmentConfig
from tests.integration.alignment_oracle import (
    continuous_decode,
    deterministic_signal,
    mux_audio,
    write_pcm_wave,
)
from tests.services.alignment_request_test_support import alignment_request


def _audio_only_fixture(path: Path, wave_path: Path) -> None:
    subprocess.run(  # noqa: S603 - fixed integration fixture executable
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(wave_path),
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
        timeout=30,
    )


@pytest.mark.integration
@pytest.mark.parametrize("sample_rate", [4000, 8000])
def test_real_service_collects_distributed_windows_from_one_decode_per_source(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
    sample_rate: int,
) -> None:
    duration_seconds = 95
    signal = deterministic_signal(
        seed=9301,
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
    )
    reference_wave = tmp_path / "reference.wav"
    comparison_wave = tmp_path / "comparison.wav"
    reference = tmp_path / "reference.mka"
    comparison = tmp_path / "comparison.mka"
    write_pcm_wave(reference_wave, signal, sample_rate=sample_rate)
    write_pcm_wave(comparison_wave, signal, sample_rate=sample_rate)
    _audio_only_fixture(reference, reference_wave)
    _audio_only_fixture(comparison, comparison_wave)

    real_collect = alignment_audio.collect_continuous_audio
    production_decodes: list[tuple[Path, int]] = []

    def collect_and_compare(*args: object, **kwargs: object):
        argv = list(args[0])
        intervals = tuple(args[1])
        media_path = Path(argv[argv.index("-i") + 1])
        result = real_collect(*args, **kwargs)
        assert isinstance(result, ContinuousAudioCollection)
        production_decodes.append((media_path, result.facts.planned_end_sample))
        stream = alignment_audio.select_reference_audio_stream(media_path)
        with continuous_decode(
            media_path,
            stream,
            sample_rate=sample_rate,
            channel_strategy="mono_downmix",
        ) as oracle:
            for interval, retained in zip(intervals, result.intervals, strict=True):
                expected = np.asarray(oracle[interval.start_sample : interval.end_sample])
                assert np.array_equal(retained.samples, expected)
        return result

    monkeypatch.setattr(alignment_audio, "collect_continuous_audio", collect_and_compare)
    config = AlignmentConfig(
        sample_rate=sample_rate,
        max_offset_seconds=30,
        cache_results=False,
    )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )

    result = align_clips_from_request(
        request,
        config,
        reference_fps=Fraction(24),
    )[0]

    assert len(production_decodes) == 2
    assert [path for path, _ in production_decodes] == [reference, comparison]
    assert result.applied is False
    assert result.frame_offset is None
    assert result.audio_attempt is not None
    attempt = result.audio_attempt
    assert attempt.estimator_policy == "continuous-origin-distributed-2097152-v7-held"
    assert attempt.collection_observation == "observed"
    assert len(attempt.collection_summaries) == 2
    assert attempt.planned_window_count == 5
    assert all(window.planned_reference_count == 30 * sample_rate for window in attempt.windows)
    assert all(window.continuous_sample_count_origin == "discovery" for window in attempt.windows)
    assert all(window.actual_coverage == pytest.approx(1.0) for window in attempt.windows)
    assert attempt.decision.candidate is not None
    assert attempt.decision.candidate.sample_offset == 0


@pytest.mark.integration
def test_noninteger_rate_verification_uses_exactly_four_production_decodes(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_rate = 44100
    requested_rate = 48000
    signal = deterministic_signal(seed=9302, sample_rate=input_rate, duration_seconds=4)
    reference_wave = tmp_path / "reference-44100.wav"
    comparison_wave = tmp_path / "comparison-44100.wav"
    reference = tmp_path / "reference-44100.mka"
    comparison = tmp_path / "comparison-44100.mka"
    write_pcm_wave(reference_wave, signal, sample_rate=input_rate)
    write_pcm_wave(comparison_wave, signal, sample_rate=input_rate)
    _audio_only_fixture(reference, reference_wave)
    _audio_only_fixture(comparison, comparison_wave)

    real_collect = alignment_audio.collect_continuous_audio
    production_rates: list[int] = []

    def count_collects(*args: object, **kwargs: object):
        argv = list(args[0])
        audio_filter = argv[argv.index("-af") + 1]
        production_rates.append(int(audio_filter.split("aresample=")[1].split(",")[0]))
        return real_collect(*args, **kwargs)

    monkeypatch.setattr(alignment_audio, "collect_continuous_audio", count_collects)
    config = AlignmentConfig(
        sample_rate=requested_rate,
        max_offset_seconds=1,
        window_length_seconds=1,
        window_stride_seconds=1,
        cache_results=False,
    )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert production_rates == [8000, 8000, 48000, 48000]
    assert result.audio_attempt is not None
    assert len(result.audio_attempt.collection_summaries) == 4
    assert result.audio_attempt.decision.candidate is not None
    assert result.audio_attempt.decision.candidate.sample_offset == 0
    assert all(
        window.continuous_sample_count_origin == "verification"
        for window in result.audio_attempt.windows
    )


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.integration
def test_real_service_recovers_both_signed_offsets(
    tmp_path: Path,
    require_ffmpeg: None,
    sign: int,
) -> None:
    sample_rate = 8000
    delay = sample_rate // 4
    source = deterministic_signal(seed=9303, sample_rate=sample_rate, duration_seconds=4)
    delayed = np.concatenate((np.zeros(delay, dtype=np.float32), source[:-delay]))
    reference_signal, comparison_signal = (delayed, source) if sign > 0 else (source, delayed)
    reference_wave = tmp_path / f"reference-{sign}.wav"
    comparison_wave = tmp_path / f"comparison-{sign}.wav"
    reference = tmp_path / f"reference-{sign}.mka"
    comparison = tmp_path / f"comparison-{sign}.mka"
    write_pcm_wave(reference_wave, reference_signal, sample_rate=sample_rate)
    write_pcm_wave(comparison_wave, comparison_signal, sample_rate=sample_rate)
    _audio_only_fixture(reference, reference_wave)
    _audio_only_fixture(comparison, comparison_wave)
    config = AlignmentConfig(sample_rate=sample_rate, max_offset_seconds=1, cache_results=False)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert result.audio_attempt is not None
    assert result.audio_attempt.decision.candidate is not None
    assert result.audio_attempt.decision.candidate.sample_offset == sign * delay


@pytest.mark.parametrize("reference_start", [-2, 2])
@pytest.mark.integration
def test_real_service_uses_sample_ordinals_for_asymmetric_stream_starts(
    tmp_path: Path,
    require_ffmpeg: None,
    reference_start: int,
) -> None:
    sample_rate = 8000
    source = deterministic_signal(seed=9304, sample_rate=sample_rate, duration_seconds=4)
    wave = tmp_path / f"source-{reference_start}.wav"
    reference = tmp_path / f"reference-start-{reference_start}.mkv"
    comparison = tmp_path / f"comparison-start-{reference_start}.mkv"
    write_pcm_wave(wave, source, sample_rate=sample_rate)
    mux_audio(
        reference,
        wave,
        source_rate=sample_rate,
        codec="pcm",
        start_seconds=reference_start,
        duration_seconds=4,
    )
    mux_audio(
        comparison,
        wave,
        source_rate=sample_rate,
        codec="pcm",
        duration_seconds=4,
    )
    config = AlignmentConfig(sample_rate=sample_rate, max_offset_seconds=1, cache_results=False)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert result.audio_attempt is not None
    assert result.audio_attempt.selected_streams[0].stream_start_num == reference_start
    assert result.audio_attempt.decision.candidate is not None
    assert result.audio_attempt.decision.candidate.sample_offset == 0
