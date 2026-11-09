"""FFprobe-backed HDR signal metadata extraction."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import cast

from frame_compare.utils.canvas import MAX_CANVAS_PIXELS, validate_canvas_size
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import (
    PROBE_STDERR_BYTES,
    PROBE_STDOUT_BYTES,
    SubprocessOutputLimitExceeded,
    run_subprocess,
)
from frame_compare.vs.types import HDRMetadata

_FFPROBE_TIMEOUT_SECONDS = 15.0
_VIDEO_STREAM_ENTRIES = (
    "stream=width,height,color_transfer,color_primaries,color_space:stream_disposition=attached_pic"
)
_PRIMARIES_BY_NAME = {"bt709": 1, "bt2020": 9}
_TRANSFER_BY_NAME = {"bt709": 1, "smpte2084": 16, "arib-std-b67": 18}
_MATRIX_BY_NAME = {"bt709": 1, "bt2020nc": 9, "bt2020c": 10}


def probe_video_streams(
    video: Path,
    *,
    abort: Callable[[], bool] | None = None,
) -> list[dict[str, object]]:
    """List video streams, excluding attached cover pictures."""
    streams, _ = _probe_video_streams(video, abort=abort)
    return streams


def probe_admission_headers(
    video: Path, executable: Path, *, abort: Callable[[], bool]
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Get video headers and the identity reported by the same FFprobe invocation."""
    return _probe_video_streams(video, abort=abort, admission_probe=executable)


def _probe_video_streams(
    video: Path,
    *,
    abort: Callable[[], bool] | None,
    admission_probe: Path | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    entries = _VIDEO_STREAM_ENTRIES
    if admission_probe is not None:
        entries = entries.replace("stream=", "stream=index,coded_width,coded_height,")
    argv = [
        str(admission_probe) if admission_probe is not None else "ffprobe",
        "-v",
        "error",
        "-max_pixels",
        str(MAX_CANVAS_PIXELS),
        "-select_streams",
        "v",
        *(["-show_program_version", "-show_library_versions"] if admission_probe else []),
        "-show_entries",
        entries,
        "-of",
        "json",
        str(video),
    ]
    try:
        proc = run_subprocess(
            argv,
            timeout_seconds=_FFPROBE_TIMEOUT_SECONDS,
            abort=abort,
            max_stdout_bytes=PROBE_STDOUT_BYTES,
            max_stderr_bytes=PROBE_STDERR_BYTES,
        )
    except FileNotFoundError as exc:
        raise FFmpegNotFoundError() from exc
    except TimeoutExpired as exc:
        raise FFmpegError("ffprobe timed out while probing hdr", 124) from exc
    except CalledProcessError as exc:
        raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc
    except SubprocessOutputLimitExceeded as exc:
        raise FFmpegError(str(exc), 1) from exc

    if admission_probe is not None and Path(proc.args[0]).resolve() != admission_probe:
        raise ValueError("FFprobe executable changed during source admission")

    try:
        payload: object = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise FFmpegError("ffprobe returned invalid json", proc.returncode) from exc

    if not isinstance(payload, dict):
        raise FFmpegError("ffprobe returned invalid json object", proc.returncode)
    payload_dict = cast(dict[str, object], payload)
    streams_obj = payload_dict.get("streams")
    if not isinstance(streams_obj, list):
        return [], payload_dict
    streams: list[dict[str, object]] = []
    for stream_obj in cast(list[object], streams_obj):
        if not isinstance(stream_obj, dict):
            continue
        stream = cast(dict[str, object], stream_obj)
        if admission_probe is None and is_attached_picture(stream):
            continue
        streams.append(stream)
    return streams, payload_dict


def is_attached_picture(stream: dict[str, object]) -> bool:
    disposition = stream.get("disposition")
    return (
        isinstance(disposition, dict)
        and cast(dict[str, object], disposition).get("attached_pic") == 1
    )


def validate_video_stream_sizes(
    streams: list[dict[str, object]], *, require_dimensions: bool = False
) -> None:
    """Reject oversized dimensions advertised by video headers before decoding."""
    for stream in streams:
        width, height = stream.get("width"), stream.get("height")
        if type(width) is int and type(height) is int:
            validate_canvas_size(width, height, label="Source video")
        elif require_dimensions:
            raise ValueError("Source video dimensions could not be verified before decoding")


def probe_hdr_metadata(
    video: Path, *, streams: Sequence[dict[str, object]] | None = None
) -> HDRMetadata | None:
    """Return color metadata from the first real video stream, when available."""
    if streams is None:
        streams = probe_video_streams(video)
    if not streams:
        return None
    stream = streams[0]

    transfer_raw = _normalized_string(stream.get("color_transfer"))
    primaries_raw = _normalized_string(stream.get("color_primaries"))
    matrix_raw = _normalized_string(stream.get("color_space"))
    color_primaries = _PRIMARIES_BY_NAME.get(primaries_raw, 2)
    transfer = _TRANSFER_BY_NAME.get(transfer_raw, 2)
    matrix = _MATRIX_BY_NAME.get(matrix_raw, 2)

    if color_primaries == 2 and transfer == 2 and matrix == 2:
        return None

    return HDRMetadata(
        mastering_display=None,
        max_cll=None,
        max_fall=None,
        color_primaries=color_primaries,
        transfer=transfer,
        matrix=matrix,
    )


def _normalized_string(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.casefold().strip()
