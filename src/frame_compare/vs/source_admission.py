"""Check local video geometry before opening an L-SMASH source."""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Callable, Set
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from subprocess import CalledProcessError
from time import monotonic, sleep, time_ns
from typing import cast

from frame_compare.utils.canvas import MAX_CANVAS_PIXELS, validate_canvas_size
from frame_compare.utils.subproc import (
    PROBE_STDERR_BYTES,
    SubprocessAborted,
    SubprocessOutputLimitExceeded,
    resolve_optional_executable,
    run_subprocess,
)
from frame_compare.vs.hdr_probe import (
    is_attached_picture,
    probe_admission_headers,
    validate_video_stream_sizes,
)

_DECODER_PAIR = re.compile(r"[A-Za-z0-9_-]+=(?:[^ \t\r\n'\\\x00]|\\[^\x00]|'[^'\x00]*')+")
_SCAN_STALL_SECONDS = 120.0
_SCAN_STDOUT_BYTES = 128 * 1024 * 1024
_MAX_FRAME_RECORD_BYTES = 256
_FRAME_RECORD = re.compile(
    rb"frame\|stream_index=(\d+)\|width=(\d+)\|height=(\d+)"
    rb"\|crop_top=(\d+)\|crop_bottom=(\d+)\|crop_left=(\d+)\|crop_right=(\d+)(?:\|)?"
)
# libavutil's av_image_check_size2 can reject a picture before ffprobe reports it.
# Match the message body regardless of the logger's prefix or color formatting.
_PROBE_PIXEL_LIMIT_FAILURE = re.compile(
    rb"Picture size [0-9]+x[0-9]+ exceeds specified max pixel count [0-9]+,"
    rb" see the documentation if you wish to increase it\b"
)
_MISSING_FRAME_DIMENSIONS = "Source video frame dimensions could not be verified"
# Match complete FFprobe demuxer names. These ordinary containers read a single
# file with the packaged defaults, including MOV with external tracks disabled.
_SINGLE_FILE_FORMAT_NAMES = frozenset({"avi", "matroska,webm", "mov,mp4,m4a,3gp,3g2,mj2", "mpegts"})
_NATIVE_FORMAT_NAMES = _SINGLE_FILE_FORMAT_NAMES | {"mpegvideo"}
# NTFS takes change times from the system clock, which advances once per timer
# interrupt (at most every 15.625 ms). Linux filesystems without multigrain
# timestamps use the once-per-jiffy clock (at most every 10 ms). Two changes
# within one of those intervals can share a change time. Twice the longest
# interval guarantees that clock has moved past a change time.
_CHANGE_TIME_SETTLE_NS = 32_000_000
# FILETIME counts 100 ns intervals from 1601-01-01; this value is 1970-01-01.
_FILETIME_UNIX_EPOCH = 116_444_736_000_000_000


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int
    change_time: int  # Nanoseconds since the Unix epoch.


def source_identity(path: Path) -> SourceIdentity:
    """Return a live file identity that no later change to the file can share.

    The identity is returned only once the clock that stamps change times has
    moved past its change time. Any later data or metadata change then records a
    newer change time, even when it restores the file's size and modification time.
    """
    if os.name == "nt":
        with path.open("rb") as handle:
            info = os.fstat(handle.fileno())
            change_time = _windows_change_time(handle.fileno())
    else:
        info = path.stat()
        change_time = info.st_ctime_ns
    _wait_for_distinct_change_time(change_time)
    return SourceIdentity(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, change_time)


def _wait_for_distinct_change_time(change_time: int) -> None:
    pending_ns = change_time + _CHANGE_TIME_SETTLE_NS - time_ns()
    if pending_ns > _CHANGE_TIME_SETTLE_NS:
        # Until the clock passes this change time, a later change could reuse it.
        raise OSError("Source change time is ahead of the system clock")
    if pending_ns > 0:
        sleep(pending_ns / 1_000_000_000)


def _windows_change_time(fd: int) -> int:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _FileBasicInfo(ctypes.Structure):
        _fields_ = [
            ("creation_time", ctypes.c_longlong),
            ("last_access_time", ctypes.c_longlong),
            ("last_write_time", ctypes.c_longlong),
            ("change_time", ctypes.c_longlong),
            ("file_attributes", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_volume_info = kernel32.GetVolumeInformationByHandleW
    get_volume_info.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.LPDWORD,
        wintypes.LPDWORD,
        wintypes.LPDWORD,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    get_volume_info.restype = wintypes.BOOL
    get_file_info = kernel32.GetFileInformationByHandleEx
    get_file_info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    get_file_info.restype = wintypes.BOOL

    handle = msvcrt.get_osfhandle(fd)
    filesystem = ctypes.create_unicode_buffer(261)  # MAX_PATH + 1
    if not get_volume_info(handle, None, 0, None, None, None, filesystem, len(filesystem)):
        raise ctypes.WinError(ctypes.get_last_error())
    # Filesystems without NTFS change-time semantics use the cache-free path.
    if filesystem.value != "NTFS":
        raise OSError("Managed source indexes on Windows require NTFS change time")
    basic = _FileBasicInfo()
    if not get_file_info(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic)):  # FileBasicInfo
        raise ctypes.WinError(ctypes.get_last_error())
    if basic.change_time <= 0:
        raise OSError("Source change time is unavailable")
    return (basic.change_time - _FILETIME_UNIX_EPOCH) * 100


def _source_stamp(path: Path) -> SourceIdentity:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Source video must be a regular file")
    if os.name == "nt":
        try:
            return source_identity(path)
        except OSError:
            # Non-NTFS sources can be opened privately, but cannot reuse an index.
            pass
    return SourceIdentity(
        info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    )


@dataclass(frozen=True, slots=True)
class SourceAdmission:
    video_stream: dict[str, object]
    format_name: str
    stamp: SourceIdentity
    stream_indices: frozenset[int]
    executable: Path
    probe_stamp: SourceIdentity | None
    geometry_probe_token: str | None
    _scan_complete: bool = field(default=False, init=False, repr=False, compare=False)

    def verify(self, path: Path) -> None:
        if _source_stamp(path) != self.stamp:
            raise ValueError("Source video changed during admission")
        if self.probe_stamp is not None and _probe_stamp(self.executable) != self.probe_stamp:
            raise ValueError("FFprobe executable changed during source admission")

    def scan(self, path: Path, *, abort_check: Callable[[], None]) -> None:
        def abort() -> bool:
            abort_check()
            return False

        stderr = b""
        try:
            abort_check()
            self.verify(path)
            if self._scan_complete:
                return
            stderr = _scan_video_frames(
                path.absolute(), self.stream_indices, abort, self.executable
            )
            self.verify(path)
            abort_check()
        except (OSError, ValueError) as error:
            raise SourceGeometryError(_scan_refusal(str(error), stderr)) from error
        object.__setattr__(self, "_scan_complete", True)


class SourceGeometryError(ValueError):
    """Complete validation failed before native geometry handling."""


def _probe_stamp(executable: Path) -> SourceIdentity | None:
    try:
        return source_identity(executable)
    except OSError:
        # The probe can run, but its result cannot establish reusable authority.
        return None


def _probe_token(
    executable: Path, stamp: SourceIdentity | None, payload: dict[str, object], format_name: str
) -> str | None:
    if format_name not in _SINGLE_FILE_FORMAT_NAMES:
        # Admitted elementary MPEG-2 retains a full scan and private index per open.
        return None
    program = payload.get("program_version")
    libraries = payload.get("library_versions")
    if (
        stamp is None
        or not isinstance(program, dict)
        or not program
        or not isinstance(libraries, list)
        or not libraries
    ):
        return None
    identity = (
        os.path.normcase(executable),
        asdict(stamp),
        cast(dict[str, object], program),
        cast(list[object], libraries),
    )
    return sha256(json.dumps(identity, sort_keys=True).encode("ascii")).hexdigest()


class _FrameGeometryScan:
    def __init__(self, expected_streams: Set[int]) -> None:
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


def _scan_refusal(reason: str, stderr: bytes) -> str:
    excerpt = stderr[:512].decode(errors="replace").strip()
    return f"{reason}: {excerpt}" if excerpt else reason


def _scan_video_frames(
    path: Path, stream_indices: Set[int], abort: Callable[[], bool], executable: Path
) -> bytes:
    scan = _FrameGeometryScan(stream_indices)
    last_stdout = monotonic()
    refusal: str | None = None

    def feed(chunk: bytes) -> None:
        nonlocal last_stdout, refusal
        last_stdout = monotonic()
        try:
            scan.feed(chunk)
        except ValueError as exc:
            refusal = str(exc)
            raise SubprocessAborted() from exc

    def abort_if_stalled() -> bool:
        nonlocal refusal
        if abort():
            return True
        if monotonic() - last_stdout >= _SCAN_STALL_SECONDS:
            refusal = (
                f"Source video frame scan made no progress for {_SCAN_STALL_SECONDS:g} seconds"
            )
            return True
        return False

    try:
        result = run_subprocess(
            [
                str(executable),
                "-v",
                "error",
                "-max_pixels",
                str(MAX_CANVAS_PIXELS),
                "-threads",
                "0",
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
            abort=abort_if_stalled,
            stdout_consumer=feed,
            max_stdout_bytes=_SCAN_STDOUT_BYTES,
            max_stderr_bytes=PROBE_STDERR_BYTES,
        )
    except SubprocessAborted as exc:
        if refusal is None:
            raise
        raise ValueError(_scan_refusal(refusal, exc.stderr)) from exc
    except SubprocessOutputLimitExceeded as exc:
        raise ValueError(
            _scan_refusal("Source video frame scan exceeded its output limit", exc.stderr)
        ) from exc
    except CalledProcessError as exc:
        raise ValueError(_scan_refusal(_MISSING_FRAME_DIMENSIONS, exc.stderr)) from exc
    try:
        if Path(result.args[0]).resolve() != executable:
            raise ValueError("FFprobe executable changed during source admission")
        if _PROBE_PIXEL_LIMIT_FAILURE.search(result.stderr):
            raise ValueError("FFprobe rejected a source video picture at its pixel limit")
        scan.finish()
    except (OSError, ValueError) as exc:
        raise ValueError(_scan_refusal(str(exc), result.stderr)) from exc
    return result.stderr


def admit_source(path: Path, *, abort_check: Callable[[], None]) -> SourceAdmission:
    """Check stream headers before the native indexer."""
    resolved = resolve_optional_executable("ffprobe")
    if resolved is None:
        raise ValueError("ffprobe is required to verify source dimensions before decoding")
    executable = Path(resolved).resolve(strict=True)
    probe_stamp = _probe_stamp(executable)

    def abort() -> bool:
        abort_check()
        return False

    path = path.absolute()
    stamp = _source_stamp(path)
    # The indexer can inspect cover art even though it is not a playable track.
    streams, payload = probe_admission_headers(path, executable, abort=abort)
    format_info = payload.get("format")
    format_name = (
        cast(dict[str, object], format_info).get("format_name")
        if isinstance(format_info, dict)
        else None
    )
    if not isinstance(format_name, str) or format_name not in _NATIVE_FORMAT_NAMES:
        raise ValueError("Source container format is not supported for native decoding")
    real_streams = [stream for stream in streams if not is_attached_picture(stream)]
    if not real_streams:
        raise ValueError("no verifiable video stream is supported")
    if len(real_streams) > 1:
        raise ValueError("multiple video streams are not supported")
    video_stream = real_streams[0]
    validate_video_stream_sizes(streams, require_dimensions=True)
    coded_header_known = True
    for stream in streams:
        width, height = stream.get("coded_width"), stream.get("coded_height")
        if type(width) is not int or type(height) is not int:
            raise ValueError("Coded source video dimensions could not be verified before decoding")
        if stream is video_stream and (width, height) == (0, 0):
            # Elementary streams can report unknown coded dimensions until decoding.
            # Without a reuse token both native callers must scan before a private open.
            coded_header_known = False
            continue
        validate_canvas_size(width, height, label="Coded source video")
    indices = frozenset(index for stream in streams if type(index := stream.get("index")) is int)
    if len(indices) != len(streams) or min(indices) < 0:
        raise ValueError("Source video stream indices could not be verified")
    admission = SourceAdmission(
        video_stream,
        format_name,
        stamp,
        indices,
        executable,
        probe_stamp,
        _probe_token(executable, probe_stamp, payload, format_name) if coded_header_known else None,
    )
    admission.verify(path)
    return admission


def bounded_decoder_options(options: str | None = None) -> str:
    """Supply an owned pixel ceiling to the L-SMASH playback decoder."""
    limit = f"max_pixels={MAX_CANVAS_PIXELS}"
    if not options or options.isspace():
        return limit
    # FFmpeg's dictionary parser stops at the first invalid or empty pair.
    # Validate complete pairs and drop caller-supplied versions of the limit.
    pair = _DECODER_PAIR.pattern
    if re.fullmatch(rf" *{pair}(?: +{pair})* *", options) is None:
        raise ValueError("LWLibavSource ff_options must contain complete key=value pairs")
    forwarded: list[str] = []
    for match in _DECODER_PAIR.finditer(options):
        option = match.group()
        key, _, value = option.partition("=")
        if re.fullmatch(r"(?:'')+", value) is not None:
            raise ValueError("LWLibavSource ff_options must contain complete key=value pairs")
        if key.lower() != "max_pixels":
            forwarded.append(option)
    forwarded.append(limit)
    return " ".join(forwarded)
