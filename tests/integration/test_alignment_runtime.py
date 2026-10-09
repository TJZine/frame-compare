"""Runtime FFmpeg/L-SMASH proofs for whole-track audio alignment."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.services.alignment import align_clips_from_request as _align_clips_from_request
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.subproc import run_subprocess
from frame_compare.utils.types import AlignmentRequest
from frame_compare.vs.env import detect_plugins, ensure_vs_environment
from frame_compare.vs.errors import VapourSynthError, VapourSynthNotFoundError
from frame_compare.vs.loader import DefaultVSLoader, VSLoader
from tests.services.alignment_request_test_support import alignment_request

vs_mod = pytest.importorskip("vapoursynth")
if isinstance(vs_mod, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)

try:
    _core = ensure_vs_environment()
except (VapourSynthNotFoundError, VapourSynthError) as exc:
    pytest.skip(f"vapoursynth not available: {exc}", allow_module_level=True)

if not detect_plugins(_core).get("lsmas", False):
    pytest.skip("lsmas plugin not available", allow_module_level=True)

_SAMPLE_RATE = 48000
_FPS = 10
_VIDEO_SIZE = "160x90"


def align_clips_from_request(
    request: AlignmentRequest, config: AlignmentConfig, *, vs_loader: VSLoader | None = None
) -> list[AlignmentResult]:
    return asyncio.run(_align_clips_from_request(request, config, vs_loader=vs_loader))


def _run_ffmpeg(argv: list[str], *, timeout_seconds: int = 120) -> None:
    run_subprocess(["ffmpeg", "-y", *argv], timeout_seconds=timeout_seconds)


def _noise_input(seed: int, duration_seconds: int) -> str:
    return (
        f"anoisesrc=color=white:sample_rate={_SAMPLE_RATE}:duration={duration_seconds}:seed={seed}"
    )


def _write_clip(
    path: Path,
    *,
    duration_seconds: int = 20,
    delay_ms: int = 0,
    video_delay_ms: int = 0,
    seed: int = 111,
) -> None:
    audio = f"[0:a]adelay={delay_ms}:all=1" if delay_ms else "[0:a]anull"
    video_filter = (
        [
            "-vf",
            f"tpad=start_mode=add:stop_mode=clone:start_duration={video_delay_ms / 1000}",
        ]
        if video_delay_ms
        else []
    )
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            _noise_input(seed, duration_seconds),
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={_VIDEO_SIZE}:rate={_FPS}:duration={duration_seconds}",
            "-filter_complex",
            f"{audio}[outa]",
            "-map",
            "1:v:0",
            "-map",
            "[outa]",
            *video_filter,
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-shortest",
            str(path),
        ]
    )


def _write_silent_clip(path: Path, *, duration_seconds: int = 20) -> None:
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={_VIDEO_SIZE}:r={_FPS}:d={duration_seconds}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate={_SAMPLE_RATE}",
            "-t",
            str(duration_seconds),
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


def _write_insert_clip(path: Path) -> None:
    """70 s of reference timing with 0.5 s of silence inserted at 30 s."""
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            _noise_input(111, 30),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000:d=0.5",
            "-ss",
            "30",
            "-f",
            "lavfi",
            "-i",
            _noise_input(111, 70),
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={_VIDEO_SIZE}:r={_FPS}:d=71",
            "-filter_complex",
            "[0:a][1:a][2:a]concat=n=3:v=0:a=1[conca]",
            "-map",
            "3:v:0",
            "-map",
            "[conca]",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-shortest",
            str(path),
        ]
    )


def _config(**overrides: object) -> AlignmentConfig:
    return AlignmentConfig(cache_results=False, **overrides)  # type: ignore[arg-type]


@pytest.fixture
def lsmash_loader() -> DefaultVSLoader:
    return DefaultVSLoader()


def _align_pair(
    reference: Path,
    comparison: Path,
    config: AlignmentConfig,
    generated_dir: Path,
    loader: DefaultVSLoader,
) -> AlignmentResult:
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        generated_dir=generated_dir,
        max_offset_seconds=1.0,
        fps_num=_FPS,
    )
    (result,) = align_clips_from_request(request, config, vs_loader=loader)
    return result


def _assert_trusted(result: AlignmentResult, *, frame_offset: int) -> None:
    attempt = result.audio_attempt
    assert result.applied is True
    assert result.frame_offset == frame_offset
    assert result.time_offset_seconds is not None
    assert result.source == "computed"
    assert result.diagnostic == "audio_video_confirmed"
    assert result.correlation_score == pytest.approx(1.0)
    assert attempt is not None
    assert attempt.status == "complete"
    assert attempt.decision.state == "trusted_automatic"
    assert attempt.decision.primary_reason == "audio_video_confirmed"
    candidate = attempt.decision.candidate
    assert candidate is not None
    assert candidate.frame_offset == frame_offset
    assert candidate.basis == "audio_only"
    assert attempt.audio.status == "agreed"
    assert attempt.audio.rounded_frame == frame_offset
    assert attempt.video_check.observation == "observed"
    assert attempt.video_check.confirmed_offset == frame_offset
    assert attempt.authority_recount is not None
    assert attempt.authority_recount.passed is True
    assert attempt.collection_observation == "observed"
    assert result.stability is not None
    assert result.stability.classification == "stable"


def _assert_unavailable(result: AlignmentResult, *, reason: str) -> None:
    assert result.applied is False
    assert result.frame_offset is None
    assert result.time_offset_seconds is None
    assert result.source == "computed"
    assert result.diagnostic == reason
    attempt = result.audio_attempt
    assert attempt is not None
    assert attempt.decision.state == "unavailable"
    assert attempt.decision.primary_reason == reason
    assert attempt.decision.candidate is None


@pytest.mark.integration
def test_delayed_comparison_is_confirmed(
    tmp_path: Path, require_ffmpeg: None, lsmash_loader: DefaultVSLoader
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _write_clip(reference)
    _write_clip(comparison, delay_ms=200, video_delay_ms=200)

    result = _align_pair(reference, comparison, _config(), tmp_path / "cache", lsmash_loader)

    _assert_trusted(result, frame_offset=-2)
    assert result.audio_attempt is not None
    assert result.audio_attempt.audio.subframe_estimate is not None
    assert abs(result.audio_attempt.audio.subframe_estimate - -2.0) < 0.25


@pytest.mark.integration
def test_delayed_reference_is_confirmed_positive(
    tmp_path: Path, require_ffmpeg: None, lsmash_loader: DefaultVSLoader
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _write_clip(reference, delay_ms=200, video_delay_ms=200)
    _write_clip(comparison)

    result = _align_pair(reference, comparison, _config(), tmp_path / "cache", lsmash_loader)

    _assert_trusted(result, frame_offset=2)


def _write_two_stem_clip(
    path: Path,
    video: Path,
    dialogue: Path,
    music: Path,
    *,
    music_gain: float,
    delay_ms: int = 0,
    video_delay_ms: int = 0,
) -> None:
    music_label = "[1:a]anull[m]" if music_gain == 1.0 else f"[1:a]volume={music_gain}[m]"
    delay = f",adelay={delay_ms}:all=1" if delay_ms else ""
    _run_ffmpeg(
        [
            "-i",
            str(video),
            "-i",
            str(music),
            "-i",
            str(dialogue),
            "-filter_complex",
            f"{music_label};[m][2:a]amix=inputs=2:duration=shortest:dropout_transition=0:normalize=0{delay}[outa]",
            "-map",
            "0:v:0",
            "-map",
            "[outa]",
            *(
                [
                    "-vf",
                    f"tpad=start_mode=add:stop_mode=clone:start_duration={video_delay_ms / 1000}",
                ]
                if video_delay_ms
                else []
            ),
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-shortest",
            str(path),
        ]
    )


@pytest.mark.integration
def test_remix_is_confirmed(
    tmp_path: Path, require_ffmpeg: None, lsmash_loader: DefaultVSLoader
) -> None:
    video = tmp_path / "video.mkv"
    dialogue = tmp_path / "dialogue.wav"
    music = tmp_path / "music.wav"
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={_VIDEO_SIZE}:rate={_FPS}:duration=20",
            "-c:v",
            "ffv1",
            "-an",
            str(video),
        ]
    )
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            _noise_input(111, 20),
            "-c:a",
            "pcm_s16le",
            str(dialogue),
        ]
    )
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            _noise_input(222, 20),
            "-c:a",
            "pcm_s16le",
            str(music),
        ]
    )
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _write_two_stem_clip(reference, video, dialogue, music, music_gain=1.0)
    # The music stem sits at -8 dB (volume 0.398107) in the comparison, plus
    # a 200 ms content delay: a real remix, distinct from the pure delay test.
    _write_two_stem_clip(
        comparison,
        video,
        dialogue,
        music,
        music_gain=0.398107,
        delay_ms=200,
        video_delay_ms=200,
    )

    result = _align_pair(
        reference,
        comparison,
        _config(),
        tmp_path / "cache",
        lsmash_loader,
    )

    _assert_trusted(result, frame_offset=-2)


@pytest.mark.integration
def test_unrelated_seeds_are_unavailable(
    tmp_path: Path, require_ffmpeg: None, lsmash_loader: DefaultVSLoader
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _write_clip(reference, seed=111)
    _write_clip(comparison, seed=333)

    result = _align_pair(reference, comparison, _config(), tmp_path / "cache", lsmash_loader)

    assert result.applied is False
    assert result.frame_offset is None
    assert result.time_offset_seconds is None
    assert result.audio_attempt is not None
    assert result.audio_attempt.decision.state == "unavailable"
    assert result.diagnostic == "video_check_inconclusive"
    assert result.audio_attempt.decision.failed_gates[0] == "video_check_inconclusive"
    assert result.audio_attempt.decision.failed_gates[1] in {
        "no_single_offset",
        "no_usable_audio",
    }


@pytest.mark.integration
def test_insert_gives_no_single_offset(
    tmp_path: Path, require_ffmpeg: None, lsmash_loader: DefaultVSLoader
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _write_clip(reference, duration_seconds=70)
    _write_insert_clip(comparison)

    result = _align_pair(reference, comparison, _config(), tmp_path / "cache", lsmash_loader)

    _assert_unavailable(result, reason="video_check_inconclusive")
    assert result.audio_attempt is not None
    assert result.audio_attempt.decision.failed_gates == (
        "video_check_inconclusive",
        "no_single_offset",
    )
    assert len(result.audio_attempt.runs) >= 2


@pytest.mark.integration
def test_silence_gives_no_usable_audio(
    tmp_path: Path, require_ffmpeg: None, lsmash_loader: DefaultVSLoader
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _write_silent_clip(reference)
    _write_silent_clip(comparison)

    result = _align_pair(reference, comparison, _config(), tmp_path / "cache", lsmash_loader)

    _assert_unavailable(result, reason="no_usable_audio")


@pytest.mark.integration
@pytest.mark.parametrize("duration_seconds", [4, 20, 60])
def test_short_sources_are_confirmed(
    tmp_path: Path,
    require_ffmpeg: None,
    lsmash_loader: DefaultVSLoader,
    duration_seconds: int,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    _write_clip(reference, duration_seconds=duration_seconds)
    _write_clip(
        comparison,
        duration_seconds=duration_seconds,
        delay_ms=200,
        video_delay_ms=200,
    )

    result = _align_pair(reference, comparison, _config(), tmp_path / "cache", lsmash_loader)

    _assert_trusted(result, frame_offset=-2)
