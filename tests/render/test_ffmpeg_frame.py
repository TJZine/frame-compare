import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.render.backend._ffmpeg_frame import (
    build_extract_frame_argv,
)
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.render.geometry import (
    GeometryMargins,
    GeometryRect,
    RenderGeometryPlan,
    SourceGeometry,
)
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import CalledProcessError


def test_build_extract_frame_argv_supports_optional_overwrite() -> None:
    assert build_extract_frame_argv(
        video=Path("clip.mkv"),
        frame_num=100,
        output=Path("frame.png"),
        overwrite=False,
    ) == [
        "ffmpeg",
        "-i",
        "clip.mkv",
        "-vf",
        "select=eq(n\\,100)",
        "-frames:v",
        "1",
        "-q:v",
        "1",
        "frame.png",
    ]
    assert build_extract_frame_argv(
        video=Path("clip.mkv"),
        frame_num=100,
        output=Path("frame.png"),
        overwrite=True,
    )[:2] == ["ffmpeg", "-y"]


def test_build_extract_frame_argv_rejects_negative_frame_numbers() -> None:
    with pytest.raises(ValueError, match="frame_num must be non-negative"):
        build_extract_frame_argv(
            video=Path("clip.mkv"),
            frame_num=-1,
            output=Path("frame.png"),
            overwrite=False,
        )


def test_build_extract_frame_argv_places_geometry_filters_after_exact_frame_select() -> None:
    source = SourceGeometry(width=1920, height=1080)
    plan = RenderGeometryPlan(
        source=source,
        source_rect=GeometryRect(0, 0, 1920, 1080),
        active_rect=GeometryRect(240, 0, 1440, 1080),
        active_rect_source="metadata",
        crop_rect=GeometryRect(240, 0, 1440, 1080),
        crop=GeometryMargins(left=240, right=240),
        cropped_size=(1440, 1080),
        scaled_size=(1280, 960),
        pad=GeometryMargins(top=60, bottom=60),
        final_canvas_size=(1280, 1080),
        content_origin=(0, 60),
        overlay_origin=(10, 70),
        source_overlay_origin=(250, 10),
    )

    argv = build_extract_frame_argv(
        video=Path("clip.mkv"),
        frame_num=100,
        output=Path("frame.png"),
        overwrite=False,
        geometry_plan=plan,
    )

    assert argv[argv.index("-vf") + 1] == (
        "select=eq(n\\,100),"
        "crop=1440:1080:240:0,"
        "scale=1280:960,"
        "pad=1280:1080:0:60:color=black"
    )


def test_build_extract_frame_argv_rejects_unrepresentable_geometry_plan() -> None:
    source = SourceGeometry(width=1920, height=1080)
    plan = RenderGeometryPlan(
        source=source,
        source_rect=GeometryRect(0, 0, 1920, 1080),
        active_rect=GeometryRect(0, 0, 1920, 1080),
        active_rect_source="full-frame",
        crop_rect=GeometryRect(0, 0, 1920, 1080),
        crop=GeometryMargins(),
        cropped_size=(1920, 1080),
        scaled_size=(0, 1080),
        pad=GeometryMargins(),
        final_canvas_size=(1920, 1080),
        content_origin=(0, 0),
        overlay_origin=(10, 10),
        source_overlay_origin=(10, 10),
    )

    with pytest.raises(ValueError, match="scale dimensions must be positive"):
        build_extract_frame_argv(
            video=Path("clip.mkv"),
            frame_num=100,
            output=Path("frame.png"),
            overwrite=False,
            geometry_plan=plan,
        )


def test_default_ffmpeg_runner_extract_frame_uses_shared_command_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner()
    output = tmp_path / "shots" / "frame.png"
    runner.extract_frame(Path("clip.mkv"), 100, output)

    run_subprocess.assert_called_once_with(
        [
        "ffmpeg",
        "-y",
        "-i",
        "clip.mkv",
        "-vf",
        "select=eq(n\\,100)",
        "-frames:v",
        "1",
        "-q:v",
        "1",
        str(output),
        ],
        timeout_seconds=30.0,
    )
    assert output.parent.is_dir()


def test_default_ffmpeg_runner_extract_frame_wraps_missing_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(side_effect=FileNotFoundError)
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner()

    with pytest.raises(FFmpegNotFoundError):
        runner.extract_frame(Path("clip.mkv"), 1, tmp_path / "frame.png")


def test_default_ffmpeg_runner_extract_frame_wraps_missing_input_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        side_effect=CalledProcessError(
            1,
            ["ffmpeg"],
            stderr=b"No such file or directory",
        )
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner()

    with pytest.raises(FFmpegError) as exc_info:
        runner.extract_frame(Path("nonexistent.mkv"), 1, tmp_path / "frame.png")

    details = exc_info.value.context.details
    assert details is not None
    assert details["returncode"] == 1
    assert "No such file or directory" in str(details["stderr"])
