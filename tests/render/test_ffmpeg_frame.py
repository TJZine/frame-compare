import subprocess
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.render.backend._ffmpeg_frame import (
    build_extract_frame_argv,
    build_extract_frames_argv,
)
from frame_compare.render.backend.ffmpeg import (
    DefaultFFmpegRunner,
    parse_showinfo_picture_type,
    parse_showinfo_picture_types,
)
from frame_compare.render.geometry import (
    GeometryMargins,
    GeometryRect,
    RenderGeometryPlan,
    SourceGeometry,
)
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.media_facts import RenderedFrameFacts
from frame_compare.vs.types import HDRMetadata


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
        "select=eq(n\\,100),showinfo=checksum=0",
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
        "select=eq(n\\,100),showinfo=checksum=0,crop=1440:1080:240:0,scale=1280:960,pad=1280:1080:0:60:color=black"
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


def test_build_extract_frames_argv_selects_ordered_frames_in_one_pass() -> None:
    assert build_extract_frames_argv(
        video=Path("clip.mkv"),
        frame_nums=[10, 20, 42],
        output_pattern=Path("staging/%09d.png"),
        overwrite=True,
    ) == [
        "ffmpeg",
        "-y",
        "-i",
        "clip.mkv",
        "-vf",
        "select=eq(n\\,10)+eq(n\\,20)+eq(n\\,42),showinfo=checksum=0",
        "-fps_mode",
        "passthrough",
        "-frames:v",
        "3",
        "-q:v",
        "1",
        "-start_number",
        "0",
        str(Path("staging") / "%09d.png"),
    ]

    legacy = build_extract_frames_argv(
        video=Path("clip.mkv"),
        frame_nums=[10, 20, 42],
        output_pattern=Path("staging/%09d.png"),
        overwrite=True,
        legacy_vsync=True,
    )
    assert legacy[legacy.index("-vsync") : legacy.index("-vsync") + 2] == ["-vsync", "0"]


@pytest.mark.parametrize("frame_nums", [[], [2, 2], [2, 1], [-1, 2]])
def test_build_extract_frames_argv_rejects_unsafe_frame_sequences(
    frame_nums: Sequence[int],
) -> None:
    with pytest.raises(ValueError):
        build_extract_frames_argv(
            video=Path("clip.mkv"),
            frame_nums=frame_nums,
            output_pattern=Path("staging/%09d.png"),
            overwrite=True,
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
            "select=eq(n\\,100),showinfo=checksum=0",
            "-frames:v",
            "1",
            "-q:v",
            "1",
            str(output),
        ],
        timeout_seconds=30.0,
    )
    assert output.parent.is_dir()


def test_default_ffmpeg_runner_returns_picture_type_from_same_extraction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"",
            stderr=b"[Parsed_showinfo_1 @ 0x1] n:0 type:B",
        )
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    facts = DefaultFFmpegRunner().extract_frame(Path("clip.mkv"), 12, tmp_path / "frame.png")

    assert facts.source_frame == 12
    assert facts.picture_type == "B"


def test_default_ffmpeg_runner_extract_frames_preserves_indexed_picture_types(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"",
            stderr=(
                b"[Parsed_showinfo_1 @ 0x1] n:0 type:I\n"
                b"[Parsed_showinfo_1 @ 0x1] n:1 type:B\n"
                b"[Parsed_showinfo_1 @ 0x1] n:2 type:P\n"
            ),
        )
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    output_dir = tmp_path / "staging"
    facts = DefaultFFmpegRunner().extract_frames(Path("clip.mkv"), [10, 20, 42], output_dir)

    assert [(fact.source_frame, fact.picture_type) for fact in facts] == [
        (10, "I"),
        (20, "B"),
        (42, "P"),
    ]
    assert run_subprocess.call_args.args[0][-1] == str(output_dir / "%09d.png")
    assert run_subprocess.call_args.kwargs["timeout_seconds"] == 30.0


def test_default_ffmpeg_runner_extract_frames_retries_legacy_vsync_when_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        side_effect=[
            subprocess.CalledProcessError(
                1,
                ["ffmpeg"],
                stderr=b"Unrecognized option 'fps_mode'. Error splitting: Option not found",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=b"",
                stderr=b"[Parsed_showinfo_1 @ 0x1] n:0 type:I",
            ),
        ]
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    facts = DefaultFFmpegRunner().extract_frames(Path("clip.mkv"), [10], tmp_path)

    assert facts == [RenderedFrameFacts(source_frame=10, picture_type="I")]
    modern_argv = run_subprocess.call_args_list[0].args[0]
    legacy_argv = run_subprocess.call_args_list[1].args[0]
    assert modern_argv[modern_argv.index("-fps_mode") : modern_argv.index("-fps_mode") + 2] == [
        "-fps_mode",
        "passthrough",
    ]
    assert legacy_argv[legacy_argv.index("-vsync") : legacy_argv.index("-vsync") + 2] == [
        "-vsync",
        "0",
    ]


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        (b"[Parsed_showinfo_1 @ 0x1] n:0 type:I", "I"),
        (b"[Parsed_showinfo_1 @ 0x1] n:0 type:P", "P"),
        (b"[Parsed_showinfo_1 @ 0x1] n:0 type:B", "B"),
        (b"[Parsed_showinfo_1 @ 0x1] n:0 type:?", None),
        (
            b"noise type:P\n[Parsed_showinfo_1 @ 0x1] n:0 type:B\n",
            "B",
        ),
        (
            b"[Parsed_showinfo_1 @ 0x1] n:0 type:B\n[Parsed_showinfo_1 @ 0x1] n:0 type:B\n",
            "B",
        ),
        (
            b"[Parsed_showinfo_1 @ 0x1] n:0 type:I\n[Parsed_showinfo_1 @ 0x1] n:0 type:B\n",
            None,
        ),
        (
            b"[Parsed_showinfo_1 @ 0x1] n:0 type:I\n[Parsed_showinfo_1 @ 0x1] n:0 type:unknown\n",
            None,
        ),
        ("[Parsed_showinfo_1 @ 0x1] n:0 type:P", "P"),
        ("", None),
    ],
)
def test_parse_showinfo_picture_type(stderr: bytes | str, expected: str | None) -> None:
    assert parse_showinfo_picture_type(stderr) == expected


def test_parse_showinfo_picture_types_isolates_missing_and_conflicting_records() -> None:
    stderr = (
        b"[Parsed_showinfo_1 @ 0x1] n:0 type:I\n"
        b"[Parsed_showinfo_1 @ 0x1] n:0 type:I\n"
        b"[Parsed_showinfo_1 @ 0x1] n:2 type:B\n"
        b"[Parsed_showinfo_1 @ 0x1] n:2 type:P\n"
    )

    assert parse_showinfo_picture_types(stderr, 4) == ["I", None, None, None]


def test_default_ffmpeg_runner_extract_frame_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_subprocess = MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
    )
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner(extraction_timeout_seconds=47.0)
    runner.extract_frame(Path("clip.mkv"), 1, tmp_path / "frame.png")

    assert run_subprocess.call_args.kwargs["timeout_seconds"] == 47.0


def test_default_ffmpeg_runner_probe_hdr_keeps_fixed_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_subprocess = MagicMock(
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b'{"streams": []}',
            stderr=b"",
        )
    )
    monkeypatch.setattr("frame_compare.vs.hdr_probe.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner(extraction_timeout_seconds=47.0)
    assert runner.probe_hdr(Path("clip.mkv")) is None

    assert run_subprocess.call_args.kwargs["timeout_seconds"] == 15.0


@pytest.mark.parametrize(
    ("color_primaries", "transfer", "matrix"),
    [
        pytest.param(2, 2, 1, id="matrix-only"),
        pytest.param(2, 16, 2, id="transfer-only"),
        pytest.param(9, 2, 2, id="primaries-only"),
    ],
)
def test_default_ffmpeg_runner_probe_hdr_treats_partial_color_signals_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
    color_primaries: int,
    transfer: int,
    matrix: int,
) -> None:
    metadata = HDRMetadata(
        mastering_display=None,
        max_cll=None,
        max_fall=None,
        color_primaries=color_primaries,
        transfer=transfer,
        matrix=matrix,
    )
    probe_hdr_metadata = MagicMock(return_value=metadata)
    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.probe_hdr_metadata",
        probe_hdr_metadata,
    )

    assert DefaultFFmpegRunner().probe_hdr(Path("clip.mkv")) is None
    probe_hdr_metadata.assert_called_once_with(Path("clip.mkv"))


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param(
            HDRMetadata(
                mastering_display=None,
                max_cll=None,
                max_fall=None,
                color_primaries=1,
                transfer=1,
                matrix=1,
            ),
            id="sdr",
        ),
        pytest.param(
            HDRMetadata(
                mastering_display=None,
                max_cll=None,
                max_fall=None,
                color_primaries=9,
                transfer=16,
                matrix=9,
            ),
            id="hdr",
        ),
    ],
)
def test_default_ffmpeg_runner_probe_hdr_preserves_complete_color_signals(
    monkeypatch: pytest.MonkeyPatch,
    metadata: HDRMetadata,
) -> None:
    probe_hdr_metadata = MagicMock(return_value=metadata)
    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.probe_hdr_metadata",
        probe_hdr_metadata,
    )

    assert DefaultFFmpegRunner().probe_hdr(Path("clip.mkv")) is metadata
    probe_hdr_metadata.assert_called_once_with(Path("clip.mkv"))


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
        side_effect=subprocess.CalledProcessError(
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
