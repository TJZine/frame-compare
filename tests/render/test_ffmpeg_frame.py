import os
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
from frame_compare.vs.hdr_probe import probe_video_streams
from frame_compare.vs.types import HDRMetadata


@pytest.fixture(autouse=True)
def _stub_stream_headers_for_synthetic_video_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.probe_video_streams",
        lambda _path, **_kwargs: [{"width": 1920, "height": 1080}],
    )


def test_build_extract_frame_argv_supports_optional_overwrite() -> None:
    assert build_extract_frame_argv(
        video=Path("clip.mkv"),
        frame_num=100,
        output=Path("frame.png"),
        overwrite=False,
    ) == [
        "ffmpeg",
        "-noautorotate",
        "-max_pixels",
        "33177600",
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


def test_oversize_media_fails_before_ffmpeg_extraction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.probe_video_streams",
        lambda _path, **_kwargs: [{"width": 7681, "height": 2}],
    )
    run = MagicMock(side_effect=AssertionError("must validate before starting FFmpeg"))
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run)
    output = tmp_path / "out.png"
    with pytest.raises(FrameExtractionError, match="7,680 pixels per axis"):
        DefaultFFmpegRunner().extract_frame(Path("clip.mkv"), 0, output)
    run.assert_not_called()
    assert not output.exists()


@pytest.mark.skipif(os.name != "posix", reason="Uses synthetic POSIX media executables")
def test_ffmpeg_and_ffprobe_children_filter_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.probe_video_streams", probe_video_streams
    )
    monkeypatch.setenv("FRAME_COMPARE_SLOWPICS__WEBHOOK_URL", "fixture-hook")
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "fixture-api-key")
    monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", "fixture-plugin-path")
    for tool, response in (
        ("ffprobe", 'printf \'%s\' \'{"streams":[{"width":1920,"height":1080}]}\''),
        (
            "ffmpeg",
            "for output do :; done\n"
            "printf '%s' 'image' > \"$output\"\n"
            "printf '%s' '[Parsed_showinfo_1 @ 0x1] n:0 type:I' >&2",
        ),
    ):
        script = tmp_path / tool
        script.write_text(
            "#!/bin/sh\n"
            '[ -z "$FRAME_COMPARE_SLOWPICS__WEBHOOK_URL" ] || exit 7\n'
            '[ -z "$FRAME_COMPARE_TMDB__API_KEY" ] || exit 7\n'
            '[ "$VAPOURSYNTH_EXTRA_PLUGIN_PATH" = fixture-plugin-path ] || exit 7\n'
            f"{response}\n",
            encoding="utf-8",
        )
        script.chmod(0o700)
        monkeypatch.setenv(f"FRAME_COMPARE_{tool.upper()}_EXECUTABLE", str(script))
    result = DefaultFFmpegRunner().extract_frame(Path("clip.mkv"), 0, tmp_path / "out.png")
    assert result.picture_type == "I"


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

    with pytest.raises(ValueError, match="Scaled frame dimensions are out of bounds"):
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
        "-max_pixels",
        "33177600",
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


def test_default_ffmpeg_runner_extract_frame_uses_shared_command_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def extract(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        staged_path = Path(argv[-1])
        assert staged_path != output
        assert staged_path.parent.parent == output.parent
        staged_path.write_bytes(b"image")
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    run_subprocess = MagicMock(side_effect=extract)
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", run_subprocess)

    runner = DefaultFFmpegRunner()
    output = tmp_path / "shots" / "frame.png"
    runner.extract_frame(Path("clip.mkv"), 100, output)

    run_subprocess.assert_called_once()
    assert run_subprocess.call_args.kwargs == {
        "timeout_seconds": 30.0,
        "abort": None,
        "max_stdout_bytes": 8192,
        "max_stderr_bytes": 128 * 1024,
        "cwd": None,
    }
    assert output.read_bytes() == b"image"


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
    assert run_subprocess.call_args.kwargs["max_stderr_bytes"] == 2 * 1024 * 1024


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
        runner.validate_source(Path("clip.mkv"), (1920, 1080), count, 0)

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


@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
@pytest.mark.parametrize("width", [1280, 7681], ids=["in-limit-replacement", "oversize"])
def test_supplied_plan_cannot_bypass_live_geometry_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, batch: bool, width: int
) -> None:
    from frame_compare.render.geometry import plan_render_geometry

    [plan] = plan_render_geometry(
        (SourceGeometry(1920, 1080, GeometryRect(0, 0, 1920, 1080), "full_frame"),),
        mode="native",
    )
    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.probe_video_streams",
        lambda _path, **_kwargs: [{"width": width, "height": 720}],
    )
    extraction = MagicMock(side_effect=AssertionError("must refuse stale geometry before decode"))
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", extraction)
    output = tmp_path / "frame.png"
    output.write_bytes(b"existing image")
    with pytest.raises(FrameExtractionError, match="dimensions"):
        if batch:
            DefaultFFmpegRunner().extract_frames(
                Path("clip.mkv"), [0, 1], tmp_path, geometry_plan=plan
            )
        else:
            DefaultFFmpegRunner().extract_frame(Path("clip.mkv"), 0, output, geometry_plan=plan)
    extraction.assert_not_called()
    assert output.read_bytes() == b"existing image"
    assert not list(tmp_path.glob(".frame-compare-ffmpeg-*"))


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b'{"streams":[{"width":1920,"height":1080,"nb_read_frames":"100"}]}', None),
        (
            b'{"streams":[{"width":1280,"height":720,"nb_read_frames":"100"}]}',
            "disagree with prepared",
        ),
        (
            b'{"streams":[{"width":1920,"height":1080,"nb_read_frames":"99"}]}',
            "FFmpeg decoded 99 frames",
        ),
        (b'{"streams":[{"width":1920,"height":1080,"nb_read_frames":"N/A"}]}', "Could not count"),
        (
            b'{"streams":[{"width":true,"height":1080,"nb_read_frames":"100"}]}',
            "could not be verified",
        ),
        (b'{"streams":[{"height":1080,"nb_read_frames":"100"}]}', "could not be verified"),
        (b'{"streams":[]}', "Exactly one"),
        (b'{"streams":[{},{}]}', "Exactly one"),
        (b'{"streams":[42]}', "Could not count"),
        (
            b'{"streams":[{"width":64,"height":64,"nb_read_frames":"100","disposition":{"attached_pic":1}}]}',
            "Exactly one",
        ),
        (b"[]", "Could not count"),
        (b"{invalid", "Expecting property name"),
    ],
)
def test_live_count_probe_validates_selected_geometry_and_count(
    monkeypatch: pytest.MonkeyPatch, payload: bytes, message: str | None
) -> None:
    probe = MagicMock(return_value=subprocess.CompletedProcess(["ffprobe"], 0, payload, b""))
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", probe)
    runner = DefaultFFmpegRunner()
    if message is None:
        runner.validate_source(Path("clip.mkv"), (1920, 1080), 100, 5)
    else:
        with pytest.raises(FrameExtractionError, match=message):
            runner.validate_source(Path("clip.mkv"), (1920, 1080), 100, 5)
    probe.assert_called_once()
    argv = probe.call_args.args[0]
    assert argv[argv.index("-select_streams") + 1] == "V:0"
    assert argv[argv.index("-show_entries") + 1] == "stream=width,height,nb_read_frames"
    assert argv[argv.index("-of") + 1] == "json"
    assert "-count_frames" in argv


@pytest.mark.parametrize("width", [1920, 1280])
def test_unknown_count_uses_only_current_header_geometry(
    monkeypatch: pytest.MonkeyPatch, width: int
) -> None:
    header = MagicMock(return_value=[{"width": width, "height": 1080}])
    count = MagicMock(side_effect=AssertionError("unknown count must not trigger full decode"))
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.probe_video_streams", header)
    monkeypatch.setattr("frame_compare.render.backend.ffmpeg.run_subprocess", count)
    if width == 1920:
        DefaultFFmpegRunner().validate_source(Path("clip.mkv"), (1920, 1080), None, 0)
    else:
        with pytest.raises(FrameExtractionError, match="disagree with prepared"):
            DefaultFFmpegRunner().validate_source(Path("clip.mkv"), (1920, 1080), None, 0)
    header.assert_called_once()
    count.assert_not_called()
