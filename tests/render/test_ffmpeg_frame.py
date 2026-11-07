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
from frame_compare.render.errors import FrameExtractionError
from frame_compare.render.geometry import (
    GeometryMargins,
    GeometryRect,
    RenderGeometryPlan,
    SourceGeometry,
)
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.vs.types import HDRMetadata


def test_build_extract_frame_argv_supports_optional_overwrite() -> None:
    assert build_extract_frame_argv(
        video=Path("clip.mkv"),
        frame_num=100,
        output=Path("frame.png"),
        overwrite=False,
    ) == [
        "ffmpeg",
        "-noautorotate",
        "-i",
        "clip.mkv",
        "-map",
        "0:V:0",
        "-vf",
        "select=eq(n\\,100),showinfo=checksum=0,format=rgb24",
        "-frames:v",
        "1",
        "-q:v",
        "1",
        "-update",
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
    source = SourceGeometry(
        width=1920, height=1080, active_rect=GeometryRect(0, 0, 1920, 1080), provenance="full_frame"
    )
    plan = RenderGeometryPlan(
        source=source,
        source_rect=GeometryRect(0, 0, 1920, 1080),
        active_rect=GeometryRect(241, 0, 1440, 1080),
        provenance="explicit",
        crop_rect=GeometryRect(241, 0, 1440, 1080),
        crop=GeometryMargins(left=241, right=239),
        cropped_size=(1440, 1080),
        scaled_size=(1280, 960),
        pad=GeometryMargins(top=60, bottom=60),
        final_canvas_size=(1280, 1080),
        content_origin=(0, 60),
        overlay_origin=(10, 70),
    )

    argv = build_extract_frame_argv(
        video=Path("clip.mkv"),
        frame_num=100,
        output=Path("frame.png"),
        overwrite=False,
        geometry_plan=plan,
    )

    chain = argv[argv.index("-vf") + 1]
    prefix = "select=eq(n\\,100),"
    assert chain.startswith(prefix)
    filters = chain.removeprefix(prefix).split(",")
    assert filters[0] == "showinfo=checksum=0"
    # A pre-crop format constraint cannot constrain the later scale output.
    assert filters[3] == "scale=1280:960"
    assert filters[4].startswith("format=pix_fmts=")
    assert filters[1] == filters[4]
    assert filters[2] == "crop=1440:1080:241:0:exact=1"
    assert filters[5:] == ["pad=1280:1080:0:60:color=black", "format=rgb24"]


def test_build_extract_frame_argv_rejects_unrepresentable_geometry_plan() -> None:
    source = SourceGeometry(
        width=1920, height=1080, active_rect=GeometryRect(0, 0, 1920, 1080), provenance="full_frame"
    )
    plan = RenderGeometryPlan(
        source=source,
        source_rect=GeometryRect(0, 0, 1920, 1080),
        active_rect=GeometryRect(0, 0, 1920, 1080),
        provenance="full_frame",
        crop_rect=GeometryRect(0, 0, 1920, 1080),
        crop=GeometryMargins(),
        cropped_size=(1920, 1080),
        scaled_size=(0, 1080),
        pad=GeometryMargins(),
        final_canvas_size=(1920, 1080),
        content_origin=(0, 0),
        overlay_origin=(10, 10),
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
        "-noautorotate",
        "-i",
        "clip.mkv",
        "-map",
        "0:V:0",
        "-vf",
        "select=eq(n\\,10)+eq(n\\,20)+eq(n\\,42),showinfo=checksum=0,format=rgb24",
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

    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.resolve_executable", lambda _: str(tmp_path / "ffmpeg")
    )

    output_dir = tmp_path / "staging"
    facts = DefaultFFmpegRunner().extract_frames(Path("clip.mkv"), [10, 20, 42], output_dir)

    assert [(fact.source_frame, fact.picture_type) for fact in facts] == [
        (10, "I"),
        (20, "B"),
        (42, "P"),
    ]
    assert run_subprocess.call_args.args[0][-1] == "%09d.png"
    assert run_subprocess.call_args.kwargs["cwd"] == output_dir
    assert run_subprocess.call_args.kwargs["timeout_seconds"] == 30.0


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


@pytest.mark.parametrize(
    ("count", "configured", "budget"),
    [
        pytest.param(4, 5.0, 31.0, id="small_count"),
        pytest.param(86_400, 30.0, 21_630.0, id="long_count"),
        pytest.param(4, 100.0, 100.0, id="configured_override"),
    ],
)
def test_ffmpeg_count_uses_scaled_budget_and_reports_it_on_timeout(
    monkeypatch: pytest.MonkeyPatch, count: int, configured: float, budget: float
) -> None:
    def timeout(argv: list[str], *, timeout_seconds: float, abort: object) -> None:
        raise subprocess.TimeoutExpired(argv, timeout_seconds)

    run_subprocess = MagicMock(side_effect=timeout)
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner(extraction_timeout_seconds=configured)
    with pytest.raises(FrameExtractionError) as exc:
        runner.validate_source_frame_count(Path("clip.mkv"), count, 0)

    assert run_subprocess.call_args.kwargs["timeout_seconds"] == budget
    assert f"timed out after {budget} seconds" in exc.value.context.message
    assert exc.value.context.hint == (
        "Use the VapourSynth renderer or raise screenshots.ffmpeg_timeout_seconds"
    )


@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
def test_default_ffmpeg_runner_extraction_uses_configured_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, batch: bool
) -> None:
    run_subprocess = MagicMock(side_effect=subprocess.TimeoutExpired(["ffmpeg"], 47))
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.resolve_executable", lambda _: str(tmp_path / "ffmpeg")
    )

    runner = DefaultFFmpegRunner(extraction_timeout_seconds=47.0)
    with pytest.raises(FFmpegError):
        if batch:
            runner.extract_frames(Path("clip.mkv"), [1, 2], tmp_path)
        else:
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
    "signal, complete",
    [
        pytest.param((2, 2, 1), False, id="matrix_only"),
        pytest.param((2, 16, 2), False, id="transfer_only"),
        pytest.param((9, 2, 2), False, id="primaries_only"),
        pytest.param((1, 1, 1), True, id="sdr"),
        pytest.param((9, 16, 9), True, id="hdr"),
    ],
)
def test_ffmpeg_probe_color_signal_cases(
    monkeypatch: pytest.MonkeyPatch, signal: tuple[int, int, int], complete: bool
) -> None:
    primaries, transfer, matrix = signal
    metadata = HDRMetadata(None, None, None, primaries, transfer, matrix)
    probe = MagicMock(return_value=metadata)
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.probe_hdr_metadata", probe)
    result = DefaultFFmpegRunner().probe_hdr(Path("clip.mkv"))
    if complete:
        assert result is metadata
    else:
        assert result is None
    probe.assert_called_once_with(Path("clip.mkv"))


@pytest.mark.parametrize(
    "failure, input_path, expected_error, check_details",
    [
        pytest.param(
            FileNotFoundError(), Path("clip.mkv"), FFmpegNotFoundError, False, id="missing_binary"
        ),
        pytest.param(
            subprocess.CalledProcessError(1, ["ffmpeg"], stderr=b"No such file or directory"),
            Path("nonexistent.mkv"),
            FFmpegError,
            True,
            id="missing_input",
        ),
    ],
)
def test_ffmpeg_extract_wraps_external_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: Exception,
    input_path: Path,
    expected_error: type[FFmpegError],
    check_details: bool,
) -> None:
    run_subprocess = MagicMock(side_effect=failure)
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)
    with pytest.raises(expected_error) as exc_info:
        DefaultFFmpegRunner().extract_frame(input_path, 1, tmp_path / "frame.png")
    if check_details:
        details = exc_info.value.context.details
        assert details is not None
        assert details["returncode"] == 1
        assert "No such file or directory" in str(details["stderr"])
