"""FFmpeg and ffprobe helpers for audio alignment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import cast

import numpy as np

from frame_compare.services.alignment_correlation import ALIGNMENT_ANALYSIS_SAMPLE_LIMIT
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentChannelStrategy
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import run_subprocess

_FFPROBE_TIMEOUT_SECONDS = 15.0
_FFMPEG_AUDIO_TIMEOUT_SECONDS = 120.0
_FLOAT32_BYTES = np.dtype(np.float32).itemsize
_MAX_ALIGNMENT_AUDIO_BYTES = ALIGNMENT_ANALYSIS_SAMPLE_LIMIT * _FLOAT32_BYTES


@dataclass(frozen=True)
class AudioStreamInfo:
    """Normalized ffprobe audio stream metadata used for deterministic selection."""

    audio_stream_index: int
    absolute_stream_index: int
    codec_name: str | None
    channels: int | None
    channel_layout: str | None
    sample_rate: int | None
    language: str | None
    is_default: bool
    is_original: bool
    is_commentary: bool


def _decode_stderr(stderr: bytes) -> str:
    return stderr.decode("utf-8", errors="replace")


def _normalize_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _parse_optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return int(normalized)
        except ValueError:
            return None
    return None


def _parse_flag(value: object) -> bool:
    parsed = _parse_optional_int(value)
    return parsed == 1


def _is_commentary_tag(value: object) -> bool:
    if _parse_flag(value):
        return True
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return False
    return "commentary" in normalized


def _load_ffprobe_json(argv: list[str], *, operation: str) -> dict[str, object]:
    try:
        proc = run_subprocess(argv, timeout_seconds=_FFPROBE_TIMEOUT_SECONDS)
    except FileNotFoundError:
        raise FFmpegNotFoundError() from None
    except TimeoutExpired as e:
        raise FFmpegError(f"ffprobe timed out while {operation}", 124) from e
    except CalledProcessError as e:
        raise FFmpegError(_decode_stderr(e.stderr), e.returncode) from e
    except OSError as e:
        raise FFmpegError(f"ffprobe could not start while {operation}: {e}", 1) from e

    try:
        payload = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise FFmpegError("ffprobe returned invalid json", proc.returncode) from e
    if not isinstance(payload, dict):
        raise FFmpegError("ffprobe returned invalid json object", proc.returncode)
    return cast(dict[str, object], payload)


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
    except OSError as e:
        raise FFmpegError(f"ffprobe could not start: {e}", 1) from e

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


def _parse_audio_stream(
    stream_obj: object, *, audio_stream_index: int, video_path: Path
) -> AudioStreamInfo:
    if not isinstance(stream_obj, dict):
        raise FFmpegError(f"ffprobe returned invalid audio stream data for {video_path.name}", 0)
    stream = cast(dict[str, object], stream_obj)

    absolute_stream_index = _parse_optional_int(stream.get("index"))
    if absolute_stream_index is None:
        raise FFmpegError(f"ffprobe returned audio stream without index for {video_path.name}", 0)

    disposition_obj = stream.get("disposition", {})
    disposition_dict = (
        cast(dict[str, object], disposition_obj) if isinstance(disposition_obj, dict) else {}
    )

    tags_obj = stream.get("tags", {})
    tags_dict = cast(dict[str, object], tags_obj) if isinstance(tags_obj, dict) else {}

    return AudioStreamInfo(
        audio_stream_index=audio_stream_index,
        absolute_stream_index=absolute_stream_index,
        codec_name=_normalize_optional_text(stream.get("codec_name")),
        channels=_parse_optional_int(stream.get("channels")),
        channel_layout=_normalize_optional_text(stream.get("channel_layout")),
        sample_rate=_parse_optional_int(stream.get("sample_rate")),
        language=_normalize_optional_text(tags_dict.get("language")),
        is_default=_parse_flag(disposition_dict.get("default")),
        is_original=_parse_flag(disposition_dict.get("original")),
        is_commentary=_is_commentary_tag(disposition_dict.get("comment"))
        or _is_commentary_tag(tags_dict.get("comment")),
    )


def _probe_audio_streams(video_path: Path) -> list[AudioStreamInfo]:
    payload = _load_ffprobe_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            (
                "stream=index,codec_name,channels,channel_layout,sample_rate:"
                "stream_disposition=default,original,comment:"
                "stream_tags=language,comment"
            ),
            "-of",
            "json",
            str(video_path),
        ],
        operation="probing audio streams",
    )

    streams_obj = payload.get("streams")
    if not isinstance(streams_obj, list):
        raise FFmpegError(f"ffprobe returned invalid audio stream list for {video_path.name}", 0)
    stream_items = cast(list[object], streams_obj)

    streams = [
        _parse_audio_stream(stream_obj, audio_stream_index=index, video_path=video_path)
        for index, stream_obj in enumerate(stream_items)
    ]
    if not streams:
        raise AudioAlignmentError(f"no audio streams found in {video_path.name}")
    return streams


def _reference_stream_sort_key(stream: AudioStreamInfo) -> tuple[int, int, int, int]:
    return (
        1 if stream.is_commentary else 0,
        0 if stream.is_default or stream.is_original else 1,
        -(stream.channels or 0),
        stream.audio_stream_index,
    )


def _text_match_score(reference_value: str | None, candidate_value: str | None) -> tuple[int, int]:
    if reference_value is None:
        return (0, 0)
    if candidate_value == reference_value:
        return (0, 0)
    if candidate_value is None:
        return (1, 0)
    return (2, 0)


def _numeric_match_score(
    reference_value: int | None, candidate_value: int | None
) -> tuple[int, int]:
    if reference_value is None:
        return (0, 0)
    if candidate_value == reference_value:
        return (0, 0)
    if candidate_value is None:
        return (1, 0)
    return (2, abs(candidate_value - reference_value))


def _comparison_stream_sort_key(
    reference_stream: AudioStreamInfo,
    candidate_stream: AudioStreamInfo,
) -> tuple[int, int, int, int, int, int, int, int, int, int, int, int]:
    language_score = _text_match_score(reference_stream.language, candidate_stream.language)
    channels_score = _numeric_match_score(reference_stream.channels, candidate_stream.channels)
    layout_score = _text_match_score(
        reference_stream.channel_layout,
        candidate_stream.channel_layout,
    )
    sample_rate_score = _numeric_match_score(
        reference_stream.sample_rate,
        candidate_stream.sample_rate,
    )
    codec_score = _text_match_score(reference_stream.codec_name, candidate_stream.codec_name)

    return (
        0 if candidate_stream.is_commentary == reference_stream.is_commentary else 1,
        language_score[0],
        language_score[1],
        channels_score[0],
        channels_score[1],
        layout_score[0],
        layout_score[1],
        sample_rate_score[0],
        sample_rate_score[1],
        codec_score[0],
        0 if candidate_stream.is_default or candidate_stream.is_original else 1,
        candidate_stream.audio_stream_index,
    )


def _select_audio_stream_override(
    streams: list[AudioStreamInfo],
    *,
    video_path: Path,
    stream_override: int,
) -> AudioStreamInfo:
    for stream in streams:
        if stream.audio_stream_index == stream_override:
            return stream

    available = ", ".join(str(stream.audio_stream_index) for stream in streams)
    raise AudioAlignmentError(
        f"audio stream override {stream_override} not found in {video_path.name}; "
        f"available audio stream ordinals: {available}"
    )


def select_reference_audio_stream(
    video_path: Path,
    *,
    stream_override: int | None = None,
) -> AudioStreamInfo:
    """Choose the reference anchor stream deterministically from ffprobe metadata."""
    streams = _probe_audio_streams(video_path)
    if stream_override is not None:
        return _select_audio_stream_override(
            streams,
            video_path=video_path,
            stream_override=stream_override,
        )
    return min(streams, key=_reference_stream_sort_key)


def select_matching_audio_stream(
    video_path: Path,
    *,
    reference_stream: AudioStreamInfo,
    stream_override: int | None = None,
) -> AudioStreamInfo:
    """Choose the comparison stream that best matches the selected reference stream."""
    streams = _probe_audio_streams(video_path)
    if stream_override is not None:
        return _select_audio_stream_override(
            streams,
            video_path=video_path,
            stream_override=stream_override,
        )
    return min(
        streams,
        key=lambda candidate: _comparison_stream_sort_key(reference_stream, candidate),
    )


def _best_channel_audio_filter(stream: AudioStreamInfo | None) -> str:
    if stream is None:
        return "pan=mono|c0=c0"

    layout = stream.channel_layout
    if layout is not None and "5.1" in layout:
        return "pan=mono|c0=FC"
    if layout in {"stereo", "2.0"}:
        return "pan=mono|c0=FL"
    if stream.channels == 1 or layout == "mono":
        return "pan=mono|c0=c0"
    if stream.channels is not None and stream.channels >= 3:
        return "pan=mono|c0=c2"
    return "pan=mono|c0=c0"


def _audio_output_args(
    *,
    channel_strategy: AlignmentChannelStrategy,
    stream: AudioStreamInfo | None,
    sample_rate: int,
) -> list[str]:
    filters: list[str] = []
    if channel_strategy == "mono_downmix":
        channel_args = ["-ac", "1"]
    else:
        channel_args = []
        filters.append(_best_channel_audio_filter(stream))
    filters.extend(
        (
            f"aresample={sample_rate}",
            f"atrim=end_sample={ALIGNMENT_ANALYSIS_SAMPLE_LIMIT}",
        )
    )
    return [*channel_args, "-af", ",".join(filters)]


def extract_audio(
    video_path: Path,
    sample_rate: int,
    *,
    audio_stream_index: int,
    channel_strategy: AlignmentChannelStrategy = "mono_downmix",
    stream: AudioStreamInfo | None = None,
) -> np.ndarray:
    """Extract audio using FFmpeg with an explicit mapped audio stream."""
    argv = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-map",
        f"0:a:{audio_stream_index}",
        "-vn",
        *_audio_output_args(
            channel_strategy=channel_strategy,
            stream=stream,
            sample_rate=sample_rate,
        ),
        "-fs",
        str(_MAX_ALIGNMENT_AUDIO_BYTES),
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
    if payload_len % _FLOAT32_BYTES != 0:
        raise AudioAlignmentError(
            f"invalid audio payload from {video_path.name}: {payload_len} bytes"
        )

    sample_count = payload_len // _FLOAT32_BYTES
    if sample_count > ALIGNMENT_ANALYSIS_SAMPLE_LIMIT:
        raise AudioAlignmentError(
            f"audio payload from {video_path.name} exceeded the analysis sample limit"
        )

    return np.frombuffer(proc.stdout, dtype=np.float32)


def extract_reference_audio(
    video_path: Path,
    sample_rate: int,
    *,
    stream_override: int | None = None,
    channel_strategy: AlignmentChannelStrategy = "mono_downmix",
) -> tuple[np.ndarray, AudioStreamInfo]:
    """Select and extract the reference anchor stream."""
    stream = select_reference_audio_stream(video_path, stream_override=stream_override)
    return (
        extract_audio(
            video_path,
            sample_rate,
            audio_stream_index=stream.audio_stream_index,
            channel_strategy=channel_strategy,
            stream=stream,
        ),
        stream,
    )


def extract_matching_audio(
    video_path: Path,
    sample_rate: int,
    *,
    reference_stream: AudioStreamInfo,
    stream_override: int | None = None,
    channel_strategy: AlignmentChannelStrategy = "mono_downmix",
) -> np.ndarray:
    """Select and extract the comparison stream that matches the reference anchor."""
    stream = select_matching_audio_stream(
        video_path,
        reference_stream=reference_stream,
        stream_override=stream_override,
    )
    return extract_audio(
        video_path,
        sample_rate,
        audio_stream_index=stream.audio_stream_index,
        channel_strategy=channel_strategy,
        stream=stream,
    )
