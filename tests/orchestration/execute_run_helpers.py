"""Shared helpers for execute_run orchestration tests."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PIL import Image

import frame_compare.analysis.cache_io as cache_io
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot, ClipState
from frame_compare.vs.types import HDRMetadata, SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs


MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""

RUN_FOLDERS_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = true

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    """Create a config file in the standard location."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(content, encoding="utf-8")
    return config_file


def create_video_files(input_dir: Path, *filenames: str) -> None:
    """Create empty video files for testing."""
    input_dir.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (input_dir / name).touch()


def write_metrics_cache(cache_dir: Path, *, source_path: Path, config: ConfigSchema) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = cache_io.compute_cache_key([source_path], config.analysis)
    cache_payload = {
        "version": cache_io.CACHE_VERSION,
        "fingerprint": fingerprint,
        "luminance": [0.1] * 100,
        "motion": [0.2] * 100,
        "metadata": {
            "frame_count": 100,
            "fps": "24",
            "config_fingerprint": fingerprint,
            "clips": [
                {
                    "path": str(source_path),
                    "size": 0,
                    "mtime": 0.0,
                    "sha1": None,
                }
            ],
            "version": cache_io.CACHE_VERSION,
        },
    }
    (cache_dir / cache_io.CACHE_FILENAME).write_text(json.dumps(cache_payload), encoding="utf-8")


def clip_state(path: Path, *, label: str, num_frames: int = 100) -> ClipState:
    probe = ClipProbeSnapshot(
        fingerprint=ClipFingerprint(path=path, size_bytes=0, mtime_ns=0),
        width=1920,
        height=1080,
        num_frames=num_frames,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    return ClipState(
        path=path,
        label=label,
        probe=probe,
        source_fps=probe.fps,
        effective_fps=probe.fps,
    )


class FakeVSLoader:
    def load(self, path: Path) -> SourceInfo:
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24, 1),
            format=cast(Any, object()),
            frame_props={},
            is_hdr=False,
            hdr_metadata=None,
        )

    def ensure_core(self) -> vs.Core:
        raise RuntimeError("ensure_core should not be called in tests")


class FakeHDRVSLoader(FakeVSLoader):
    def load(self, path: Path) -> SourceInfo:
        return SourceInfo(
            clip=cast(Any, object()),
            width=1920,
            height=1080,
            num_frames=100,
            fps=Fraction(24, 1),
            format=cast(Any, object()),
            frame_props={},
            is_hdr=True,
            hdr_metadata=HDRMetadata(
                mastering_display="G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)",
                max_cll=1000,
                max_fall=400,
                color_primaries=9,
                transfer=16,
                matrix=9,
            ),
        )


class FakeFFmpegRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), color=(0, 0, 0)).save(output, format="PNG")
        self.calls.append((video.name, frame_num, output.name))

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        return HDRMetadata(
            mastering_display=None,
            max_cll=None,
            max_fall=None,
            color_primaries=1,
            transfer=1,
            matrix=1,
        )
