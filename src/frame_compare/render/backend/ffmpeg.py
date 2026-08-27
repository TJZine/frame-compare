"""FFmpeg-based frame extraction and probing runtime adapter."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired
from typing import TYPE_CHECKING, Protocol

from frame_compare.render.backend._ffmpeg_frame import (
    build_extract_frame_argv,
    build_extract_frames_argv,
)
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.media_facts import PictureType, RenderedFrameFacts, normalize_picture_type
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.hdr_probe import probe_hdr_metadata
from frame_compare.vs.types import HDRMetadata

if TYPE_CHECKING:
    from frame_compare.render.geometry import RenderGeometryPlan


_H273_UNSPECIFIED = 2


def _fps_mode_option_is_unavailable(stderr: str) -> bool:
    normalized = stderr.casefold()
    return "fps_mode" in normalized and (
        "unrecognized option" in normalized or "option not found" in normalized
    )


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
        argv = build_extract_frame_argv(
            video=video,
            frame_num=frame_num,
            output=output,
            overwrite=True,
            geometry_plan=geometry_plan,
        )
        completed = self._run_extraction(
            argv,
            timeout_message="ffmpeg timed out while extracting frame",
        )
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
    ) -> list[RenderedFrameFacts]:
        """Extract ordered frames in one decode pass into numbered staging files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        argv = build_extract_frames_argv(
            video=video,
            frame_nums=frame_nums,
            output_pattern=output_dir / "%09d.png",
            overwrite=True,
            geometry_plan=geometry_plan,
        )
        legacy_argv = build_extract_frames_argv(
            video=video,
            frame_nums=frame_nums,
            output_pattern=output_dir / "%09d.png",
            overwrite=True,
            geometry_plan=geometry_plan,
            legacy_vsync=True,
        )
        completed = self._run_extraction(
            argv,
            timeout_message="ffmpeg timed out while extracting frames",
            unsupported_fps_mode_fallback=legacy_argv,
        )
        picture_types = parse_showinfo_picture_types(completed.stderr, len(frame_nums))
        return [
            RenderedFrameFacts(source_frame=frame_num, picture_type=picture_type)
            for frame_num, picture_type in zip(frame_nums, picture_types, strict=True)
        ]

    def _run_extraction(
        self,
        argv: list[str],
        *,
        timeout_message: str,
        unsupported_fps_mode_fallback: list[str] | None = None,
    ) -> CompletedProcess[bytes]:
        try:
            return run_subprocess(argv, timeout_seconds=self._extraction_timeout_seconds)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except TimeoutExpired as exc:
            raise FFmpegError(timeout_message, 124) from exc
        except CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace")
            if unsupported_fps_mode_fallback is not None and _fps_mode_option_is_unavailable(
                stderr
            ):
                return self._run_extraction(
                    unsupported_fps_mode_fallback,
                    timeout_message=timeout_message,
                )
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


_SHOWINFO_TYPE_RE = re.compile(rb"\[Parsed_showinfo_[^]]+\].*?\btype\s*[:=]\s*([^\s,\]]+)")
_SHOWINFO_INDEXED_TYPE_RE = re.compile(
    rb"\[Parsed_showinfo_[^]]+\][^\r\n]*?\bn\s*[:=]\s*(\d+)"
    rb"[^\r\n]*?\btype\s*[:=]\s*([^\s,\]]+)"
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
