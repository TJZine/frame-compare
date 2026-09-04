"""Runtime FFmpeg proofs for end-to-end audio alignment."""

from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_reuse_cache import CACHE_FILE_NAME as REUSE_CACHE_FILE_NAME
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.subproc import run_subprocess
from tests.services.alignment_request_test_support import alignment_request

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
def test_alignment_recovers_known_offset_from_generated_media(
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

    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=cache_dir,
        fps_num=_FPS,
    )
    results = align_clips_from_request(request, config)

    assert len(results) == 1
    _assert_applied_offset(results[0], frame_offset=-2)
    downmix_request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=downmix_config,
        generated_dir=downmix_cache_dir,
        fps_num=_FPS,
    )
    downmix_results = align_clips_from_request(downmix_request, downmix_config)
    assert downmix_results[0].applied is False
    assert downmix_results[0].diagnostic == "low_confidence"


_LONG_CLIP_SECONDS = 65


def _write_long_clip(path: Path, *, delay_ms: int = 0) -> None:
    if delay_ms % 20:
        raise ValueError("delay_ms must align to the 20 ms packet framing")
    # 65 s of audio forces the planner past the full-rate FFT budget, so
    # analysis runs downsampled while fallback windows are scored at the
    # requested 48 kHz rate.
    #
    # asetnsamples=960 reframes the audio into exact 20 ms packets. Matroska
    # stores packet timestamps at millisecond precision, so unaligned
    # packetization would shift post-seek extractions by a few samples and
    # white-noise windows could never reach exact sample consensus. Aligned
    # framing keeps every packet timestamp lossless, which makes the expected
    # offsets below deterministic instead of muxer-layout luck. The delay is
    # a multiple of the frame size, so the delayed variant stays aligned too.
    noise = (
        f"anoisesrc=color=white:sample_rate={_SAMPLE_RATE}"
        f":duration={_LONG_CLIP_SECONDS}:seed=917,asetnsamples=960"
    )
    argv = [
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=16x16:r={_FPS}:d={_LONG_CLIP_SECONDS}",
        "-f",
        "lavfi",
        "-i",
        noise,
    ]
    if delay_ms:
        argv += [
            "-filter_complex",
            f"[1:a]adelay={delay_ms}:all=1,atrim=0:{_LONG_CLIP_SECONDS},asetnsamples=960[delayed]",
            "-map",
            "0:v:0",
            "-map",
            "[delayed]",
        ]
    else:
        argv += ["-map", "0:v:0", "-map", "1:a:0"]
    argv += [
        "-c:v",
        "ffv1",
        "-c:a",
        "pcm_s16le",
        "-shortest",
        str(path),
    ]
    _run_ffmpeg(argv)


@pytest.mark.integration
def test_long_48k_alignment_scores_fallback_windows_at_requested_rate(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    reference = tmp_path / "long-reference.mkv"
    comparison = tmp_path / "long-comparison.mkv"
    generated_dir = tmp_path / "cache"
    generated_dir.mkdir()
    _write_long_clip(reference)
    _write_long_clip(comparison, delay_ms=200)
    config = AlignmentConfig(
        cache_results=False,
        sample_rate=48000,
        max_offset_seconds=1.0,
        confidence_threshold=0.9,
    )

    request = alignment_request(
        reference=reference,
        # The self pair pins the fallback path at zero offset while the
        # delayed pair proves the requested-rate result is genuinely
        # discriminating: a constant-zero implementation fails the second
        # assertion. Both are deterministic because _write_long_clip aligns
        # audio packetization to exact millisecond timestamps (see above).
        comparisons=[reference, comparison],
        config=config,
        generated_dir=generated_dir,
        fps_num=_FPS,
    )
    results = align_clips_from_request(request, config)

    assert len(results) == 2
    by_clip = {result.comparison_clip: result for result in results}
    _assert_applied_offset(by_clip[reference.name], frame_offset=0)
    _assert_applied_offset(by_clip[comparison.name], frame_offset=-2)


@pytest.mark.integration
def test_alignment_selects_runtime_streams_and_keeps_cache_config_distinct(
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

    default_request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=default_config,
        generated_dir=cache_dir,
        fps_num=_FPS,
    )
    default_results = align_clips_from_request(default_request, default_config)

    _assert_applied_offset(default_results[0], frame_offset=-2)

    override_request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=override_config,
        generated_dir=cache_dir,
        fps_num=_FPS,
    )
    override_results = align_clips_from_request(override_request, override_config)

    _assert_applied_offset(override_results[0], frame_offset=-1)


@pytest.mark.integration
def test_typed_alignment_writes_shared_reuse_when_previous_offsets_disabled(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    generated_dir = tmp_path / "generated"
    shared_alignment_cache_dir = tmp_path / "generated" / "cache" / "alignment"
    generated_dir.mkdir()
    _write_hostile_stereo_clip(reference)
    _write_hostile_stereo_clip(comparison, target_delay_ms=200)
    config = AlignmentConfig(
        cache_results=True,
        previous_offsets="disabled",
        sample_rate=_SAMPLE_RATE,
        max_offset_seconds=1.0,
        channel_strategy="best_channel",
        confidence_threshold=0.9,
    )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=generated_dir,
        shared_alignment_cache_dir=shared_alignment_cache_dir,
        fps_num=_FPS,
    )
    results = align_clips_from_request(request, config)

    assert len(results) == 1
    _assert_applied_offset(results[0], frame_offset=-2)
    assert (shared_alignment_cache_dir / REUSE_CACHE_FILE_NAME).exists()
    assert not (generated_dir / "audio_offsets.toml").exists()


@pytest.mark.integration
def test_alignment_rejects_weak_signal_without_applying_or_caching(
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

    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=cache_dir,
        fps_num=_FPS,
    )
    results = align_clips_from_request(request, config)

    assert len(results) == 1
    assert results[0].applied is False
    assert results[0].frame_offset is None
    assert results[0].time_offset_seconds is None
    assert results[0].diagnostic == "insufficient_valid_windows"
