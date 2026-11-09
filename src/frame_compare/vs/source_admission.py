"""Check local video geometry before opening an L-SMASH source."""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Callable, Set
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import cast

from frame_compare.utils.canvas import MAX_CANVAS_PIXELS, validate_canvas_size
from frame_compare.utils.subproc import (
    PROBE_STDERR_BYTES,
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
_SCAN_TIMEOUT_SECONDS = 1800.0
_SCAN_STDOUT_BYTES = 128 * 1024 * 1024
_MAX_FRAME_RECORD_BYTES = 256
_FRAME_RECORD = re.compile(
    rb"frame\|stream_index=(\d+)\|width=(\d+)\|height=(\d+)"
    rb"\|crop_top=(\d+)\|crop_bottom=(\d+)\|crop_left=(\d+)\|crop_right=(\d+)(?:\|)?"
)
_MISSING_FRAME_DIMENSIONS = "Source video frame dimensions could not be verified"


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int
    change_time: int


def source_identity(path: Path) -> SourceIdentity:
    if os.name == "nt":
        with path.open("rb") as handle:
            info = os.fstat(handle.fileno())
            change_time = _windows_change_time(handle.fileno())
    else:
        info = path.stat()
        change_time = info.st_ctime_ns
    return SourceIdentity(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, change_time)


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
    return basic.change_time


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
    stamp: SourceIdentity
    stream_indices: frozenset[int]
    executable: Path
    probe_stamp: SourceIdentity | None
    geometry_probe_token: str | None

    def verify(self, path: Path) -> None:
        if _source_stamp(path) != self.stamp:
            raise ValueError("Source video changed during admission")
        if self.probe_stamp is not None and _probe_stamp(self.executable) != self.probe_stamp:
            raise ValueError("FFprobe executable changed during source admission")

    def scan(self, path: Path, *, abort_check: Callable[[], None]) -> None:
        def abort() -> bool:
            abort_check()
            return False

        try:
            self.verify(path)
            _scan_video_frames(path.absolute(), self.stream_indices, abort, self.executable)
            self.verify(path)
            abort_check()
        except (OSError, ValueError) as error:
            raise SourceGeometryError(str(error)) from error


class SourceGeometryError(ValueError):
    """Complete validation failed before native geometry handling."""


def _probe_stamp(executable: Path) -> SourceIdentity | None:
    try:
        return source_identity(executable)
    except OSError:
        # The probe can run, but its result cannot establish reusable authority.
        return None


def _probe_token(
    executable: Path, stamp: SourceIdentity | None, payload: dict[str, object]
) -> str | None:
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


def _scan_video_frames(
    path: Path, stream_indices: Set[int], abort: Callable[[], bool], executable: Path
) -> None:
    scan = _FrameGeometryScan(stream_indices)
    try:
        result = run_subprocess(
            [
                str(executable),
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
    if Path(result.args[0]).resolve() != executable:
        raise ValueError("FFprobe executable changed during source admission")
    # ffprobe can report decoding errors and still exit successfully.
    if result.stderr:
        raise ValueError(_MISSING_FRAME_DIMENSIONS)
    scan.finish()


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
    real_streams = [stream for stream in streams if not is_attached_picture(stream)]
    if not real_streams:
        raise ValueError("no verifiable video stream is supported")
    if len(real_streams) > 1:
        raise ValueError("multiple video streams are not supported")
    validate_video_stream_sizes(streams, require_dimensions=True)
    for stream in streams:
        width, height = stream.get("coded_width"), stream.get("coded_height")
        if type(width) is not int or type(height) is not int:
            raise ValueError("Coded source video dimensions could not be verified before decoding")
        validate_canvas_size(width, height, label="Coded source video")
    indices = frozenset(index for stream in streams if type(index := stream.get("index")) is int)
    if len(indices) != len(streams) or min(indices) < 0:
        raise ValueError("Source video stream indices could not be verified")
    admission = SourceAdmission(
        real_streams[0],
        stamp,
        indices,
        executable,
        probe_stamp,
        _probe_token(executable, probe_stamp, payload),
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
