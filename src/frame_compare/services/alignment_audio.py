"""FFmpeg and ffprobe helpers for audio alignment."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np

from frame_compare.services.errors import AudioAlignmentError
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import CalledProcessError, TimeoutExpired, run_subprocess

_FFPROBE_TIMEOUT_SECONDS = 15.0
_FFMPEG_AUDIO_TIMEOUT_SECONDS = 120.0


def _decode_stderr(stderr: bytes) -> str:
    return stderr.decode("utf-8", errors="replace")


def probe_fps(video_path: Path) -> Fraction:
    """Probe video FPS using FFprobe."""
    argv = [
        "ffprobe",
        "-v",
        "quiet",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        proc = run_subprocess(argv, timeout_seconds=_FFPROBE_TIMEOUT_SECONDS)
    except FileNotFoundError:
        raise FFmpegNotFoundError() from None
    except TimeoutExpired as e:
        raise FFmpegError("ffprobe timed out", 124) from e
    except CalledProcessError as e:
        raise FFmpegError(_decode_stderr(e.stderr), e.returncode) from e

    output = proc.stdout.decode("utf-8").strip()
    normalized_output = output.removesuffix(",")
    if not normalized_output:
        raise AudioAlignmentError(
            f"unable to parse ffprobe FPS output for {video_path.name}: empty"
        )
    if "," in normalized_output:
        raise AudioAlignmentError(
            f"unable to parse ffprobe FPS output for {video_path.name}: {output!r}"
        )

    try:
        return Fraction(normalized_output)
    except (ValueError, ZeroDivisionError) as e:
        raise AudioAlignmentError(
            f"unable to parse ffprobe FPS output for {video_path.name}: {output!r}"
        ) from e


def extract_audio(video_path: Path, sample_rate: int) -> np.ndarray:
    """Extract audio using FFmpeg."""
    argv = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "-",
    ]

    try:
        proc = run_subprocess(argv, timeout_seconds=_FFMPEG_AUDIO_TIMEOUT_SECONDS)
    except FileNotFoundError:
        raise FFmpegNotFoundError() from None
    except TimeoutExpired as e:
        raise FFmpegError("ffmpeg audio extraction timed out", 124) from e
    except CalledProcessError as e:
        raise FFmpegError(_decode_stderr(e.stderr), e.returncode) from e
    except OSError as e:
        raise FFmpegError(f"ffmpeg audio extraction could not start: {e}", 1) from e

    if not proc.stdout:
        raise AudioAlignmentError(f"empty audio track in {video_path.name}")

    payload_len = len(proc.stdout)
    if payload_len % np.dtype(np.float32).itemsize != 0:
        raise AudioAlignmentError(
            f"invalid audio payload from {video_path.name}: {payload_len} bytes"
        )

    return np.frombuffer(proc.stdout, dtype=np.float32)
