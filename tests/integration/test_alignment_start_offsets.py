"""Start-offset merge gate: container start times must compensate exactly.

In-sync container-delay fixtures use identical video, audio whose first ``D``
seconds are trimmed (padded with silence for negative ``D``) and
``-itsoffset D``, so playback stays in sync. The compensated sub-frame
estimate must land on ``r == 0`` with lag about ``+D*8000`` and compensation
about ``-D`` on every runtime. Nonzero truths trim ``N`` frames from both
video and audio of the comparison (keeping sync) and expect ``r == +N``.
Desync fixtures (same content with an uncompensated container shift) are
deleted: their truth is a content offset under desync, not a video truth.
"""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.services.alignment import align_clips_from_request as _align_clips_from_request
from frame_compare.services.alignment_audio import (
    probe_streams,
    select_audio_pair,
)
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.subproc import run_subprocess
from frame_compare.utils.types import AlignmentRequest
from tests.services.alignment_request_test_support import alignment_request

_SAMPLE_RATE = 48000
_FPS_NUM = 24000
_FPS_DEN = 1001
_VIDEO_SIZE = "64x64"
_DURATION_SECONDS = 10
_DELAY_SECONDS = 0.5
_NONZERO_TRIM_FRAMES = 5


def align_clips_from_request(
    request: AlignmentRequest, config: AlignmentConfig
) -> list[AlignmentResult]:
    return asyncio.run(_align_clips_from_request(request, config))


def _run_ffmpeg(argv: list[str], *, timeout_seconds: int = 120) -> None:
    run_subprocess(["ffmpeg", "-y", *argv], timeout_seconds=timeout_seconds)


def _noise_wav(path: Path, *, seed: int, sample_rate: int = _SAMPLE_RATE) -> None:
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=white:sample_rate={sample_rate}:duration={_DURATION_SECONDS}:seed={seed}",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def _video_testsrc2(path: Path) -> None:
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={_VIDEO_SIZE}:rate={_FPS_NUM}/{_FPS_DEN}:duration={_DURATION_SECONDS}",
            "-c:v",
            "ffv1",
            "-an",
            str(path),
        ]
    )


def _trim_audio_first_delay(input_path: Path, output_path: Path, *, delay_seconds: float) -> None:
    _run_ffmpeg(
        [
            "-i",
            str(input_path),
            "-af",
            f"atrim=start={delay_seconds}",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    )


def _pad_audio_delay(input_path: Path, output_path: Path, *, delay_ms: int) -> None:
    _run_ffmpeg(
        [
            "-i",
            str(input_path),
            "-af",
            f"adelay={delay_ms}:all=1",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    )


def _mux_with_audio_offset(
    path: Path,
    video: Path,
    audio: Path,
    *,
    offset_seconds: float,
    audio_codec: str,
    container: str,
) -> None:
    """Mux with the audio shifted by ``offset_seconds`` (negative allowed)."""
    _run_ffmpeg(
        [
            "-i",
            str(video),
            "-itsoffset",
            str(offset_seconds),
            "-i",
            str(audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy" if container == "mkv" else "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            audio_codec,
            "-shortest",
            str(path),
        ]
    )


def _probe_starts(path: Path) -> tuple[Fraction, Fraction]:
    probed = probe_streams(path)
    selection, _ = select_audio_pair(
        probed,
        probed,
        reference_path=path,
        comparison_path=path,
        reference_override=None,
        comparison_override=None,
    )
    return (
        selection.stream.timeline.start_time,
        selection.video_start.start_time,
    )


def _align_pair(reference: Path, comparison: Path, generated_dir: Path) -> AlignmentResult:
    config = AlignmentConfig(cache_results=False, max_offset_seconds=1.0)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=generated_dir,
        fps_num=_FPS_NUM,
        fps_den=_FPS_DEN,
    )
    (result,) = align_clips_from_request(request, config)
    return result


def _assert_compensated(
    result: AlignmentResult,
    *,
    truth_frames: int,
    compensation_seconds: float,
    expected_lag: int,
) -> None:
    assert result.applied is False
    attempt = result.audio_attempt
    assert attempt is not None
    assert attempt.status == "complete"
    assert attempt.decision.state == "provisional"
    assert attempt.audio.compensation_seconds == pytest.approx(compensation_seconds, abs=0.005)
    assert attempt.audio.global_lag == pytest.approx(expected_lag, abs=2)
    subframe = attempt.audio.subframe_estimate
    assert subframe is not None
    assert abs(subframe - truth_frames) < 0.25
    assert attempt.audio.rounded_frame == truth_frames
    candidate = attempt.decision.candidate
    assert candidate is not None
    assert candidate.frame_offset == truth_frames


@pytest.mark.integration
def test_mkv_positive_in_sync_compensates_to_zero(tmp_path: Path, require_ffmpeg: None) -> None:
    video = tmp_path / "video.mkv"
    audio = tmp_path / "audio.wav"
    _video_testsrc2(video)
    _noise_wav(audio, seed=111)
    trimmed = tmp_path / "audio_trim.wav"
    _trim_audio_first_delay(audio, trimmed, delay_seconds=_DELAY_SECONDS)
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _mux_with_audio_offset(
        reference, video, audio, offset_seconds=0.0, audio_codec="pcm_s16le", container="mkv"
    )
    _mux_with_audio_offset(
        comparison,
        video,
        trimmed,
        offset_seconds=_DELAY_SECONDS,
        audio_codec="pcm_s16le",
        container="mkv",
    )

    audio_start, video_start = _probe_starts(comparison)
    assert float(audio_start) == pytest.approx(_DELAY_SECONDS, abs=0.005)
    assert float(video_start) == pytest.approx(0.0, abs=0.005)

    result = _align_pair(reference, comparison, tmp_path / "cache")
    _assert_compensated(
        result, truth_frames=0, compensation_seconds=-_DELAY_SECONDS, expected_lag=4000
    )


@pytest.mark.integration
def test_mkv_negative_in_sync_compensates_to_zero(tmp_path: Path, require_ffmpeg: None) -> None:
    video = tmp_path / "video.mkv"
    audio = tmp_path / "audio.wav"
    _video_testsrc2(video)
    _noise_wav(audio, seed=111)
    padded = tmp_path / "audio_pad.wav"
    _pad_audio_delay(audio, padded, delay_ms=int(_DELAY_SECONDS * 1000))
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _mux_with_audio_offset(
        reference, video, audio, offset_seconds=0.0, audio_codec="pcm_s16le", container="mkv"
    )
    _mux_with_audio_offset(
        comparison,
        video,
        padded,
        offset_seconds=-_DELAY_SECONDS,
        audio_codec="pcm_s16le",
        container="mkv",
    )

    audio_start, video_start = _probe_starts(comparison)
    # FFmpeg avoids negative timestamps by shifting the video forward: the
    # padded audio still starts at zero while the video starts at +D.
    assert float(audio_start) == pytest.approx(0.0, abs=0.005)
    assert float(video_start) == pytest.approx(_DELAY_SECONDS, abs=0.005)

    result = _align_pair(reference, comparison, tmp_path / "cache")
    _assert_compensated(
        result, truth_frames=0, compensation_seconds=_DELAY_SECONDS, expected_lag=-4000
    )


@pytest.mark.integration
@pytest.mark.parametrize("sample_rate", [44100, 48000])
def test_aac_resampled_in_sync_compensates_to_zero(
    tmp_path: Path, require_ffmpeg: None, sample_rate: int
) -> None:
    video = tmp_path / "video.mkv"
    audio = tmp_path / "audio.wav"
    _video_testsrc2(video)
    _noise_wav(audio, seed=111, sample_rate=sample_rate)
    trimmed = tmp_path / "audio_trim.wav"
    _trim_audio_first_delay(audio, trimmed, delay_seconds=_DELAY_SECONDS)
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _mux_with_audio_offset(
        reference, video, audio, offset_seconds=0.0, audio_codec="aac", container="mkv"
    )
    _mux_with_audio_offset(
        comparison,
        video,
        trimmed,
        offset_seconds=_DELAY_SECONDS,
        audio_codec="aac",
        container="mkv",
    )

    audio_start, _ = _probe_starts(comparison)
    # The AAC priming interval (1024 samples) is either signaled out of band
    # (CodecDelay; newer muxers) so the probed start is the mux offset, or
    # left in-band (older muxers) so the probed start trails by exactly one
    # priming interval. The reference side carries the same priming, so the
    # differenced A5 compensation is exactly the mux offset either way.
    observed_start = float(audio_start)
    candidates = (_DELAY_SECONDS, _DELAY_SECONDS - 1024 / sample_rate)
    expected_start = min(candidates, key=lambda value: abs(observed_start - value))
    assert observed_start == pytest.approx(expected_start, abs=0.005)

    result = _align_pair(reference, comparison, tmp_path / "cache")
    _assert_compensated(
        result, truth_frames=0, compensation_seconds=-_DELAY_SECONDS, expected_lag=4000
    )


@pytest.mark.integration
def test_mp4_edit_list_in_sync_compensates_to_zero(tmp_path: Path, require_ffmpeg: None) -> None:
    video = tmp_path / "video.mkv"
    audio = tmp_path / "audio.wav"
    _video_testsrc2(video)
    _noise_wav(audio, seed=111)
    trimmed = tmp_path / "audio_trim.wav"
    _trim_audio_first_delay(audio, trimmed, delay_seconds=_DELAY_SECONDS)
    reference = tmp_path / "reference.mp4"
    comparison = tmp_path / "comparison.mp4"
    _mux_with_audio_offset(
        reference, video, audio, offset_seconds=0.0, audio_codec="aac", container="mp4"
    )
    _mux_with_audio_offset(
        comparison,
        video,
        trimmed,
        offset_seconds=_DELAY_SECONDS,
        audio_codec="aac",
        container="mp4",
    )

    audio_start, _ = _probe_starts(comparison)
    # The mux delay lands in an MP4 edit list; the probed start is the mux
    # offset minus one AAC priming interval (1024 samples: decoded sample 0
    # sits at start_time on both sides). The priming itself is carried by the
    # chunk lag, so the sum still lands truth.
    assert 0.45 < float(audio_start) < 0.5

    result = _align_pair(reference, comparison, tmp_path / "cache")
    _assert_compensated(
        result,
        truth_frames=0,
        compensation_seconds=-(_DELAY_SECONDS - 1024 / 48000),
        expected_lag=3829,
    )


@pytest.mark.integration
def test_trim_both_video_and_audio_gives_nonzero_truth(
    tmp_path: Path, require_ffmpeg: None
) -> None:
    trim_seconds = _NONZERO_TRIM_FRAMES * _FPS_DEN / _FPS_NUM
    video = tmp_path / "video.mkv"
    audio = tmp_path / "audio.wav"
    _video_testsrc2(video)
    _noise_wav(audio, seed=111)
    reference = tmp_path / "reference.mkv"
    _mux_with_audio_offset(
        reference, video, audio, offset_seconds=0.0, audio_codec="pcm_s16le", container="mkv"
    )
    comparison = tmp_path / "comparison.mkv"
    _run_ffmpeg(
        [
            "-i",
            str(reference),
            "-vf",
            f"select='gte(n\\,{_NONZERO_TRIM_FRAMES})',setpts=PTS-STARTPTS",
            "-af",
            f"atrim=start={trim_seconds},asetpts=PTS-STARTPTS",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            str(comparison),
        ]
    )

    audio_start, video_start = _probe_starts(comparison)
    assert float(audio_start) == pytest.approx(0.0, abs=0.005)
    assert float(video_start) == pytest.approx(0.0, abs=0.005)

    result = _align_pair(reference, comparison, tmp_path / "cache")
    _assert_compensated(
        result,
        truth_frames=_NONZERO_TRIM_FRAMES,
        compensation_seconds=0.0,
        expected_lag=1668,
    )
