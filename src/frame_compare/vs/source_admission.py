"""Check local video frame geometry before opening an L-SMASH source."""

from __future__ import annotations

import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired

from frame_compare.utils.canvas import MAX_CANVAS_PIXELS, validate_canvas_size
from frame_compare.utils.subproc import (
    PROBE_STDERR_BYTES,
    SubprocessOutputLimitExceeded,
    resolve_optional_executable,
    run_subprocess,
)
from frame_compare.vs.hdr_probe import (
    is_attached_picture,
    probe_video_streams,
    validate_video_stream_sizes,
)

_SCAN_TIMEOUT_SECONDS = 1800.0
_SCAN_STDOUT_BYTES = 128 * 1024 * 1024
_MAX_FRAME_RECORD_BYTES = 256
_FRAME_RECORD = re.compile(
    rb"frame\|stream_index=(\d+)\|width=(\d+)\|height=(\d+)"
    rb"\|crop_top=(\d+)\|crop_bottom=(\d+)\|crop_left=(\d+)\|crop_right=(\d+)(?:\|)?"
)
_MISSING_FRAME_DIMENSIONS = "Source video frame dimensions could not be verified"


def _source_stamp(path: Path) -> tuple[int, int, int, int, int]:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Source video must be a regular file")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


@dataclass(frozen=True, slots=True)
class SourceAdmission:
    streams: tuple[dict[str, object], ...]
    stamp: tuple[int, int, int, int, int]

    def verify(self, path: Path) -> None:
        if _source_stamp(path) != self.stamp:
            raise ValueError("Source video changed during admission")


class _FrameGeometryScan:
    def __init__(self, expected_streams: set[int]) -> None:
        self.expected_streams = expected_streams
        self.sizes: dict[int, tuple[int, int, int, int]] = {}
        self.pending = b""

    def feed(self, chunk: bytes) -> None:
        lines = (self.pending + chunk).split(b"\n")
        self.pending = lines.pop()
        if len(self.pending) > _MAX_FRAME_RECORD_BYTES:
            raise ValueError(_MISSING_FRAME_DIMENSIONS)
        for line in lines:
            self._check_frame(line.removesuffix(b"\r"))

    def _check_frame(self, line: bytes) -> None:
        match = _FRAME_RECORD.fullmatch(line) if len(line) <= _MAX_FRAME_RECORD_BYTES else None
        if match is None:
            raise ValueError(_MISSING_FRAME_DIMENSIONS)
        index, width, height, top, bottom, left, right = map(int, match.groups())
        if index not in self.expected_streams:
            raise ValueError("An unverified video stream appeared during the source frame scan")
        validate_canvas_size(width, height, label="Coded source video frame")
        visible_width, visible_height = width - left - right, height - top - bottom
        validate_canvas_size(visible_width, visible_height, label="Visible source video frame")
        size = width, height, visible_width, visible_height
        if self.sizes.setdefault(index, size) != size:
            raise ValueError("Source video frame dimensions change within a stream")

    def finish(self) -> None:
        if self.pending or self.sizes.keys() != self.expected_streams:
            raise ValueError(_MISSING_FRAME_DIMENSIONS)


def _scan_video_frames(path: Path, stream_indices: set[int], abort: Callable[[], bool]) -> None:
    scan = _FrameGeometryScan(stream_indices)
    try:
        result = run_subprocess(
            [
                "ffprobe",
                "-v",
                "error",
                "-max_pixels",
                str(MAX_CANVAS_PIXELS),
                "-err_detect",
                "explode",
                "-apply_cropping",
                "0",
                "-select_streams",
                "v",
                "-show_entries",
                "frame=stream_index,width,height,crop_top,crop_bottom,crop_left,crop_right:"
                "frame_side_data=",
                "-of",
                "compact=p=1:nk=0",
                str(path),
            ],
            timeout_seconds=_SCAN_TIMEOUT_SECONDS,
            abort=abort,
            stdout_consumer=scan.feed,
            max_stdout_bytes=_SCAN_STDOUT_BYTES,
            max_stderr_bytes=PROBE_STDERR_BYTES,
        )
    except TimeoutExpired as exc:
        raise ValueError("Source video frame scan timed out") from exc
    except SubprocessOutputLimitExceeded as exc:
        raise ValueError("Source video frame scan exceeded its output limit") from exc
    except CalledProcessError as exc:
        raise ValueError(_MISSING_FRAME_DIMENSIONS) from exc
    # ffprobe can report decoding errors and still exit successfully.
    if result.stderr:
        raise ValueError(_MISSING_FRAME_DIMENSIONS)
    scan.finish()


def admit_source(path: Path, *, abort_check: Callable[[], None]) -> SourceAdmission:
    """Check headers and every decoded video frame before the native indexer."""
    if resolve_optional_executable("ffprobe") is None:
        raise ValueError("ffprobe is required to verify source dimensions before decoding")

    def abort() -> bool:
        abort_check()
        return False

    path = path.absolute()
    stamp = _source_stamp(path)
    # The indexer can inspect cover art even though it is not a playable track.
    streams = probe_video_streams(path, abort=abort, include_attached=True)
    real_streams = [stream for stream in streams if not is_attached_picture(stream)]
    if not real_streams:
        raise ValueError("no verifiable video stream is supported")
    if len(real_streams) > 1:
        raise ValueError("multiple video streams are not supported")
    validate_video_stream_sizes(streams, require_dimensions=True)
    indices = {index for stream in streams if type(index := stream.get("index")) is int}
    if len(indices) != len(streams) or min(indices) < 0:
        raise ValueError("Source video stream indices could not be verified")
    admission = SourceAdmission(tuple(real_streams), stamp)
    admission.verify(path)
    _scan_video_frames(path, indices, abort)
    admission.verify(path)
    return admission


def bounded_decoder_options(options: str | None = None) -> str:
    """Supply an owned pixel ceiling to the L-SMASH playback decoder."""
    limit = f"max_pixels={MAX_CANVAS_PIXELS}"
    if not options or options.isspace():
        return limit
    # The pinned plugin uses av_dict_parse_string with "=" and space separators.
    # Admit complete pairs so quoting, escaping or a bare key cannot absorb the
    # final limit. av_dict_set replaces duplicates, including case variants.
    pair = r"[A-Za-z0-9_-]+=(?:[^ \t\r\n'\\\x00]|\\[^\x00]|'[^'\x00]*')+"
    if re.fullmatch(rf" *{pair}(?: +{pair})* *", options) is None:
        raise ValueError("LWLibavSource ff_options must contain complete key=value pairs")
    return f"{options} {limit}"
