"""FFmpeg-based frame extraction and probing runtime adapter."""

from __future__ import annotations

import re
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import TYPE_CHECKING, Protocol

from frame_compare.render.backend._ffmpeg_frame import build_extract_frame_argv
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.media_facts import PictureType, RenderedFrameFacts, normalize_picture_type
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.hdr_probe import probe_hdr_metadata
from frame_compare.vs.types import HDRMetadata

if TYPE_CHECKING:
    from frame_compare.render.geometry import RenderGeometryPlan


_H273_UNSPECIFIED = 2


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
        try:
            completed = run_subprocess(argv, timeout_seconds=self._extraction_timeout_seconds)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except TimeoutExpired as exc:
            raise FFmpegError("ffmpeg timed out while extracting frame", 124) from exc
        except CalledProcessError as exc:
            raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc
        return RenderedFrameFacts(
            source_frame=frame_num,
            picture_type=parse_showinfo_picture_type(completed.stderr),
        )

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


def parse_showinfo_picture_type(stderr: bytes | str) -> PictureType | None:
    """Return one unambiguous picture type from selected-frame ``showinfo`` output.

    ``showinfo`` is intentionally parsed only on its own ``Parsed_showinfo_*``
    diagnostics. Duplicate identical records are harmless; a missing, unknown,
    or contradictory value is represented as ``None``.
    """
    raw = stderr.encode() if isinstance(stderr, str) else stderr
    values: set[PictureType] = set()
    saw_unknown = False
    saw_invalid = False
    for match in _SHOWINFO_TYPE_RE.finditer(raw):
        token = match.group(1).rstrip(b".;")
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
