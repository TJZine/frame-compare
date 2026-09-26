"""ffprobe stream probing and FFmpeg recipes for whole-track audio alignment."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import Any, cast

from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentChannelStrategy
from frame_compare.utils.alignment_evidence import (
    AUDIO_ANALYSIS_SAMPLE_RATE,
    AudioDurationBasis,
    AudioMetadataMatch,
    AudioPairSide,
    AudioStartBasis,
    SelectedAudioStreamEvidence,
)
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import run_subprocess

_FFPROBE_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class AudioStreamTimeline:
    """Selected stream timing normalized to its own zero-based audio timeline."""

    start_time: Fraction
    duration: Fraction | None
    time_base: Fraction | None
    duration_basis: AudioDurationBasis
    input_start_time: Fraction = Fraction(0)
    start_time_basis: AudioStartBasis = "default_zero"
    input_start_time_basis: AudioStartBasis = "default_zero"


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
class VideoStreamStart:
    """Start time of the first non-attached-pic video stream (A5 compensation)."""

    start_time: Fraction
    basis: AudioStartBasis


@dataclass(frozen=True)
class AudioStreamSelection:
    """Resolved audio stream plus the companion video start for A5 compensation."""

    stream: AudioStreamInfo
    video_start: VideoStreamStart


@dataclass(frozen=True)
class _ProbedStreams:
    audio: tuple[AudioStreamInfo, ...]
    video_start: VideoStreamStart


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
    input_start_time_basis: AudioStartBasis,
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
    duration_basis: AudioDurationBasis = "unavailable"
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


def _parse_video_start(stream_obj: object) -> VideoStreamStart | None:
    """Return the start of the first non-attached-pic video stream, if present."""
    if not isinstance(stream_obj, dict):
        return None
    stream = cast(dict[str, object], stream_obj)
    if stream.get("codec_type") != "video":
        return None
    disposition_obj = stream.get("disposition", {})
    disposition_dict = (
        cast(dict[str, object], disposition_obj) if isinstance(disposition_obj, dict) else {}
    )
    if _parse_flag(disposition_dict.get("attached_pic")):
        return None
    parsed_start_time = _parse_optional_fraction(stream.get("start_time"))
    if parsed_start_time is None:
        return VideoStreamStart(start_time=Fraction(0), basis="default_zero")
    return VideoStreamStart(start_time=parsed_start_time, basis="metadata")


def _probe_streams(video_path: Path) -> _ProbedStreams:
    """Probe audio streams and the companion video start in one ffprobe call."""
    payload = _load_ffprobe_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "stream=index,codec_type,codec_name,channels,channel_layout,sample_rate,"
                "start_time,duration,duration_ts,time_base:"
                "stream_disposition=default,original,comment,attached_pic:"
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

    audio: list[AudioStreamInfo] = []
    video_start = VideoStreamStart(start_time=Fraction(0), basis="default_zero")
    video_found = False
    for raw_item in stream_items:
        if not isinstance(raw_item, dict):
            raise FFmpegError(f"ffprobe returned invalid stream data for {video_path.name}", 0)
        stream_item = cast(dict[str, Any], raw_item)
        if stream_item.get("codec_type") == "audio":
            audio.append(
                _parse_audio_stream(
                    stream_item,
                    audio_stream_index=len(audio),
                    video_path=video_path,
                    input_start_time=input_start_time,
                    input_start_time_basis=(
                        "metadata" if parsed_input_start_time is not None else "default_zero"
                    ),
                )
            )
        elif not video_found:
            parsed = _parse_video_start(stream_item)
            if parsed is not None:
                video_start = parsed
                video_found = True
    if not audio:
        raise AudioAlignmentError(f"no audio streams found in {video_path.name}")
    return _ProbedStreams(audio=tuple(audio), video_start=video_start)


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
    streams: tuple[AudioStreamInfo, ...],
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
) -> AudioStreamSelection:
    """Choose the reference anchor stream deterministically from ffprobe metadata."""
    probed = _probe_streams(video_path)
    if stream_override is not None:
        stream = _select_audio_stream_override(
            probed.audio,
            video_path=video_path,
            stream_override=stream_override,
        )
    else:
        stream = min(probed.audio, key=_reference_stream_sort_key)
    return AudioStreamSelection(stream=stream, video_start=probed.video_start)


def select_matching_audio_stream(
    video_path: Path,
    *,
    reference_stream: AudioStreamInfo,
    stream_override: int | None = None,
) -> AudioStreamSelection:
    """Choose the comparison stream that best matches the selected reference stream."""
    probed = _probe_streams(video_path)
    if stream_override is not None:
        stream = _select_audio_stream_override(
            probed.audio,
            video_path=video_path,
            stream_override=stream_override,
        )
    else:
        stream = min(
            probed.audio,
            key=lambda candidate: _comparison_stream_sort_key(reference_stream, candidate),
        )
    return AudioStreamSelection(stream=stream, video_start=probed.video_start)


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
    role: AudioPairSide,
    source_identity_digest: str,
    explicit_override: bool,
    video_start: VideoStreamStart,
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
        video_start_num=video_start.start_time.numerator,
        video_start_den=video_start.start_time.denominator,
        video_start_basis=video_start.basis,
    )


def normalized_extraction_recipe() -> str:
    """Describe extraction without retaining media paths or a concrete command line."""
    return (
        "ffmpeg -i <role_input> -map 0:a:<selected_ordinal> -vn "
        "[channel] -af <channel>,aresample=8000 -f f32le -"
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


def collection_argv(
    video_path: Path,
    stream: AudioStreamInfo,
    *,
    channel_strategy: AlignmentChannelStrategy,
) -> list[str]:
    """Build the canonical whole-track 8 kHz mono float32 FFmpeg recipe."""
    filters: list[str] = []
    if channel_strategy == "mono_downmix":
        channel_args = ["-ac", "1"]
    else:
        channel_args = []
        filters.append(_best_channel_audio_filter(stream))
    filters.append(f"aresample={AUDIO_ANALYSIS_SAMPLE_RATE}")
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
