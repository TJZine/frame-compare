"""Small config/workspace builder for preparation tests."""

from __future__ import annotations

from pathlib import Path

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

METRIC_CONFIG = (
    MINIMAL_CONFIG
    + """
[analysis]
random_frame_count = 0
dark_frame_count = 1
"""
)

AUTO_METRIC_CONFIG = METRIC_CONFIG.replace(
    "[screenshots]\nuse_ffmpeg = true",
    '[screenshots]\nuse_ffmpeg = true\nactive_rect_detection = "auto"',
)

AUTO_MINIMAL_CONFIG = MINIMAL_CONFIG.replace(
    "[screenshots]\nuse_ffmpeg = true",
    '[screenshots]\nuse_ffmpeg = true\nactive_rect_detection = "auto"',
)

ALIGNMENT_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
use_run_folders = false

[audio_alignment]
enable = true

[screenshots]
use_ffmpeg = true

[report]
enable = false
"""


def create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def create_video_files(input_dir: Path, *filenames: str) -> list[Path]:
    input_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename in filenames:
        path = input_dir / filename
        path.write_bytes(b"video")
        paths.append(path)
    return paths
