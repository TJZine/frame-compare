"""FFmpeg-based frame extraction and probing runtime adapter."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from signal import SIGINT
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Protocol

from frame_compare.render.backend._ffmpeg_frame import (
    build_extract_frame_argv,
    build_extract_frames_argv,
)
from frame_compare.render.errors import FrameExtractionError
from frame_compare.utils.cancellation import is_cancelling, raise_if_cancelling
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.media_facts import PictureType, RenderedFrameFacts, normalize_picture_type
from frame_compare.utils.subproc import SubprocessAborted, resolve_executable, run_subprocess
from frame_compare.vs.hdr_probe import probe_hdr_metadata
from frame_compare.vs.types import HDRMetadata

if TYPE_CHECKING:
    from frame_compare.render.geometry import RenderGeometryPlan


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

    def __init__(self, extraction_timeout_seconds: float = _FFMPEG_TIMEOUT_SECONDS) -> None:
        self._extraction_timeout_seconds = extraction_timeout_seconds

    def extract_frame(
        self,
        video: Path,
        frame_num: int,
        output: Path,
        *,
        geometry_plan: RenderGeometryPlan | None = None,
    ) -> RenderedFrameFacts:
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".frame-compare-ffmpeg-", dir=output.parent) as temp_dir:
            staged_path = Path(temp_dir) / "frame.png"
            argv = build_extract_frame_argv(
                video=video,
                frame_num=frame_num,
                output=staged_path,
                overwrite=True,
                geometry_plan=geometry_plan,
            )
            completed = self._run_extraction(
                argv,
                timeout_message="ffmpeg timed out while extracting frame",
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
        abort: Callable[[], bool] | None = None,
    ) -> list[RenderedFrameFacts]:
        """Extract ordered frames in one decode pass into numbered staging files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        argv = build_extract_frames_argv(
            video=video.absolute(),
            frame_nums=frame_nums,
            output_pattern=Path("%09d.png"),
            overwrite=True,
            geometry_plan=geometry_plan,
        )
        completed = self._run_extraction(
            argv,
            timeout_message="ffmpeg timed out while extracting frames",
            abort=abort,
            cwd=output_dir,
        )
        _validate_showinfo_timeline(completed.stderr, video, frame_nums[0])
        picture_types = parse_showinfo_picture_types(completed.stderr, len(frame_nums))
        return [
            RenderedFrameFacts(source_frame=frame_num, picture_type=picture_type)
            for frame_num, picture_type in zip(frame_nums, picture_types, strict=True)
        ]

    def validate_source_frame_count(
        self, video: Path, expected_count: int, first_requested_frame: int
    ) -> None:
        """Refuse extraction when the decoded count disagrees with the prepared timeline."""
        argv = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "V:0",
            "-threads",
            "0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
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
        except (FileNotFoundError, CalledProcessError) as exc:
            # Ctrl+C can stop ffprobe inside wait() before the next abort poll.
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

        decoded = completed.stdout.strip()
        if completed.stderr or not decoded.isdigit():
            reason = "Could not count FFmpeg's decoded frames"
        else:
            decoded_count = int(decoded)
            if decoded_count == expected_count:
                return
            reason = (
                f"FFmpeg decoded {decoded_count} frames but the prepared "
                f"L-SMASH timeline has {expected_count}"
            )
        raise FrameExtractionError(
            first_requested_frame, str(video), reason=reason, hint="Use the VapourSynth renderer"
        )

    def _run_extraction(
        self,
        argv: list[str],
        *,
        timeout_message: str,
        abort: Callable[[], bool] | None = None,
        cwd: Path | None = None,
    ) -> CompletedProcess[bytes]:
        try:
            if cwd is not None:
                # Relative PATH entries belong to the caller, before staging changes cwd.
                executable = Path(resolve_executable(argv[0])).absolute()
                argv = [str(executable), *argv[1:]]
            return run_subprocess(
                argv, timeout_seconds=self._extraction_timeout_seconds, abort=abort, cwd=cwd
            )
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except TimeoutExpired as exc:
            raise FFmpegError(timeout_message, 124) from exc
        except CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace")
            raise FFmpegError(stderr, exc.returncode) from exc

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        metadata = probe_hdr_metadata(video)
        if (
            metadata is None
            or metadata.transfer == _H273_UNSPECIFIED
            or metadata.color_primaries == _H273_UNSPECIFIED
        ):
            return None
        return metadata


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
