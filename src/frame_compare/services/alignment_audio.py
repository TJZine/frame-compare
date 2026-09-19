"""FFmpeg and ffprobe helpers for audio alignment."""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import Literal, cast

import numpy as np

from frame_compare.services.alignment_streaming import (
    AudioSampleInterval,
    ContinuousAudioCollection,
    ContinuousAudioCollectionFailure,
    collect_continuous_audio,
)
from frame_compare.services.errors import (
    AudioAlignmentCancellationError,
    AudioAlignmentCleanupError,
    AudioAlignmentError,
    raise_if_alignment_cancelled,
)
from frame_compare.services.types import (
    AlignmentChannelStrategy,
    AlignmentConfig,
    AudioAlignmentCollectionRecord,
    AudioMetadataMatch,
    SelectedAudioStreamEvidence,
)
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import run_subprocess

_FFPROBE_TIMEOUT_SECONDS = 15.0
_FFMPEG_AUDIO_TIMEOUT_SECONDS = 120.0
_FLOAT32_BYTES = np.dtype(np.float32).itemsize
_DEFAULT_WINDOW_SECONDS = 30
_DEFAULT_DISTRIBUTED_WINDOWS = 5
_MIN_ANALYSIS_SAMPLE_RATE = 4000
_MAX_ANALYSIS_SAMPLE_RATE = 8000
_MAX_ANALYSIS_WINDOWS = 16
_MAX_FFT_POINTS = 1 << 21
_FFT_WORK_BUDGET = 1 << 24
_MAX_SCORING_PAIR_SAMPLES = 3_000_000
_SCORING_SAMPLE_WORK_BUDGET = 15_000_000
_MAX_DISCOVERY_RETAINED_SAMPLES = _FFT_WORK_BUDGET + _MAX_ANALYSIS_WINDOWS
_MAX_SCORE_EVALUATIONS_PER_WINDOW = 512
_MAX_SCORED_POSITIONS = 536_870_912
_MAX_SCORE_POSITIONS_PER_EVALUATION = 65_536

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
    start_time_basis: Literal["metadata", "default_zero"] = "default_zero"
    input_start_time_basis: Literal["metadata", "default_zero"] = "default_zero"


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
    discovery_retained_samples: int = 0
    verification_reserved_samples: int = 0
    score_evaluations_per_window: int = 0
    scored_positions: int = 0
    reference_duration_samples: int = 0
    comparison_duration_samples: int = 0


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


@dataclass(frozen=True)
class AudioVerificationSpec:
    """One frozen requested-rate pair and its admitted global hypotheses."""

    window_index: int
    reference_start_sample: int
    reference_sample_count: int
    comparison_start_sample: int
    comparison_sample_count: int
    global_lower_offset: int
    global_upper_offset: int


@dataclass(frozen=True)
class CollectedAudioPhase:
    """One phase's read-only logical windows and bounded scalar summaries."""

    windows: tuple[AudioWindow, ...]
    summaries: tuple[AudioAlignmentCollectionRecord, ...]


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
    input_start_time_basis: Literal["metadata", "default_zero"],
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

    parsed_start_time = _parse_optional_fraction(stream.get("start_time"))
    start_time = parsed_start_time if parsed_start_time is not None else Fraction(0)
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
            start_time_basis="metadata" if parsed_start_time is not None else "default_zero",
            input_start_time_basis=input_start_time_basis,
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
    parsed_input_start_time = _parse_optional_fraction(format_dict.get("start_time"))
    input_start_time = (
        parsed_input_start_time if parsed_input_start_time is not None else Fraction(0)
    )

    streams = [
        _parse_audio_stream(
            stream_obj,
            audio_stream_index=index,
            video_path=video_path,
            input_start_time=input_start_time,
            input_start_time_basis=(
                "metadata" if parsed_input_start_time is not None else "default_zero"
            ),
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


def _bounded_evidence_text(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split())[:256]


def _metadata_match(reference: object | None, comparison: object | None) -> AudioMetadataMatch:
    if reference is None or comparison is None:
        return "unknown"
    return "match" if reference == comparison else "mismatch"


def selected_stream_evidence(
    stream: AudioStreamInfo,
    *,
    role: Literal["reference", "comparison"],
    source_identity_digest: str,
    explicit_override: bool,
    reference_stream: AudioStreamInfo | None = None,
) -> SelectedAudioStreamEvidence:
    """Project the resolved choice into bounded, pathless diagnostic facts."""
    timeline = stream.timeline
    duration = timeline.duration
    time_base = timeline.time_base
    if role == "reference":
        rank = (
            (stream.audio_stream_index,)
            if explicit_override
            else _reference_stream_sort_key(stream)
        )
        language_match: AudioMetadataMatch = "not_applicable"
        commentary_match: AudioMetadataMatch = "not_applicable"
    else:
        if reference_stream is None:
            raise ValueError("comparison stream evidence requires the reference stream")
        rank = (
            (stream.audio_stream_index,)
            if explicit_override
            else _comparison_stream_sort_key(reference_stream, stream)
        )
        language_match = _metadata_match(reference_stream.language, stream.language)
        commentary_match = _metadata_match(
            reference_stream.is_commentary,
            stream.is_commentary,
        )
    return SelectedAudioStreamEvidence(
        role=role,
        source_identity_digest=source_identity_digest,
        audio_stream_index=stream.audio_stream_index,
        absolute_stream_index=stream.absolute_stream_index,
        selection_method="explicit_override" if explicit_override else "automatic_metadata",
        selection_rank=rank,
        codec_name=_bounded_evidence_text(stream.codec_name),
        sample_rate=stream.sample_rate,
        channels=stream.channels,
        channel_layout=_bounded_evidence_text(stream.channel_layout),
        language=_bounded_evidence_text(stream.language),
        is_default=stream.is_default,
        is_original=stream.is_original,
        is_commentary=stream.is_commentary,
        language_match=language_match,
        commentary_match=commentary_match,
        stream_start_num=timeline.start_time.numerator,
        stream_start_den=timeline.start_time.denominator,
        stream_start_basis=timeline.start_time_basis,
        input_start_num=timeline.input_start_time.numerator,
        input_start_den=timeline.input_start_time.denominator,
        input_start_basis=timeline.input_start_time_basis,
        time_base_num=time_base.numerator if time_base is not None else None,
        time_base_den=time_base.denominator if time_base is not None else None,
        duration_num=duration.numerator if duration is not None else None,
        duration_den=duration.denominator if duration is not None else None,
        duration_basis=timeline.duration_basis,
    )


def normalized_extraction_recipe() -> str:
    """Describe extraction without retaining media paths or a concrete command line."""
    return (
        "ffmpeg -i <role_input> -map 0:a:<selected_ordinal> -vn "
        "[channel] -af <channel>,aresample=<rate>,atrim=end_sample=<horizon> -f f32le -"
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

    # Discovery is deliberately standardized at no more than 8 kHz. A single
    # 4 kHz retry is admitted only when the first rate cannot fit the FFT bound.
    rates = tuple(dict.fromkeys((min(config.sample_rate, _MAX_ANALYSIS_SAMPLE_RATE), 4000)))
    for rate in rates:
        candidate = _plan_at_discovery_rate(
            reference_duration,
            comparison_duration,
            requested_window_seconds=requested_window_seconds,
            max_offset_seconds=max_offset_seconds,
            rate=rate,
            config=config,
        )
        if isinstance(candidate, AudioAnalysisPlan):
            return candidate
        if candidate.reason != "window_or_offset_exceeds_peak_budget":
            return candidate
    return AudioAnalysisBudgetExceeded("window_or_offset_exceeds_peak_budget")


def _plan_at_discovery_rate(
    reference_duration: Fraction,
    comparison_duration: Fraction,
    *,
    requested_window_seconds: Fraction,
    max_offset_seconds: Fraction,
    rate: int,
    config: AlignmentConfig,
) -> AudioAnalysisPlan | AudioAnalysisBudgetExceeded:
    reference_total = max(1, math.floor(reference_duration * rate))
    comparison_total = max(1, math.floor(comparison_duration * rate))
    shared_total = min(reference_total, comparison_total)
    default_shape = config.window_length_seconds <= 0
    if default_shape:
        shared_seconds = min(reference_duration, comparison_duration)
        if shared_seconds <= 30:
            window_samples = shared_total
        elif shared_seconds < 90:
            window_samples = min(30 * rate, max(2, round(shared_seconds * rate / 2)))
        else:
            window_samples = min(shared_total, 30 * rate)
    else:
        window_samples = max(
            2, round(min(reference_duration, comparison_duration, requested_window_seconds) * rate)
        )
    margin_samples = math.ceil(max_offset_seconds * rate)
    conservative_fft = _fft_size(2 * window_samples + 2 * margin_samples - 1)
    if conservative_fft > _MAX_FFT_POINTS:
        return AudioAnalysisBudgetExceeded("window_or_offset_exceeds_peak_budget")

    refinement_rate = config.refinement_sample_rate or rate
    local_radius = min(
        int(config.max_offset_seconds * rate),
        max(1, int(round(rate * 0.005))),
    )
    local_evaluations = 0
    if config.refinement_mode == "local":
        local_evaluations = 2 * int(round(local_radius * max(1.0, refinement_rate / rate))) + 1
    discovery_evaluations = 1 + local_evaluations
    verification_evaluations = (
        2 * math.ceil(config.sample_rate / rate) + 1 if rate != config.sample_rate else 0
    )
    evaluations = discovery_evaluations + verification_evaluations
    if evaluations > _MAX_SCORE_EVALUATIONS_PER_WINDOW:
        return AudioAnalysisBudgetExceeded("scoring_evaluations_exceed_window_budget")

    window_capacity = min(_MAX_ANALYSIS_WINDOWS, _FFT_WORK_BUDGET // conservative_fft)
    stride_samples = (
        max(1, round(config.window_stride_seconds * rate))
        if config.window_stride_seconds > 0
        else (window_samples if config.window_length_seconds > 0 else 0)
    )
    if default_shape and min(reference_duration, comparison_duration) <= 30:
        starts = (0,)
    elif default_shape and min(reference_duration, comparison_duration) < 90:
        endpoint_starts = (0, max(0, shared_total - window_samples))
        if config.minimum_valid_windows <= 2:
            starts = endpoint_starts
        else:
            starts = _window_starts(
                shared_total,
                window_samples=window_samples,
                stride_samples=0,
                default_windows=config.minimum_valid_windows,
                limit=window_capacity,
            )
    else:
        starts = _window_starts(
            shared_total,
            window_samples=window_samples,
            stride_samples=stride_samples,
            default_windows=max(_DEFAULT_DISTRIBUTED_WINDOWS, config.minimum_valid_windows),
            limit=window_capacity,
        )

    windows: list[AudioWindowSpec] = []
    total_fft_points = 0
    peak_fft_points = 0
    retained_samples = 0
    verification_samples = 0
    scored_positions = 0
    halo = math.ceil(config.sample_rate / rate)
    for reference_start in starts:
        reference_count = min(window_samples, reference_total - reference_start)
        comparison_start = max(0, reference_start - margin_samples)
        comparison_end = min(
            comparison_total,
            reference_start + reference_count + margin_samples,
        )
        comparison_count = comparison_end - comparison_start
        if reference_count < 2 or comparison_count < 2:
            continue
        fft_points = _fft_size(reference_count + comparison_count - 1)
        total_fft_points += fft_points
        peak_fft_points = max(peak_fft_points, fft_points)
        retained_samples += reference_count + comparison_count
        windows.append(
            AudioWindowSpec(reference_start, reference_count, comparison_start, comparison_count)
        )
        if rate != config.sample_rate:
            requested_count = round(
                Fraction(reference_start + reference_count, rate) * config.sample_rate
            ) - round(Fraction(reference_start, rate) * config.sample_rate)
            pair_samples = 2 * requested_count + 2 * halo
            if pair_samples > _MAX_SCORING_PAIR_SAMPLES:
                return AudioAnalysisBudgetExceeded("requested_rate_scoring_exceeds_peak_budget")
            verification_samples += pair_samples
            scored_positions += verification_evaluations * min(
                requested_count, _MAX_SCORE_POSITIONS_PER_EVALUATION
            )
        scored_positions += discovery_evaluations * min(
            reference_count, comparison_count, _MAX_SCORE_POSITIONS_PER_EVALUATION
        )

    if config.minimum_valid_windows > len(windows):
        return AudioAnalysisBudgetExceeded("minimum_valid_windows_exceeds_work_budget")
    if total_fft_points > _FFT_WORK_BUDGET or retained_samples > _MAX_DISCOVERY_RETAINED_SAMPLES:
        return AudioAnalysisBudgetExceeded("planned_windows_exceed_work_budget")
    if verification_samples > _SCORING_SAMPLE_WORK_BUDGET:
        return AudioAnalysisBudgetExceeded("requested_rate_scoring_exceeds_total_budget")
    if scored_positions > _MAX_SCORED_POSITIONS:
        return AudioAnalysisBudgetExceeded("scoring_positions_exceed_work_budget")
    return AudioAnalysisPlan(
        sample_rate=rate,
        requested_sample_rate=config.sample_rate,
        windows=tuple(windows),
        peak_fft_points=peak_fft_points,
        total_fft_points=total_fft_points,
        discovery_retained_samples=retained_samples,
        verification_reserved_samples=verification_samples,
        score_evaluations_per_window=evaluations,
        scored_positions=scored_positions,
        reference_duration_samples=reference_total,
        comparison_duration_samples=comparison_total,
    )


def continuous_collection_argv(
    video_path: Path,
    stream: AudioStreamInfo,
    *,
    sample_rate: int,
    end_sample: int,
    channel_strategy: AlignmentChannelStrategy,
) -> list[str]:
    """Build the canonical origin-based, endpoint-limited FFmpeg recipe."""
    filters: list[str] = []
    if channel_strategy == "mono_downmix":
        channel_args = ["-ac", "1"]
    else:
        channel_args = []
        filters.append(_best_channel_audio_filter(stream))
    filters.extend((f"aresample={sample_rate}", f"atrim=end_sample={end_sample}"))
    return [
        "ffmpeg",
        "-i",
        str(video_path),
        "-map",
        f"0:a:{stream.audio_stream_index}",
        "-vn",
        *channel_args,
        "-af",
        ",".join(filters),
        "-f",
        "f32le",
        "-",
    ]


def _collection_record(
    result: ContinuousAudioCollection | ContinuousAudioCollectionFailure,
    *,
    phase: Literal["discovery", "verification"],
    role: Literal["reference", "comparison"],
    output_rate: int,
) -> AudioAlignmentCollectionRecord:
    facts = result.facts
    succeeded = isinstance(result, ContinuousAudioCollection)
    return AudioAlignmentCollectionRecord(
        phase=phase,
        role=role,
        output_rate=output_rate,
        requested_horizon=facts.planned_end_sample,
        emitted_sample_count=facts.emitted_sample_count,
        emitted_byte_count=facts.emitted_byte_count,
        retained_sample_count=facts.retained_sample_count,
        retained_byte_count=facts.retained_sample_count * _FLOAT32_BYTES,
        status="complete" if succeeded else "failed",
        end_category=result.end if succeeded else "not_observed",
        observed_eof_sample=result.observed_eof_sample if succeeded else None,
        elapsed_seconds=facts.elapsed_seconds,
        cleanup_failure_count=int(not result.cleanup.completed),
        failure_count=0 if succeeded else 1,
    )


def _collect_role(
    path: Path,
    stream: AudioStreamInfo,
    intervals: tuple[AudioSampleInterval, ...],
    *,
    phase: Literal["discovery", "verification"],
    role: Literal["reference", "comparison"],
    sample_rate: int,
    channel_strategy: AlignmentChannelStrategy,
    max_retained_samples: int,
    cancellation: threading.Event | None,
) -> tuple[ContinuousAudioCollection, AudioAlignmentCollectionRecord]:
    raise_if_alignment_cancelled(cancellation)
    horizon = max(interval.end_sample for interval in intervals)
    result = collect_continuous_audio(
        continuous_collection_argv(
            path,
            stream,
            sample_rate=sample_rate,
            end_sample=horizon,
            channel_strategy=channel_strategy,
        ),
        intervals,
        planned_end_sample=horizon,
        max_retained_samples=max_retained_samples,
        timeout_seconds=_FFMPEG_AUDIO_TIMEOUT_SECONDS,
        cancellation=cancellation,
    )
    summary = _collection_record(result, phase=phase, role=role, output_rate=sample_rate)
    if isinstance(result, ContinuousAudioCollectionFailure):
        error_type: type[AudioAlignmentError]
        if not result.cleanup.completed:
            error_type = AudioAlignmentCleanupError
        elif result.category == "cancelled":
            error_type = AudioAlignmentCancellationError
        else:
            error_type = AudioAlignmentError
        raise error_type(
            result.message,
            category=result.category,
            stage=phase,
            role=role,
            collection_summaries=(summary,),
        )
    return result, summary


def collect_discovery_phase(
    reference_path: Path,
    comparison_path: Path,
    reference_stream: AudioStreamInfo,
    comparison_stream: AudioStreamInfo,
    plan: AudioAnalysisPlan,
    *,
    channel_strategy: AlignmentChannelStrategy,
    cancellation: threading.Event | None = None,
) -> CollectedAudioPhase:
    """Collect all planned discovery intervals with two sequential decodes."""
    reference_intervals = tuple(
        AudioSampleInterval(spec.reference_start_sample, spec.reference_sample_count)
        for spec in plan.windows
    )
    comparison_intervals = tuple(
        AudioSampleInterval(spec.comparison_start_sample, spec.comparison_sample_count)
        for spec in plan.windows
    )
    reference_result, reference_summary = _collect_role(
        reference_path,
        reference_stream,
        reference_intervals,
        phase="discovery",
        role="reference",
        sample_rate=plan.sample_rate,
        channel_strategy=channel_strategy,
        max_retained_samples=plan.discovery_retained_samples,
        cancellation=cancellation,
    )
    try:
        comparison_result, comparison_summary = _collect_role(
            comparison_path,
            comparison_stream,
            comparison_intervals,
            phase="discovery",
            role="comparison",
            sample_rate=plan.sample_rate,
            channel_strategy=channel_strategy,
            max_retained_samples=plan.discovery_retained_samples,
            cancellation=cancellation,
        )
    except AudioAlignmentError as exc:
        exc.collection_summaries = (reference_summary, *exc.collection_summaries)
        raise
    return CollectedAudioPhase(
        windows=tuple(
            AudioWindow(
                reference=reference_interval.samples,
                comparison=comparison_interval.samples,
                reference_start_sample=reference_interval.start_sample,
                comparison_start_sample=comparison_interval.start_sample,
            )
            for reference_interval, comparison_interval in zip(
                reference_result.intervals, comparison_result.intervals, strict=True
            )
        ),
        summaries=(reference_summary, comparison_summary),
    )


def verification_specs(
    plan: AudioAnalysisPlan,
    coarse_offsets: tuple[tuple[int, Fraction], ...],
    *,
    reference_stream: AudioStreamInfo,
    comparison_stream: AudioStreamInfo,
    max_offset_seconds: float,
) -> tuple[AudioVerificationSpec, ...]:
    """Freeze requested-rate intervals and global hypotheses before verification I/O."""
    rate = plan.requested_sample_rate
    halo = math.ceil(rate / plan.sample_rate)
    requested_limit = int(max_offset_seconds * rate)
    reference_total = math.floor((reference_stream.timeline.duration or Fraction(0)) * rate)
    comparison_total = math.floor((comparison_stream.timeline.duration or Fraction(0)) * rate)
    frozen: list[AudioVerificationSpec] = []
    for window_index, coarse_offset in coarse_offsets:
        source = plan.windows[window_index]
        reference_start = round(Fraction(source.reference_start_sample * rate, plan.sample_rate))
        reference_end = round(
            Fraction(
                (source.reference_start_sample + source.reference_sample_count) * rate,
                plan.sample_rate,
            )
        )
        requested_offset = round(coarse_offset * rate / plan.sample_rate)
        comparison_core_start = reference_start - requested_offset
        comparison_start = max(0, comparison_core_start - halo)
        comparison_end = min(
            comparison_total, comparison_core_start + (reference_end - reference_start) + halo
        )
        reference_start = min(max(0, reference_start), reference_total)
        reference_end = min(max(reference_start, reference_end), reference_total)
        if reference_end <= reference_start or comparison_end <= comparison_start:
            continue
        frozen.append(
            AudioVerificationSpec(
                window_index=window_index,
                reference_start_sample=reference_start,
                reference_sample_count=reference_end - reference_start,
                comparison_start_sample=comparison_start,
                comparison_sample_count=comparison_end - comparison_start,
                global_lower_offset=max(-requested_limit, requested_offset - halo),
                global_upper_offset=min(requested_limit, requested_offset + halo),
            )
        )
    return tuple(frozen)


def collect_verification_phase(
    reference_path: Path,
    comparison_path: Path,
    reference_stream: AudioStreamInfo,
    comparison_stream: AudioStreamInfo,
    plan: AudioAnalysisPlan,
    specs: tuple[AudioVerificationSpec, ...],
    *,
    channel_strategy: AlignmentChannelStrategy,
    cancellation: threading.Event | None = None,
) -> CollectedAudioPhase:
    """Collect one frozen requested-rate phase with two sequential decodes."""
    reference_intervals = tuple(
        AudioSampleInterval(spec.reference_start_sample, spec.reference_sample_count)
        for spec in specs
    )
    comparison_intervals = tuple(
        AudioSampleInterval(spec.comparison_start_sample, spec.comparison_sample_count)
        for spec in specs
    )
    reference_result, reference_summary = _collect_role(
        reference_path,
        reference_stream,
        reference_intervals,
        phase="verification",
        role="reference",
        sample_rate=plan.requested_sample_rate,
        channel_strategy=channel_strategy,
        max_retained_samples=plan.verification_reserved_samples,
        cancellation=cancellation,
    )
    try:
        comparison_result, comparison_summary = _collect_role(
            comparison_path,
            comparison_stream,
            comparison_intervals,
            phase="verification",
            role="comparison",
            sample_rate=plan.requested_sample_rate,
            channel_strategy=channel_strategy,
            max_retained_samples=plan.verification_reserved_samples,
            cancellation=cancellation,
        )
    except AudioAlignmentError as exc:
        exc.collection_summaries = (reference_summary, *exc.collection_summaries)
        raise
    return CollectedAudioPhase(
        windows=tuple(
            AudioWindow(
                reference=reference_interval.samples,
                comparison=comparison_interval.samples,
                reference_start_sample=reference_interval.start_sample,
                comparison_start_sample=comparison_interval.start_sample,
            )
            for reference_interval, comparison_interval in zip(
                reference_result.intervals, comparison_result.intervals, strict=True
            )
        ),
        summaries=(reference_summary, comparison_summary),
    )
