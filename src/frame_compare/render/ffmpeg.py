"""FFmpeg-based frame extraction and probing runtime adapter."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Protocol, cast

from frame_compare.errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.types import HDRMetadata


class FFmpegRunner(Protocol):
    """Protocol for FFmpeg-based frame extraction and probing."""

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        """Extract a single frame from the given video into the output path."""
        ...

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        """Probe HDR metadata for a video, returning None if unavailable."""
        ...


class DefaultFFmpegRunner:
    """Default FFmpeg runner for dependency injection in orchestration."""

    _FFPROBE_TIMEOUT_SECONDS = 15.0
    _FFMPEG_TIMEOUT_SECONDS = 30.0

    def _probe_fps(self, video: Path) -> float:
        argv = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]
        try:
            proc = run_subprocess(argv, timeout_seconds=self._FFPROBE_TIMEOUT_SECONDS)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError("ffprobe timed out while probing fps", 124) from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc

        raw = proc.stdout.decode("utf-8", errors="replace").strip()
        if not raw:
            raise FFmpegError("ffprobe returned empty avg_frame_rate", proc.returncode)

        try:
            if "/" in raw:
                num, den = raw.split("/", maxsplit=1)
                num_f = float(num)
                den_f = float(den)
                if den_f == 0.0:
                    raise ValueError("zero denominator")
                fps = num_f / den_f
            else:
                fps = float(raw)
        except ValueError as exc:
            raise FFmpegError(f"invalid avg_frame_rate value: {raw!r}", proc.returncode) from exc

        if not math.isfinite(fps) or fps <= 0.0:
            raise FFmpegError(f"invalid probed fps value: {raw!r}", proc.returncode)
        return fps

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        fps = self._probe_fps(video)
        seek_time = f"{math.floor((frame_num / fps) * 1000) / 1000:.3f}"
        output.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            "ffmpeg",
            "-y",
            "-ss",
            seek_time,
            "-i",
            str(video),
            "-vframes",
            "1",
            "-q:v",
            "1",
            str(output),
        ]
        try:
            run_subprocess(argv, timeout_seconds=self._FFMPEG_TIMEOUT_SECONDS)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError("ffmpeg timed out while extracting frame", 124) from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        argv = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=color_transfer,color_primaries,color_space",
            "-of",
            "json",
            str(video),
        ]
        try:
            proc = run_subprocess(argv, timeout_seconds=self._FFPROBE_TIMEOUT_SECONDS)
        except FileNotFoundError as exc:
            raise FFmpegNotFoundError() from exc
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError("ffprobe timed out while probing hdr", 124) from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(exc.stderr.decode(errors="replace"), exc.returncode) from exc

        try:
            payload = cast(
                dict[str, object], json.loads(proc.stdout.decode("utf-8", errors="replace"))
            )
        except json.JSONDecodeError as exc:
            raise FFmpegError("ffprobe returned invalid json", proc.returncode) from exc

        streams_obj = payload.get("streams")
        if not isinstance(streams_obj, list) or not streams_obj:
            return None
        streams = cast(list[object], streams_obj)
        stream_obj = streams[0]
        if not isinstance(stream_obj, dict):
            return None
        stream = cast(dict[str, object], stream_obj)

        transfer_raw = str(stream.get("color_transfer", "")).lower().strip()
        primaries_raw = str(stream.get("color_primaries", "")).lower().strip()
        matrix_raw = str(stream.get("color_space", "")).lower().strip()
        is_hdr = transfer_raw in {"smpte2084", "arib-std-b67"} and primaries_raw == "bt2020"
        if not is_hdr:
            return None

        primaries_map = {"bt709": 1, "bt2020": 9}
        transfer_map = {"bt709": 1, "smpte2084": 16, "arib-std-b67": 18}
        matrix_map = {"bt709": 1, "bt2020nc": 9, "bt2020c": 10}
        return HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=primaries_map.get(primaries_raw, 2),
            transfer=transfer_map.get(transfer_raw, 2),
            matrix=matrix_map.get(matrix_raw, 2),
        )
