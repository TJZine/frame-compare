"""FFmpeg and ffprobe helpers for audio alignment."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import Literal, cast

import numpy as np

from frame_compare.services.alignment_correlation import ALIGNMENT_ANALYSIS_SAMPLE_LIMIT
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentChannelStrategy, AlignmentConfig
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import run_subprocess

_FFPROBE_TIMEOUT_SECONDS = 15.0
_FFMPEG_AUDIO_TIMEOUT_SECONDS = 120.0
_FLOAT32_BYTES = np.dtype(np.float32).itemsize
_MAX_ALIGNMENT_AUDIO_BYTES = ALIGNMENT_ANALYSIS_SAMPLE_LIMIT * _FLOAT32_BYTES
_SEEK_PREROLL_SECONDS = 1
_DEFAULT_WINDOW_SECONDS = 30
_DEFAULT_DISTRIBUTED_WINDOWS = 5
_MIN_ANALYSIS_SAMPLE_RATE = 4000
_MAX_ANALYSIS_SAMPLE_RATE = 8000
_MAX_ANALYSIS_WINDOWS = 16
_MAX_FFT_POINTS = 1 << 21
_FFT_WORK_BUDGET = 1 << 24
_MAX_SCORING_PAIR_SAMPLES = 3_000_000
_SCORING_SAMPLE_WORK_BUDGET = 15_000_000

TimelineDurationBasis = Literal[
    "duration_ts",
    "stream_duration",
    "stream_tag",
    "unavailable",
]


@dataclass(frozen=True)
class AudioStreamTimeline:
    """Selected stream timing normalized to its own zero-based audio timeline."""

    start_time: Fraction
    duration: Fraction | None
    time_base: Fraction | None
    duration_basis: TimelineDurationBasis
    input_start_time: Fraction = Fraction(0)


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
    timeline: AudioStreamTimeline = field(
        default_factory=lambda: AudioStreamTimeline(
            start_time=Fraction(0),
            duration=None,
            time_base=None,
            duration_basis="unavailable",
        )
    )


@dataclass(frozen=True)
class AudioWindowSpec:
    """One bounded reference window and its comparison search interval."""

    reference_start_sample: int
    reference_sample_count: int
    comparison_start_sample: int
    comparison_sample_count: int


@dataclass(frozen=True)
class AudioAnalysisPlan:
    """Bounded work selected for one reference/comparison stream pair."""

    sample_rate: int
    requested_sample_rate: int
    windows: tuple[AudioWindowSpec, ...]
    peak_fft_points: int
    total_fft_points: int


@dataclass(frozen=True)
class AudioAnalysisBudgetExceeded:
    """A schema-valid request that cannot fit the fixed analysis budget."""

    reason: str


@dataclass(frozen=True)
class AudioWindow:
    """Decoded signals plus their origins on each selected stream timeline."""

    reference: np.ndarray
    comparison: np.ndarray
    reference_start_sample: int
    comparison_start_sample: int


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


def _parse_optional_fraction(value: object) -> Fraction | None:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    try:
        parsed = Fraction(Decimal(str(value).strip()))
    except (InvalidOperation, OverflowError, ValueError, ZeroDivisionError):
        return None
    return parsed


def _parse_optional_duration(value: object) -> Fraction | None:
    parsed = _parse_optional_fraction(value)
    return parsed if parsed is not None and parsed > 0 else None


def _parse_time_base(value: object) -> Fraction | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return parsed if parsed > 0 else None


def _parse_duration_tag(value: object) -> Fraction | None:
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = Fraction(Decimal(parts[2]))
    except (InvalidOperation, OverflowError, ValueError, ZeroDivisionError):
        return None
    duration = hours * 3600 + minutes * 60 + seconds
    return duration if duration > 0 else None


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
    stream_obj: object,
    *,
    audio_stream_index: int,
    video_path: Path,
    input_start_time: Fraction,
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

    start_time = _parse_optional_fraction(stream.get("start_time")) or Fraction(0)
    time_base = _parse_time_base(stream.get("time_base"))
    duration_ts = _parse_optional_int(stream.get("duration_ts"))
    duration: Fraction | None = None
    duration_basis: TimelineDurationBasis = "unavailable"
    if duration_ts is not None and duration_ts > 0 and time_base is not None:
        duration = duration_ts * time_base
        duration_basis = "duration_ts"
    if duration is None:
        duration = _parse_optional_duration(stream.get("duration"))
        if duration is not None:
            duration_basis = "stream_duration"
    if duration is None:
        duration = _parse_duration_tag(tags_dict.get("DURATION") or tags_dict.get("duration"))
        if duration is not None:
            duration = max(Fraction(0), duration - start_time)
            duration_basis = "stream_tag"
    if duration is not None and duration <= 0:
        duration = None
        duration_basis = "unavailable"

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
        timeline=AudioStreamTimeline(
            start_time=start_time,
            duration=duration,
            time_base=time_base,
            duration_basis=duration_basis,
            input_start_time=input_start_time,
        ),
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
                "stream=index,codec_name,channels,channel_layout,sample_rate,"
                "start_time,duration,duration_ts,time_base:"
                "stream_disposition=default,original,comment:"
                "stream_tags=language,comment,DURATION:format=start_time"
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
    format_obj = payload.get("format")
    format_dict = cast(dict[str, object], format_obj) if isinstance(format_obj, dict) else {}
    input_start_time = _parse_optional_fraction(format_dict.get("start_time")) or Fraction(0)

    streams = [
        _parse_audio_stream(
            stream_obj,
            audio_stream_index=index,
            video_path=video_path,
            input_start_time=input_start_time,
        )
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


def _fft_size(sample_count: int) -> int:
    return 1 << max(0, sample_count - 1).bit_length()


def _distributed_indexes(count: int, selected: int) -> tuple[int, ...]:
    if selected >= count:
        return tuple(range(count))
    if selected == 1:
        return (count // 2,)
    return tuple(
        dict.fromkeys(round(index * (count - 1) / (selected - 1)) for index in range(selected))
    )


def _window_starts(
    total_samples: int,
    *,
    window_samples: int,
    stride_samples: int,
    default_windows: int,
    limit: int,
) -> tuple[int, ...]:
    available_start = max(0, total_samples - window_samples)
    if available_start == 0:
        return (0,)
    if stride_samples <= 0:
        selected = min(default_windows, limit)
        return tuple(
            dict.fromkeys(
                round(index * available_start / (selected - 1)) for index in range(selected)
            )
        )

    grid_count = available_start // stride_samples + 1
    includes_final = (grid_count - 1) * stride_samples == available_start
    count = grid_count if includes_final else grid_count + 1
    indexes = _distributed_indexes(count, min(count, limit))
    return tuple(
        available_start if not includes_final and index == grid_count else index * stride_samples
        for index in indexes
    )


def plan_audio_analysis(
    reference_stream: AudioStreamInfo,
    comparison_stream: AudioStreamInfo,
    *,
    config: AlignmentConfig,
) -> AudioAnalysisPlan | AudioAnalysisBudgetExceeded:
    """Plan bounded, timeline-distributed work without changing config validation."""
    if not all(
        math.isfinite(value)
        for value in (
            config.max_offset_seconds,
            config.window_length_seconds,
            config.window_stride_seconds,
        )
    ):
        return AudioAnalysisBudgetExceeded("non_finite_analysis_config")
    reference_duration = reference_stream.timeline.duration
    comparison_duration = comparison_stream.timeline.duration
    if reference_duration is None or comparison_duration is None:
        return AudioAnalysisBudgetExceeded("selected_audio_timeline_unavailable")

    shared_duration = min(reference_duration, comparison_duration)
    if shared_duration <= 0:
        return AudioAnalysisBudgetExceeded("selected_audio_timeline_empty")

    requested_window_seconds = (
        Fraction(Decimal(str(config.window_length_seconds)))
        if config.window_length_seconds > 0
        else Fraction(_DEFAULT_WINDOW_SECONDS)
    )
    max_offset_seconds = Fraction(Decimal(str(config.max_offset_seconds)))

    rates = tuple(
        dict.fromkeys(
            (
                config.sample_rate,
                min(config.sample_rate, _MAX_ANALYSIS_SAMPLE_RATE),
                _MIN_ANALYSIS_SAMPLE_RATE,
            )
        )
    )
    selected_rate: int | None = None
    selected_window_samples = 0
    selected_margin_samples = 0
    selected_fft_points = 0
    for rate in rates:
        window_samples = max(2, round(min(shared_duration, requested_window_seconds) * rate))
        margin_samples = math.ceil(max_offset_seconds * rate)
        # Budget against the full requested search range even when a boundary would
        # shorten a particular window. This makes pathological config deterministic.
        fft_points = _fft_size(2 * window_samples + 2 * margin_samples - 1)
        if fft_points <= _MAX_FFT_POINTS:
            selected_rate = rate
            selected_window_samples = window_samples
            selected_margin_samples = margin_samples
            selected_fft_points = fft_points
            break

    if selected_rate is None:
        return AudioAnalysisBudgetExceeded("window_or_offset_exceeds_peak_budget")

    window_capacity = min(_MAX_ANALYSIS_WINDOWS, _FFT_WORK_BUDGET // selected_fft_points)
    if selected_rate != config.sample_rate:
        scoring_pair_samples = math.ceil(
            2 * selected_window_samples * config.sample_rate / selected_rate
        )
        if scoring_pair_samples > _MAX_SCORING_PAIR_SAMPLES:
            return AudioAnalysisBudgetExceeded("requested_rate_scoring_exceeds_peak_budget")
        window_capacity = min(
            window_capacity,
            _SCORING_SAMPLE_WORK_BUDGET // scoring_pair_samples,
        )
    if config.minimum_valid_windows > window_capacity:
        return AudioAnalysisBudgetExceeded("minimum_valid_windows_exceeds_work_budget")

    reference_total = max(1, math.floor(reference_duration * selected_rate))
    comparison_total = max(1, math.floor(comparison_duration * selected_rate))
    shared_total = min(reference_total, comparison_total)
    stride_samples = (
        max(1, round(config.window_stride_seconds * selected_rate))
        if config.window_stride_seconds > 0
        else (selected_window_samples if config.window_length_seconds > 0 else 0)
    )
    default_windows = max(_DEFAULT_DISTRIBUTED_WINDOWS, config.minimum_valid_windows)
    starts = _window_starts(
        shared_total,
        window_samples=selected_window_samples,
        stride_samples=stride_samples,
        default_windows=default_windows,
        limit=window_capacity,
    )

    windows: list[AudioWindowSpec] = []
    total_fft_points = 0
    peak_fft_points = 0
    for reference_start in starts:
        reference_count = min(selected_window_samples, reference_total - reference_start)
        comparison_start = max(0, reference_start - selected_margin_samples)
        comparison_end = min(
            comparison_total,
            reference_start + reference_count + selected_margin_samples,
        )
        comparison_count = comparison_end - comparison_start
        if reference_count < 2 or comparison_count < 2:
            continue
        fft_points = _fft_size(reference_count + comparison_count - 1)
        total_fft_points += fft_points
        peak_fft_points = max(peak_fft_points, fft_points)
        windows.append(
            AudioWindowSpec(
                reference_start_sample=reference_start,
                reference_sample_count=reference_count,
                comparison_start_sample=comparison_start,
                comparison_sample_count=comparison_count,
            )
        )

    if total_fft_points > _FFT_WORK_BUDGET:
        return AudioAnalysisBudgetExceeded("planned_windows_exceed_work_budget")
    return AudioAnalysisPlan(
        sample_rate=selected_rate,
        requested_sample_rate=config.sample_rate,
        windows=tuple(windows),
        peak_fft_points=peak_fft_points,
        total_fft_points=total_fft_points,
    )


def _seconds_arg(value: Fraction) -> str:
    return format(float(value), ".9f")


def extract_audio_window(
    video_path: Path,
    stream: AudioStreamInfo,
    *,
    sample_rate: int,
    start_sample: int,
    sample_count: int,
    channel_strategy: AlignmentChannelStrategy,
) -> np.ndarray:
    """Seek with preroll, then trim exactly on the selected stream timeline."""
    preroll_samples = min(start_sample, _SEEK_PREROLL_SECONDS * sample_rate)
    window_start = stream.timeline.start_time + Fraction(start_sample, sample_rate)
    window_end = window_start + Fraction(sample_count, sample_rate)
    seek_time = max(
        Fraction(0),
        window_start - Fraction(preroll_samples, sample_rate) - stream.timeline.input_start_time,
    )
    if seek_time > 0 and stream.timeline.time_base is not None:
        seek_time = (seek_time // stream.timeline.time_base) * stream.timeline.time_base
    filters: list[str] = []
    if channel_strategy == "mono_downmix":
        channel_args = ["-ac", "1"]
    else:
        channel_args = []
        filters.append(_best_channel_audio_filter(stream))
    filters.extend(
        (
            f"atrim=start={_seconds_arg(window_start)}:end={_seconds_arg(window_end)}",
            "asetpts=PTS-STARTPTS",
            f"aresample={sample_rate}",
            f"atrim=end_sample={sample_count}",
        )
    )
    seek_args = ["-ss", _seconds_arg(seek_time)] if seek_time > 0 else []
    if seek_time > 0 or stream.timeline.start_time != 0:
        seek_args.append("-copyts")
    argv = [
        "ffmpeg",
        *seek_args,
        "-i",
        str(video_path),
        "-map",
        f"0:a:{stream.audio_stream_index}",
        "-vn",
        *channel_args,
        "-af",
        ",".join(filters),
        "-fs",
        str(sample_count * _FLOAT32_BYTES),
        "-f",
        "f32le",
        "-",
    ]
    try:
        proc = run_subprocess(argv, timeout_seconds=_FFMPEG_AUDIO_TIMEOUT_SECONDS)
    except FileNotFoundError:
        raise FFmpegNotFoundError() from None
    except TimeoutExpired as e:
        raise FFmpegError("ffmpeg audio window extraction timed out", 124) from e
    except CalledProcessError as e:
        raise FFmpegError(_decode_stderr(e.stderr), e.returncode) from e
    except OSError as e:
        raise FFmpegError(f"ffmpeg audio window extraction could not start: {e}", 1) from e

    payload_len = len(proc.stdout)
    if payload_len == 0:
        raise AudioAlignmentError(f"empty audio window in {video_path.name}")
    if payload_len % _FLOAT32_BYTES != 0:
        raise AudioAlignmentError(
            f"invalid audio window payload from {video_path.name}: {payload_len} bytes"
        )
    if payload_len > sample_count * _FLOAT32_BYTES:
        raise AudioAlignmentError(
            f"audio window from {video_path.name} exceeded the planned sample count"
        )
    return np.frombuffer(proc.stdout, dtype=np.float32)


def iter_audio_windows(
    reference_path: Path,
    comparison_path: Path,
    reference_stream: AudioStreamInfo,
    comparison_stream: AudioStreamInfo,
    plan: AudioAnalysisPlan,
    *,
    channel_strategy: AlignmentChannelStrategy,
) -> Iterator[AudioWindow]:
    """Yield one decoded pair at a time so media duration cannot accumulate memory."""
    for spec in plan.windows:
        yield extract_planned_window(
            reference_path,
            comparison_path,
            reference_stream,
            comparison_stream,
            plan,
            spec,
            channel_strategy=channel_strategy,
        )


def extract_planned_window(
    reference_path: Path,
    comparison_path: Path,
    reference_stream: AudioStreamInfo,
    comparison_stream: AudioStreamInfo,
    plan: AudioAnalysisPlan,
    spec: AudioWindowSpec,
    *,
    channel_strategy: AlignmentChannelStrategy,
) -> AudioWindow:
    """Decode one planned coarse or requested-rate correlation pair."""
    reference = extract_audio_window(
        reference_path,
        reference_stream,
        sample_rate=plan.sample_rate,
        start_sample=spec.reference_start_sample,
        sample_count=spec.reference_sample_count,
        channel_strategy=channel_strategy,
    )
    comparison = extract_audio_window(
        comparison_path,
        comparison_stream,
        sample_rate=plan.sample_rate,
        start_sample=spec.comparison_start_sample,
        sample_count=spec.comparison_sample_count,
        channel_strategy=channel_strategy,
    )
    return AudioWindow(
        reference=reference,
        comparison=comparison,
        reference_start_sample=spec.reference_start_sample,
        comparison_start_sample=spec.comparison_start_sample,
    )


def extract_aligned_scoring_window(
    reference_path: Path,
    comparison_path: Path,
    reference_stream: AudioStreamInfo,
    comparison_stream: AudioStreamInfo,
    plan: AudioAnalysisPlan,
    spec: AudioWindowSpec,
    *,
    global_analysis_offset: int,
    channel_strategy: AlignmentChannelStrategy,
) -> AudioWindow:
    """Extract one requested-rate overlap aligned to a coarse global candidate."""
    rate = plan.requested_sample_rate
    reference_start = round(spec.reference_start_sample * rate / plan.sample_rate)
    reference_end = round(
        (spec.reference_start_sample + spec.reference_sample_count) * rate / plan.sample_rate
    )
    global_offset = round(global_analysis_offset * rate / plan.sample_rate)
    comparison_start = reference_start - global_offset
    if comparison_start < 0:
        reference_start -= comparison_start
        comparison_start = 0

    reference_total = math.floor((reference_stream.timeline.duration or Fraction(0)) * rate)
    comparison_total = math.floor((comparison_stream.timeline.duration or Fraction(0)) * rate)
    sample_count = min(
        reference_end - reference_start,
        reference_total - reference_start,
        comparison_total - comparison_start,
    )
    if sample_count < 1:
        raise AudioAlignmentError("candidate leaves no selected-stream audio overlap")
    reference = extract_audio_window(
        reference_path,
        reference_stream,
        sample_rate=rate,
        start_sample=reference_start,
        sample_count=sample_count,
        channel_strategy=channel_strategy,
    )
    comparison = extract_audio_window(
        comparison_path,
        comparison_stream,
        sample_rate=rate,
        start_sample=comparison_start,
        sample_count=sample_count,
        channel_strategy=channel_strategy,
    )
    return AudioWindow(
        reference=reference,
        comparison=comparison,
        reference_start_sample=reference_start,
        comparison_start_sample=comparison_start,
    )


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
