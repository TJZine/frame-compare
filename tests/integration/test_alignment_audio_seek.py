"""Real FFmpeg seek-grid checks for bounded audio alignment windows."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from frame_compare.services.alignment_audio import (
    extract_audio_window,
    select_reference_audio_stream,
)
from frame_compare.utils.subproc import run_subprocess


@pytest.mark.integration
@pytest.mark.parametrize(
    ("suffix", "codec_args"),
    [
        ("mkv", ["-c:a", "pcm_s16le"]),
        ("mp4", ["-c:a", "aac", "-b:a", "192k"]),
    ],
)
def test_seek_with_preroll_stays_on_selected_stream_sample_grid(
    tmp_path: Path,
    require_ffmpeg: None,
    suffix: str,
    codec_args: list[str],
) -> None:
    media = tmp_path / f"timeline.{suffix}"
    run_subprocess(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=sin(2*PI*(317+7*t)*t)+0.2*sin(2*PI*911*t):s=48000:d=12",
            *codec_args,
            str(media),
        ],
        timeout_seconds=20,
    )
    stream = select_reference_audio_stream(media)
    full = extract_audio_window(
        media,
        stream,
        sample_rate=8000,
        start_sample=0,
        sample_count=96000,
        channel_strategy="mono_downmix",
    )

    for start in (0, 1, 7999, 8000, 23456, 64000, 79999):
        window = extract_audio_window(
            media,
            stream,
            sample_rate=8000,
            start_sample=start,
            sample_count=4000,
            channel_strategy="mono_downmix",
        )
        expected = full[start : start + 4000]
        assert window.size == expected.size == 4000
        assert np.corrcoef(window, expected)[0, 1] > 0.9999
        lag = int(np.argmax(np.correlate(expected, window, mode="full"))) - (window.size - 1)
        assert lag == 0


@pytest.mark.integration
def test_seek_is_relative_to_nonzero_selected_stream_start(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    media = tmp_path / "delayed-audio.mkv"
    run_subprocess(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-itsoffset",
            "2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=437:sample_rate=48000:duration=4",
            "-f",
            "lavfi",
            "-i",
            "color=size=16x16:rate=1:duration=6",
            "-map",
            "1:v:0",
            "-map",
            "0:a:0",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-copyts",
            str(media),
        ],
        timeout_seconds=20,
    )
    stream = select_reference_audio_stream(media)

    assert stream.timeline.start_time == 2
    assert stream.timeline.duration == 4
    window = extract_audio_window(
        media,
        stream,
        sample_rate=8000,
        start_sample=8000,
        sample_count=4000,
        channel_strategy="mono_downmix",
    )
    assert window.size == 4000
    assert float(np.sqrt(np.mean(window * window))) > 0.01


@pytest.mark.integration
@pytest.mark.parametrize(
    "codec_args",
    [
        ["-c:a", "pcm_s16le"],
        ["-c:a", "aac", "-b:a", "192k"],
    ],
)
def test_audio_only_positive_container_start_matches_full_decode_grid(
    tmp_path: Path,
    require_ffmpeg: None,
    codec_args: list[str],
) -> None:
    media = tmp_path / f"positive-container-start-{codec_args[1]}.mkv"
    run_subprocess(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-itsoffset",
            "2",
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=sin(2*PI*(317+7*t)*t)+0.2*sin(2*PI*911*t):s=48000:d=8",
            *codec_args,
            "-copyts",
            str(media),
        ],
        timeout_seconds=20,
    )
    stream = select_reference_audio_stream(media)
    full = extract_audio_window(
        media,
        stream,
        sample_rate=8000,
        start_sample=0,
        sample_count=64000,
        channel_strategy="mono_downmix",
    )
    start = 12345
    window = extract_audio_window(
        media,
        stream,
        sample_rate=8000,
        start_sample=start,
        sample_count=4000,
        channel_strategy="mono_downmix",
    )
    expected = full[start : start + 4000]

    assert stream.timeline.start_time > Fraction(19, 10)
    assert stream.timeline.input_start_time > Fraction(19, 10)
    assert np.corrcoef(window, expected)[0, 1] > 0.9999
    lag = int(np.argmax(np.correlate(expected, window, mode="full"))) - (window.size - 1)
    assert lag == 0


@pytest.mark.integration
def test_negative_selected_stream_start_is_preserved_during_trim(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    media = tmp_path / "negative-start.mkv"
    run_subprocess(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-itsoffset",
            "-1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=437:sample_rate=48000:duration=4",
            "-c:a",
            "pcm_s16le",
            "-copyts",
            "-avoid_negative_ts",
            "disabled",
            str(media),
        ],
        timeout_seconds=20,
    )
    stream = select_reference_audio_stream(media)

    assert stream.timeline.start_time == -1
    assert stream.timeline.duration == 4
    window = extract_audio_window(
        media,
        stream,
        sample_rate=8000,
        start_sample=0,
        sample_count=4000,
        channel_strategy="mono_downmix",
    )
    assert window.size == 4000
    assert float(np.sqrt(np.mean(window * window))) > 0.01
