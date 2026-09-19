"""Real-FFmpeg regression proof for the production continuous collector."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from frame_compare.services.alignment_audio import select_reference_audio_stream
from frame_compare.services.alignment_streaming import (
    AudioSampleInterval,
    ContinuousAudioCollection,
    collect_continuous_audio,
)
from tests.integration.alignment_oracle import (
    continuous_decode,
    continuous_decode_argv,
    deterministic_signal,
    mux_audio,
    write_pcm_wave,
)


def _endpoint_limited_argv(argv: list[str], planned_end_sample: int) -> list[str]:
    limited = list(argv)
    filter_index = limited.index("-af") + 1
    limited[filter_index] = f"{limited[filter_index]},atrim=end_sample={planned_end_sample}"
    return limited


@pytest.mark.integration
@pytest.mark.parametrize("output_rate", [8000, 48000])
def test_positive_start_aac_matches_same_runtime_continuous_oracle(
    tmp_path: Path,
    require_ffmpeg: None,
    output_rate: int,
) -> None:
    wave_path = tmp_path / "positive-start.wav"
    media = tmp_path / "positive-start.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=7301, sample_rate=44100, duration_seconds=12),
        sample_rate=44100,
    )
    mux_audio(media, wave_path, source_rate=44100, codec="aac", start_seconds=2)
    stream = select_reference_audio_stream(media)
    planned_end = 7 * output_rate
    intervals = (
        AudioSampleInterval(0, 2048),
        AudioSampleInterval(5 * output_rate - 1, 2048),
        AudioSampleInterval(planned_end - 2048, 2048),
    )
    oracle_argv = continuous_decode_argv(
        media,
        stream,
        sample_rate=output_rate,
        channel_strategy="mono_downmix",
    )
    argv = _endpoint_limited_argv(oracle_argv, planned_end)

    result = collect_continuous_audio(
        argv,
        intervals,
        planned_end_sample=planned_end,
        max_retained_samples=sum(interval.sample_count for interval in intervals),
    )

    assert isinstance(result, ContinuousAudioCollection)
    assert result.end == "planned_end_reached"
    assert result.facts.emitted_sample_count == planned_end
    assert "-ss" not in argv
    assert any(f"atrim=end_sample={planned_end}" in part for part in argv)
    with continuous_decode(
        media,
        stream,
        sample_rate=output_rate,
        channel_strategy="mono_downmix",
    ) as oracle:
        assert isinstance(oracle, np.ndarray)
        assert not isinstance(oracle, np.memmap)
        retained_oracle_prefix = oracle[:16].copy()
        for interval, collected in zip(intervals, result.intervals, strict=True):
            expected = np.asarray(oracle[interval.start_sample : interval.end_sample])
            assert collected.actual_sample_count == interval.sample_count
            assert np.array_equal(collected.samples, expected)
    assert np.array_equal(oracle[:16], retained_oracle_prefix)


@pytest.mark.integration
def test_final_endpoint_preserves_untrimmed_continuous_prefix(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    output_rate = 8000
    wave_path = tmp_path / "prefix.wav"
    media = tmp_path / "prefix.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=7302, sample_rate=48000, duration_seconds=6),
        sample_rate=48000,
    )
    mux_audio(media, wave_path, source_rate=48000, codec="pcm")
    stream = select_reference_audio_stream(media)
    planned_end = 3 * output_rate + 123
    intervals = (AudioSampleInterval(planned_end - 4096, 4096),)
    oracle_argv = continuous_decode_argv(
        media,
        stream,
        sample_rate=output_rate,
        channel_strategy="mono_downmix",
    )

    result = collect_continuous_audio(
        _endpoint_limited_argv(oracle_argv, planned_end),
        intervals,
        planned_end_sample=planned_end,
        max_retained_samples=sum(interval.sample_count for interval in intervals),
    )

    assert isinstance(result, ContinuousAudioCollection)
    assert result.end == "planned_end_reached"
    with continuous_decode(
        media,
        stream,
        sample_rate=output_rate,
        channel_strategy="mono_downmix",
    ) as oracle:
        expected = np.asarray(oracle[intervals[0].start_sample : planned_end])
        assert np.array_equal(result.intervals[0].samples, expected)
