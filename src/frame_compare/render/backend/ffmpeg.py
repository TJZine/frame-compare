"""FFmpeg-based frame extraction and probing runtime adapter."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from signal import SIGINT
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Protocol, cast

from frame_compare.render.backend._ffmpeg_frame import (
    build_extract_frame_argv,
    build_extract_frames_argv,
)
from frame_compare.render.errors import FrameExtractionError
from frame_compare.utils.cancellation import is_cancelling, raise_if_cancelling
from frame_compare.utils.canvas import MAX_CANVAS_PIXELS, validate_canvas_size
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.media_facts import PictureType, RenderedFrameFacts, normalize_picture_type
from frame_compare.utils.subproc import (
    SubprocessAborted,
    SubprocessOutputLimitExceeded,
    resolve_executable,
    run_subprocess,
)
from frame_compare.vs.hdr_probe import (
    is_attached_picture,
    probe_hdr_metadata,
    probe_video_streams,
)
from frame_compare.vs.types import HDRMetadata

if TYPE_CHECKING:
    from frame_compare.render.geometry import RenderGeometryPlan
    from frame_compare.utils.media_facts import SourceSignalFacts


_H273_UNSPECIFIED = 2
_WINDOWS_STATUS_CONTROL_C_EXIT = 0xC000013A


class FFmpegRunner(Protocol):
    """Protocol for FFmpeg-based frame extraction and probing."""

    def extract_frame(
        self,
        video: Path,
        frame_num: int,
        output: Path,
        *,
        geometry_plan: RenderGeometryPlan | None = None,
        source_signal: SourceSignalFacts | None = None,
    ) -> RenderedFrameFacts:
        """Extract a frame and return facts from that same exact-frame process."""
        ...

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        """Probe HDR metadata for a video.

        Returns:
            HDRMetadata if valid color primaries and transfer characteristics are present,
            or None if they are missing or unspecified (mapped to 2).
            Returns an HDRMetadata object even for SDR streams (e.g., BT.709) if the
            metadata is explicitly available.
        """
        ...


class DefaultFFmpegRunner:
    """Default FFmpeg runner for dependency injection in orchestration."""

    _FFMPEG_TIMEOUT_SECONDS = 30.0
    _SINGLE_FRAME_STDERR_BYTES = 128 * 1024
    # Batch showinfo retains one selected-frame receipt per requested frame.
    _BATCH_STDERR_BYTES = 2 * 1024 * 1024

    def __init__(self, extraction_timeout_seconds: float = _FFMPEG_TIMEOUT_SECONDS) -> None:
        self._extraction_timeout_seconds = extraction_timeout_seconds

    def extract_frame(
        self,
        video: Path,
        frame_num: int,
        output: Path,
        *,
        geometry_plan: RenderGeometryPlan | None = None,
        source_signal: SourceSignalFacts | None = None,
    ) -> RenderedFrameFacts:
        self._validate_current_geometry(
            video, frame_num, geometry_plan=geometry_plan, abort=is_cancelling
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".frame-compare-ffmpeg-", dir=output.parent) as temp_dir:
            staged_path = Path(temp_dir) / "frame.png"
            argv = build_extract_frame_argv(
                video=video,
                frame_num=frame_num,
                output=staged_path,
                overwrite=True,
                geometry_plan=geometry_plan,
                source_signal=source_signal,
            )
            completed = self._run_extraction(
                argv,
                timeout_message="ffmpeg timed out while extracting frame",
                stderr_limit=self._SINGLE_FRAME_STDERR_BYTES,
            )
            _validate_showinfo_timeline(completed.stderr, video, frame_num)
            if not staged_path.is_file() or staged_path.stat().st_size == 0:
                raise FrameExtractionError(frame_num, str(video), reason="FFmpeg produced no image")
            staged_path.replace(output)
        return RenderedFrameFacts(
            source_frame=frame_num,
            picture_type=parse_showinfo_picture_type(completed.stderr),
        )

    def extract_frames(
        self,
        video: Path,
        frame_nums: Sequence[int],
        output_dir: Path,
        *,
        geometry_plan: RenderGeometryPlan | None = None,
        source_signal: SourceSignalFacts | None = None,
        abort: Callable[[], bool] | None = None,
    ) -> list[RenderedFrameFacts]:
        """Extract ordered frames in one decode pass into numbered staging files."""
        if not frame_nums:
            raise ValueError("frame_nums must not be empty")
        self._validate_current_geometry(
            video, frame_nums[0], geometry_plan=geometry_plan, abort=abort
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        argv = build_extract_frames_argv(
            video=video.absolute(),
            frame_nums=frame_nums,
            output_pattern=Path("%09d.png"),
            overwrite=True,
            geometry_plan=geometry_plan,
            source_signal=source_signal,
        )
        completed = self._run_extraction(
            argv,
            timeout_message="ffmpeg timed out while extracting frames",
            stderr_limit=self._BATCH_STDERR_BYTES,
            abort=abort,
            cwd=output_dir,
        )
        _validate_showinfo_timeline(completed.stderr, video, frame_nums[0])
        picture_types = parse_showinfo_picture_types(completed.stderr, len(frame_nums))
        return [
            RenderedFrameFacts(source_frame=frame_num, picture_type=picture_type)
            for frame_num, picture_type in zip(frame_nums, picture_types, strict=True)
        ]

    def _validate_current_geometry(
        self,
        video: Path,
        first_requested_frame: int,
        *,
        geometry_plan: RenderGeometryPlan | None = None,
        expected_dimensions: tuple[int, int] | None = None,
        abort: Callable[[], bool] | None = None,
    ) -> None:
        try:
            streams = probe_video_streams(video, abort=abort)
            if geometry_plan is not None:
                expected_dimensions = (geometry_plan.source.width, geometry_plan.source.height)
            _validate_selected_geometry(streams, expected_dimensions)
        except (ValueError, FFmpegError, FFmpegNotFoundError) as error:
            raise FrameExtractionError(
                first_requested_frame, str(video), reason=str(error)
            ) from error

    def validate_source(
        self,
        video: Path,
        expected_dimensions: tuple[int, int],
        expected_count: int | None,
        first_requested_frame: int,
    ) -> None:
        """Validate the live source against the prepared geometry and timeline once per clip."""
        if expected_count is None:
            self._validate_current_geometry(
                video,
                first_requested_frame,
                expected_dimensions=expected_dimensions,
                abort=is_cancelling,
            )
            return
        argv = [
            "ffprobe",
            "-v",
            "error",
            "-max_pixels",
            str(MAX_CANVAS_PIXELS),
            "-select_streams",
            "V:0",
            "-threads",
            "0",
            "-count_frames",
            "-show_entries",
            "stream=width,height,nb_read_frames",
            "-of",
            "json",
            "-i",
            str(video),
        ]
        count_timeout = max(self._extraction_timeout_seconds, 30.0 + expected_count / 4)
        try:
            completed = run_subprocess(argv, timeout_seconds=count_timeout, abort=is_cancelling)
        except SubprocessAborted:
            raise_if_cancelling()
            raise
        except TimeoutExpired as exc:
            raise FrameExtractionError(
                first_requested_frame,
                str(video),
                reason=f"FFmpeg's decoded frame count check timed out after {count_timeout} seconds",
                hint="Use the VapourSynth renderer or raise screenshots.ffmpeg_timeout_seconds",
            ) from exc
        except (FileNotFoundError, CalledProcessError, SubprocessOutputLimitExceeded) as exc:
            if isinstance(exc, CalledProcessError) and exc.returncode in (
                -SIGINT,
                _WINDOWS_STATUS_CONTROL_C_EXIT,
            ):
                raise_if_cancelling()
            raise FrameExtractionError(
                first_requested_frame,
                str(video),
                reason="Could not count FFmpeg's decoded frames",
                hint="Use the VapourSynth renderer",
            ) from exc

        try:
            payload: object = json.loads(completed.stdout)
            if completed.stderr or not isinstance(payload, dict):
                raise ValueError("Could not count FFmpeg's decoded frames")
            raw_streams = cast(dict[str, object], payload).get("streams")
            if not isinstance(raw_streams, list) or any(
                not isinstance(stream, dict) for stream in cast(list[object], raw_streams)
            ):
                raise ValueError("Could not count FFmpeg's decoded frames")
            streams = cast(list[dict[str, object]], raw_streams)
            if len(streams) != 1 or is_attached_picture(streams[0]):
                raise ValueError("Exactly one verifiable playable video stream is required")
            _validate_selected_geometry(streams, expected_dimensions)
            decoded = streams[0].get("nb_read_frames")
            if not isinstance(decoded, str) or not decoded.isascii() or not decoded.isdigit():
                raise ValueError("Could not count FFmpeg's decoded frames")
            decoded_count = int(decoded)
            if decoded_count != expected_count:
                raise ValueError(
                    f"FFmpeg decoded {decoded_count} frames but the prepared "
                    f"L-SMASH timeline has {expected_count}"
                )
        except (ValueError, TypeError) as exc:
            raise FrameExtractionError(
                first_requested_frame,
                str(video),
                reason=str(exc),
                hint="Use the VapourSynth renderer",
            ) from exc

    def _run_extraction(
        self,
        argv: list[str],
        *,
        timeout_message: str,
        stderr_limit: int,
        abort: Callable[[], bool] | None = None,
        cwd: Path | None = None,
    ) -> CompletedProcess[bytes]:
        try:
            if cwd is not None:
                # Relative PATH entries belong to the caller, before staging changes cwd.
                executable = Path(resolve_executable(argv[0])).absolute()
                argv = [str(executable), *argv[1:]]
            return run_subprocess(
                argv,
                timeout_seconds=self._extraction_timeout_seconds,
                abort=abort,
                max_stdout_bytes=8 * 1024,
                max_stderr_bytes=stderr_limit,
                cwd=cwd,
            )
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except TimeoutExpired as exc:
            raise FFmpegError(timeout_message, 124) from exc
        except CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace")
            raise FFmpegError(stderr, exc.returncode) from exc
        except SubprocessOutputLimitExceeded as exc:
            raise FFmpegError(str(exc), 1) from exc

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        metadata = probe_hdr_metadata(video)
        if (
            metadata is None
            or metadata.transfer == _H273_UNSPECIFIED
            or metadata.color_primaries == _H273_UNSPECIFIED
        ):
            return None
        return metadata


def _validate_selected_geometry(
    streams: list[dict[str, object]], expected_dimensions: tuple[int, int] | None
) -> None:
    playable = [stream for stream in streams if not is_attached_picture(stream)]
    if len(playable) != 1:
        raise ValueError("Exactly one verifiable playable video stream is required")
    width, height = playable[0].get("width"), playable[0].get("height")
    if type(width) is not int or type(height) is not int:
        raise ValueError("Source video dimensions could not be verified before decoding")
    validate_canvas_size(width, height, label="Source video")
    if expected_dimensions is not None and (width, height) != expected_dimensions:
        raise ValueError(
            f"Current source dimensions {width}x{height} disagree with prepared "
            f"source dimensions {expected_dimensions[0]}x{expected_dimensions[1]}"
        )


_SHOWINFO_CONFIG_RE = re.compile(rb"\[Parsed_showinfo_[^]]+\] config in time_base:")
_SHOWINFO_TYPE_RE = re.compile(rb"\[Parsed_showinfo_[^]]+\].*?\btype\s*[:=]\s*([^\s,\]]+)")
_SHOWINFO_INDEXED_TYPE_RE = re.compile(
    rb"\[Parsed_showinfo_[^]]+\][^\r\n]*?\bn\s*[:=]\s*(\d+)"
    rb"[^\r\n]*?\btype\s*[:=]\s*([^\s,\]]+)"
)


def _validate_showinfo_timeline(stderr: bytes, video: Path, frame_num: int) -> None:
    # A reconfigured graph restarts select's source index. Its new showinfo
    # logs a second config even if it never receives a selected frame.
    if len(_SHOWINFO_CONFIG_RE.findall(stderr)) > 1 or any(
        int(match.group(1)) != index
        for index, match in enumerate(_SHOWINFO_INDEXED_TYPE_RE.finditer(stderr))
    ):
        raise FrameExtractionError(
            frame_num,
            str(video),
            reason="FFmpeg reconfigured its filter graph during extraction",
            hint="Use the VapourSynth renderer",
        )


def _resolve_picture_type_tokens(tokens: Sequence[bytes]) -> PictureType | None:
    values: set[PictureType] = set()
    saw_unknown = False
    saw_invalid = False
    for raw_token in tokens:
        token = raw_token.rstrip(b".;")
        if token == b"?":
            saw_unknown = True
            continue
        normalized = normalize_picture_type(token)
        if normalized is not None:
            values.add(normalized)
        else:
            saw_invalid = True
    if saw_unknown or saw_invalid or len(values) != 1:
        return None
    return values.pop()


def parse_showinfo_picture_type(stderr: bytes | str) -> PictureType | None:
    """Return one unambiguous picture type from selected-frame ``showinfo`` output.

    ``showinfo`` is intentionally parsed only on its own ``Parsed_showinfo_*``
    diagnostics. Duplicate identical records are harmless; a missing, unknown,
    or contradictory value is represented as ``None``.
    """
    raw = stderr.encode() if isinstance(stderr, str) else stderr
    return _resolve_picture_type_tokens(
        [match.group(1) for match in _SHOWINFO_TYPE_RE.finditer(raw)]
    )


def parse_showinfo_picture_types(
    stderr: bytes | str, expected_count: int
) -> list[PictureType | None]:
    """Return picture types keyed by selected-frame output index."""
    if expected_count < 0:
        raise ValueError("expected_count must be non-negative")
    raw = stderr.encode() if isinstance(stderr, str) else stderr
    tokens_by_index: list[list[bytes]] = [[] for _ in range(expected_count)]
    for match in _SHOWINFO_INDEXED_TYPE_RE.finditer(raw):
        index = int(match.group(1))
        if index < expected_count:
            tokens_by_index[index].append(match.group(2))
    return [_resolve_picture_type_tokens(tokens) for tokens in tokens_by_index]
