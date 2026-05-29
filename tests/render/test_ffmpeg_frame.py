import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.render.backend._ffmpeg_frame import (
    build_extract_frame_argv,
    frame_seek_time_seconds,
)
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import CalledProcessError


def test_frame_seek_time_seconds_matches_repo_contract() -> None:
    assert frame_seek_time_seconds(100, 24000 / 1001) == "4.170833"


@pytest.mark.parametrize(
    ("frame_num", "fps"),
    [
        (-1, 24.0),
        (0, 0.0),
    ],
)
def test_frame_seek_time_seconds_rejects_invalid_inputs(frame_num: int, fps: float) -> None:
    with pytest.raises(ValueError):
        frame_seek_time_seconds(frame_num, fps)


def test_build_extract_frame_argv_supports_optional_overwrite() -> None:
    assert build_extract_frame_argv(
        video=Path("clip.mkv"),
        seek_time="4.170",
        output=Path("frame.png"),
        overwrite=False,
    ) == [
        "ffmpeg",
        "-ss",
        "4.170",
        "-i",
        "clip.mkv",
        "-vframes",
        "1",
        "-q:v",
        "1",
        "frame.png",
    ]
    assert build_extract_frame_argv(
        video=Path("clip.mkv"),
        seek_time="4.170",
        output=Path("frame.png"),
        overwrite=True,
    )[:2] == ["ffmpeg", "-y"]


def test_default_ffmpeg_runner_extract_frame_uses_shared_command_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        side_effect=[
            subprocess.CompletedProcess(args=[], returncode=0, stdout=b"24000/1001\n", stderr=b""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b""),
        ]
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner()
    output = tmp_path / "shots" / "frame.png"
    runner.extract_frame(Path("clip.mkv"), 100, output)

    assert run_subprocess.call_count == 2
    extract_call = run_subprocess.call_args_list[1]
    argv = extract_call.args[0]
    assert argv == [
        "ffmpeg",
        "-y",
        "-ss",
        "4.170833",
        "-i",
        "clip.mkv",
        "-vframes",
        "1",
        "-q:v",
        "1",
        str(output),
    ]
    assert output.parent.is_dir()


def test_default_ffmpeg_runner_extract_frame_wraps_missing_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        side_effect=[subprocess.CompletedProcess([], 0, b"24\n", b""), FileNotFoundError]
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner()

    with pytest.raises(FFmpegNotFoundError):
        runner.extract_frame(Path("clip.mkv"), 1, tmp_path / "frame.png")


def test_default_ffmpeg_runner_extract_frame_wraps_missing_input_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        side_effect=[
            subprocess.CompletedProcess(args=[], returncode=0, stdout=b"24\n", stderr=b""),
            CalledProcessError(
                1,
                ["ffmpeg"],
                stderr=b"No such file or directory",
            ),
        ]
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner()

    with pytest.raises(FFmpegError) as exc_info:
        runner.extract_frame(Path("nonexistent.mkv"), 1, tmp_path / "frame.png")

    details = exc_info.value.context.details
    assert details is not None
    assert details["returncode"] == 1
    assert "No such file or directory" in str(details["stderr"])
