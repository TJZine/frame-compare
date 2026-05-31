"""Runtime FFmpeg proofs for end-to-end audio alignment."""

from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.services.alignment import align_clips, check_alignment_cached
from frame_compare.services.alignment_cache import CACHE_FILE_NAME
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.subproc import run_subprocess

_DURATION_SECONDS = 3
_SAMPLE_RATE = 48000
_FPS = 10
_VIDEO_SIZE = "32x32"


def _run_ffmpeg(argv: list[str]) -> None:
    run_subprocess(["ffmpeg", "-y", *argv], timeout_seconds=30)


def _noise_input(seed: int, *, color: str = "white") -> str:
    return (
        "anoisesrc="
        f"color={color}:sample_rate={_SAMPLE_RATE}:duration={_DURATION_SECONDS}:seed={seed}"
    )


def _delayed_input(input_label: str, *, delay_ms: int = 0) -> str:
    if delay_ms == 0:
        return input_label
    return f"{input_label}adelay={delay_ms}:all=1,atrim=0:{_DURATION_SECONDS},"


def _hostile_stereo_filter(
    target_input: str,
    distractor_input: str,
    output_label: str,
    *,
    target_delay_ms: int = 0,
) -> str:
    return (
        f"{_delayed_input(target_input, delay_ms=target_delay_ms)}volume=1.0[{output_label}l];"
        f"{distractor_input}volume=2.0[{output_label}r];"
        f"[{output_label}l][{output_label}r]amerge=inputs=2[{output_label}]"
    )


def _write_hostile_stereo_clip(path: Path, *, target_delay_ms: int = 0) -> None:
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={_VIDEO_SIZE}:r={_FPS}:d={_DURATION_SECONDS}",
            "-f",
            "lavfi",
            "-i",
            _noise_input(111, color="white"),
            "-f",
            "lavfi",
            "-i",
            _noise_input(333, color="blue"),
            "-filter_complex",
            _hostile_stereo_filter("[1:a]", "[2:a]", "main", target_delay_ms=target_delay_ms),
            "-map",
            "0:v:0",
            "-map",
            "[main]",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-shortest",
            str(path),
        ]
    )


def _write_silent_clip(path: Path) -> None:
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={_VIDEO_SIZE}:r={_FPS}:d={_DURATION_SECONDS}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate={_SAMPLE_RATE}",
            "-t",
            str(_DURATION_SECONDS),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def _write_multi_stream_clip(
    path: Path,
    *,
    main_delay_ms: int = 0,
    commentary_delay_ms: int = 0,
) -> None:
    commentary_filter = (
        f"{_delayed_input('[1:a]', delay_ms=commentary_delay_ms)}"
        f"aformat=channel_layouts=mono[commentary]"
    )
    main_filter = _hostile_stereo_filter(
        "[2:a]",
        "[3:a]",
        "main",
        target_delay_ms=main_delay_ms,
    )
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={_VIDEO_SIZE}:r={_FPS}:d={_DURATION_SECONDS}",
            "-f",
            "lavfi",
            "-i",
            _noise_input(222, color="pink"),
            "-f",
            "lavfi",
            "-i",
            _noise_input(111, color="white"),
            "-f",
            "lavfi",
            "-i",
            _noise_input(333, color="blue"),
            "-filter_complex",
            f"{commentary_filter};{main_filter}",
            "-map",
            "0:v:0",
            "-map",
            "[commentary]",
            "-map",
            "[main]",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-disposition:a:0",
            "default+comment",
            "-metadata:s:a:0",
            "language=eng",
            "-metadata:s:a:0",
            "comment=Director commentary",
            "-disposition:a:1",
            "0",
            "-metadata:s:a:1",
            "language=eng",
            "-shortest",
            str(path),
        ]
    )


def _assert_applied_offset(result: AlignmentResult, *, frame_offset: int) -> None:
    assert result.applied is True
    assert result.source == "computed"
    assert result.frame_offset == frame_offset
    assert result.time_offset_seconds == pytest.approx(frame_offset / _FPS, abs=1 / _SAMPLE_RATE)
    assert result.correlation_score > 0.9


@pytest.mark.integration
def test_align_clips_recovers_known_offset_from_generated_media(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    cache_dir = tmp_path / "cache"
    downmix_cache_dir = tmp_path / "downmix-cache"
    cache_dir.mkdir()
    downmix_cache_dir.mkdir()
    _write_hostile_stereo_clip(reference)
    _write_hostile_stereo_clip(comparison, target_delay_ms=200)
    config = AlignmentConfig(
        cache_results=True,
        sample_rate=_SAMPLE_RATE,
        max_offset_seconds=1.0,
        channel_strategy="best_channel",
        confidence_threshold=0.9,
    )
    downmix_config = AlignmentConfig(
        cache_results=True,
        sample_rate=_SAMPLE_RATE,
        max_offset_seconds=1.0,
        channel_strategy="mono_downmix",
        confidence_threshold=0.9,
    )

    results = align_clips(reference, [comparison], config, cache_dir)

    assert len(results) == 1
    _assert_applied_offset(results[0], frame_offset=2)
    assert check_alignment_cached(reference, [comparison], cache_dir, config=config) == []
    downmix_results = align_clips(reference, [comparison], downmix_config, downmix_cache_dir)
    assert downmix_results[0].applied is False
    assert downmix_results[0].diagnostic == "low_confidence"


@pytest.mark.integration
def test_align_clips_selects_runtime_streams_and_keeps_cache_config_distinct(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _write_multi_stream_clip(reference)
    _write_multi_stream_clip(
        comparison,
        main_delay_ms=200,
        commentary_delay_ms=100,
    )
    default_config = AlignmentConfig(
        cache_results=True,
        sample_rate=_SAMPLE_RATE,
        max_offset_seconds=1.0,
        channel_strategy="best_channel",
        confidence_threshold=0.9,
    )
    override_config = AlignmentConfig(
        cache_results=True,
        sample_rate=_SAMPLE_RATE,
        max_offset_seconds=1.0,
        channel_strategy="best_channel",
        confidence_threshold=0.9,
        reference_stream=0,
        comparison_streams={comparison.stem: 0},
    )

    default_results = align_clips(reference, [comparison], default_config, cache_dir)

    _assert_applied_offset(default_results[0], frame_offset=2)
    assert check_alignment_cached(reference, [comparison], cache_dir, config=default_config) == []
    assert check_alignment_cached(reference, [comparison], cache_dir, config=override_config) == [
        "reference:comparison"
    ]

    override_results = align_clips(reference, [comparison], override_config, cache_dir)

    _assert_applied_offset(override_results[0], frame_offset=1)
    assert check_alignment_cached(reference, [comparison], cache_dir, config=override_config) == []
    assert check_alignment_cached(reference, [comparison], cache_dir, config=default_config) == [
        "reference:comparison"
    ]


@pytest.mark.integration
def test_align_clips_rejects_weak_signal_without_applying_or_caching(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _write_silent_clip(reference)
    _write_silent_clip(comparison)
    config = AlignmentConfig(
        cache_results=True,
        sample_rate=_SAMPLE_RATE,
        max_offset_seconds=1.0,
    )

    results = align_clips(reference, [comparison], config, cache_dir)

    assert len(results) == 1
    assert results[0].applied is False
    assert results[0].frame_offset is None
    assert results[0].time_offset_seconds is None
    assert results[0].diagnostic == "insufficient_valid_windows"
    assert not (cache_dir / CACHE_FILE_NAME).exists()
    assert check_alignment_cached(reference, [comparison], cache_dir, config=config) == [
        "reference:comparison"
    ]
