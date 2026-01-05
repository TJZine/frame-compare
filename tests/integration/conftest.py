import shutil
from pathlib import Path

import pytest
from PIL import Image

from frame_compare.utils.subproc import run_subprocess

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.fixture
def require_ffmpeg():
    """Skip test if ffmpeg/ffprobe are not available."""
    if not FFMPEG_AVAILABLE:
        pytest.skip("ffmpeg/ffprobe not available")


@pytest.fixture
def integration_output_dir(tmp_path: Path) -> Path:
    """Create and return a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.fixture
def sample_image_path(tmp_path: Path) -> Path:
    """Create a sample 100x100 solid red PNG."""
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    path = tmp_path / "red.png"
    img.save(path)
    return path


@pytest.fixture
def mock_video_path(tmp_path: Path, require_ffmpeg: None) -> Path:
    """Create a deterministic 3-frame CFR video using FFmpeg.

    Returns:
        Path to generated .mp4 file.
    """
    output_path = tmp_path / "test.mp4"
    # Command per plan-v3: exactly 3 frames at 10 fps
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=100x100:r=10",
        "-frames:v",
        "3",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    run_subprocess(cmd, timeout_seconds=10)
    return output_path
