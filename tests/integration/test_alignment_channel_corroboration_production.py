"""Native FFmpeg proof for the production channel-corroboration path."""

from __future__ import annotations

import asyncio
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from frame_compare.services import alignment_audio
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.types import AlignmentConfig
from tests.integration.alignment_oracle import deterministic_signal
from tests.services.alignment_request_test_support import alignment_request


def _write_51(path: Path, samples: np.ndarray) -> None:
    raw = path.with_suffix(".f32le")
    raw.write_bytes(np.asarray(samples, dtype="<f4").tobytes())
    subprocess.run(  # noqa: S603 - fixed integration fixture executable
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "f32le",
            "-ar",
            "8000",
            "-ac",
            "6",
            "-channel_layout",
            "5.1",
            "-i",
            str(raw),
            "-c:a",
            "pcm_f32le",
            str(path),
        ],
        check=True,
        timeout=30,
    )


def _shift(signal: np.ndarray, offset: int) -> np.ndarray:
    shifted = np.zeros_like(signal)
    shifted[offset:] = signal[:-offset]
    return shifted


@pytest.mark.integration
def test_native_service_channel_corroboration_is_bounded_and_provisional(
    tmp_path: Path,
    require_ffmpeg: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duration_seconds = 95
    reference_samples = np.column_stack(
        [
            deterministic_signal(
                seed=6600 + channel,
                sample_rate=8000,
                duration_seconds=duration_seconds,
            )
            for channel in range(6)
        ]
    ).astype(np.float32)
    comparison_samples = np.column_stack(
        [_shift(reference_samples[:, channel], 80) for channel in range(6)]
    ).astype(np.float32)
    comparison_samples[:, 1] *= -0.7
    comparison_samples[:, 2] *= 0.45
    comparison_samples[:, 3:] *= -0.8
    reference = tmp_path / "reference.wav"
    comparison = tmp_path / "comparison.wav"
    _write_51(reference, reference_samples)
    _write_51(comparison, comparison_samples)

    real_collect = alignment_audio.collect_continuous_audio
    decode_count = 0
    active = 0
    maximum_active = 0
    retained_samples = 0

    def observed_collect(*args: object, **kwargs: object):
        nonlocal decode_count, active, maximum_active, retained_samples
        decode_count += 1
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            result = real_collect(*args, **kwargs)
            retained_samples += result.facts.retained_sample_count
            return result
        finally:
            active -= 1

    monkeypatch.setattr(alignment_audio, "collect_continuous_audio", observed_collect)
    config = AlignmentConfig(
        sample_rate=8000,
        max_offset_seconds=1,
        cache_results=False,
    )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )

    results = asyncio.run(align_clips_from_request(request, config, reference_fps=Fraction(24)))

    assert decode_count == 8
    assert maximum_active == 1
    assert active == 0
    assert retained_samples <= 2 * (1 << 24)
    result = results[0]
    assert result.applied is False
    assert result.frame_offset is None
    assert result.audio_attempt is not None
    attempt = result.audio_attempt
    assert attempt.decision.state == "provisional"
    assert attempt.decision.primary_reason == "channel_corroboration_provisional"
    assert attempt.decision.candidate is not None
    assert attempt.decision.candidate.frame_offset == 0
    assert attempt.channel_corroboration is not None
    assert attempt.channel_corroboration.status == "corroborated"
    assert attempt.channel_corroboration.independent_windows == 3
    assert len(attempt.channel_corroboration.collections) == 6
