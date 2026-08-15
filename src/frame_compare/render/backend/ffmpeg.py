"""FFmpeg-based frame extraction and probing runtime adapter."""

from __future__ import annotations

from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from typing import TYPE_CHECKING, Protocol

from frame_compare.render.backend._ffmpeg_frame import build_extract_frame_argv
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
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
    ) -> None:
        """Extract a single frame from the given video into the output path."""
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
    ) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        argv = build_extract_frame_argv(
            video=video,
            frame_num=frame_num,
            output=output,
            overwrite=True,
            geometry_plan=geometry_plan,
        )
        try:
            run_subprocess(argv, timeout_seconds=self._extraction_timeout_seconds)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except TimeoutExpired as exc:
            raise FFmpegError("ffmpeg timed out while extracting frame", 124) from exc
        except CalledProcessError as exc:
            raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        metadata = probe_hdr_metadata(video)
        if (
            metadata is None
            or metadata.transfer == _H273_UNSPECIFIED
            or metadata.color_primaries == _H273_UNSPECIFIED
        ):
            return None
        return metadata
