"""FFprobe-backed HDR signal metadata extraction."""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import cast

from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.types import HDRMetadata

_FFPROBE_TIMEOUT_SECONDS = 15.0
_PRIMARIES_BY_NAME = {"bt709": 1, "bt2020": 9}
_TRANSFER_BY_NAME = {"bt709": 1, "smpte2084": 16, "arib-std-b67": 18}
_MATRIX_BY_NAME = {"bt709": 1, "bt2020nc": 9, "bt2020c": 10}


def probe_video_streams(video: Path) -> list[dict[str, object]]:
    """List real video streams, excluding attached cover pictures."""
    argv = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v",
        "-show_entries",
        "stream=color_transfer,color_primaries,color_space:stream_disposition=attached_pic",
        "-of",
        "json",
        str(video),
    ]
    try:
        proc = run_subprocess(argv, timeout_seconds=_FFPROBE_TIMEOUT_SECONDS)
    except FileNotFoundError as exc:
        raise FFmpegNotFoundError() from exc
    except TimeoutExpired as exc:
        raise FFmpegError("ffprobe timed out while probing hdr", 124) from exc
    except CalledProcessError as exc:
        raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc

    try:
        payload: object = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise FFmpegError("ffprobe returned invalid json", proc.returncode) from exc

    if not isinstance(payload, dict):
        raise FFmpegError("ffprobe returned invalid json object", proc.returncode)
    payload_dict = cast(dict[str, object], payload)
    streams_obj = payload_dict.get("streams")
    if not isinstance(streams_obj, list):
        return []
    streams: list[dict[str, object]] = []
    for stream_obj in cast(list[object], streams_obj):
        if not isinstance(stream_obj, dict):
            continue
        stream = cast(dict[str, object], stream_obj)
        disposition = stream.get("disposition")
        if (
            isinstance(disposition, dict)
            and cast(dict[str, object], disposition).get("attached_pic") == 1
        ):
            continue
        streams.append(stream)
    return streams


def probe_hdr_metadata(
    video: Path, *, streams: list[dict[str, object]] | None = None
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
