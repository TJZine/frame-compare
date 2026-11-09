from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import frame_compare.vs.source_admission as admission_module
from frame_compare.utils.canvas import MAX_CANVAS_PIXELS
from frame_compare.vs.source_admission import admit_source, bounded_decoder_options

_VIDEO: dict[str, object] = {
    "index": 2,
    "width": 62,
    "height": 66,
    "coded_width": 64,
    "coded_height": 72,
}
_COVER = {
    "index": 0,
    "width": 64,
    "height": 64,
    "coded_width": 64,
    "coded_height": 64,
    "disposition": {"attached_pic": 1},
}


@pytest.fixture
def executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    executable = tmp_path / "ffprobe"
    executable.touch()
    monkeypatch.setattr(
        admission_module, "resolve_optional_executable", lambda _name: str(executable)
    )
    return executable


@pytest.fixture
def video(tmp_path: Path, executable: Path) -> Path:
    path = tmp_path / "video.mkv"
    path.write_bytes(b"fixture")
    return path


def _record(index: int, width: int, height: int, *, trailing_pipe: bool = False) -> bytes:
    suffix = b"|" if trailing_pipe else b""
    return (
        (
            f"frame|stream_index={index}|width={width}|height={height}|"
            "crop_top=0|crop_bottom=0|crop_left=0|crop_right=0"
        ).encode()
        + suffix
        + b"\n"
    )


def test_frame_scan_accepts_chunked_constant_dimensions() -> None:
    scan = admission_module._FrameGeometryScan({0, 2})
    payload = _record(0, 64, 64, trailing_pipe=True) + _record(2, 1920, 1080)

    for offset in range(0, len(payload), 17):
        scan.feed(payload[offset : offset + 17])
    scan.finish()

    assert scan.sizes == {0: (64, 64, 64, 64), 2: (1920, 1080, 1920, 1080)}


@pytest.mark.parametrize(
    ("second", "message"),
    [
        (_record(0, 128, 64), "dimensions change"),
        (_record(0, 8192, 64), "7,680 pixels per axis"),
        (_record(1, 64, 64), "unverified video stream"),
        (b"frame|stream_index=0|width=NAN\n", "could not be verified"),
    ],
)
def test_frame_scan_rejects_unsafe_or_unproven_followup(second: bytes, message: str) -> None:
    scan = admission_module._FrameGeometryScan({0})
    scan.feed(_record(0, 64, 64))

    with pytest.raises(ValueError, match=message):
        scan.feed(second)


def test_frame_scan_requires_a_complete_record_for_every_stream() -> None:
    scan = admission_module._FrameGeometryScan({0, 1})
    scan.feed(_record(0, 64, 64))

    with pytest.raises(ValueError, match="could not be verified"):
        scan.finish()


def test_scan_streams_output_without_buffering_the_complete_probe(
    video: Path, executable: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command: list[str] = []

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        command.extend(argv)
        consumer = kwargs["stdout_consumer"]
        assert callable(consumer)
        consumer(_record(0, 64, 64)[:31])
        consumer(_record(0, 64, 64)[31:])
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(admission_module, "run_subprocess", run)
    admission_module._scan_video_frames(video, {0}, lambda: False, executable)

    assert "-show_entries" in command
    assert (
        "frame=stream_index,width,height,crop_top,crop_bottom,crop_left,crop_right:frame_side_data="
        in command
    )
    assert "-max_pixels" in command


def test_admission_probes_headers_once_and_selects_the_real_stream(
    video: Path, executable: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_stream = {**_VIDEO, "color_transfer": "smpte2084"}
    run_subprocess = MagicMock(
        return_value=subprocess.CompletedProcess(
            [str(executable)],
            0,
            json.dumps(
                {
                    "streams": [_COVER, real_stream],
                    "program_version": {"version": "7.1.5"},
                    "library_versions": [{"name": "libavcodec", "version": 61}],
                }
            ).encode(),
            b"",
        )
    )
    monkeypatch.setattr("frame_compare.vs.hdr_probe.run_subprocess", run_subprocess)

    admitted = admit_source(video, abort_check=lambda: None)

    assert admitted.video_stream == real_stream
    assert admitted.geometry_probe_token is not None
    run_subprocess.assert_called_once()
    argv, kwargs = run_subprocess.call_args.args[0], run_subprocess.call_args.kwargs
    assert argv == [
        str(executable),
        "-v",
        "error",
        "-max_pixels",
        str(MAX_CANVAS_PIXELS),
        "-select_streams",
        "v",
        "-show_program_version",
        "-show_library_versions",
        "-show_entries",
        "stream=index,coded_width,coded_height,width,height,color_transfer,color_primaries,"
        "color_space:stream_disposition=attached_pic",
        "-of",
        "json",
        str(video),
    ]
    assert kwargs["timeout_seconds"] == 15.0
    assert kwargs["max_stdout_bytes"] == 256 * 1024
    assert kwargs["max_stderr_bytes"] == 64 * 1024
    admitted.verify(video)


def test_geometry_probe_token_binds_executable_and_runtime(
    video: Path, executable: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload: dict[str, object] = {
        "program_version": {"version": "7.1.5"},
        "library_versions": [{"name": "libavcodec", "version": 61}],
    }
    monkeypatch.setattr(
        admission_module, "probe_admission_headers", lambda *_args, **_kwargs: ([_VIDEO], payload)
    )

    first = admit_source(video, abort_check=lambda: None)
    assert first.geometry_probe_token is not None
    executable.write_bytes(b"replacement executable")
    with pytest.raises(ValueError, match="FFprobe executable changed"):
        first.verify(video)

    replaced = admit_source(video, abort_check=lambda: None)
    assert replaced.geometry_probe_token not in {None, first.geometry_probe_token}
    payload["library_versions"] = [{"name": "libavcodec", "version": 62}]
    changed_runtime = admit_source(video, abort_check=lambda: None)
    assert changed_runtime.geometry_probe_token not in {None, replaced.geometry_probe_token}


@pytest.mark.parametrize(
    ("streams", "message"),
    [
        ([], "no verifiable video stream"),
        ([_COVER], "no verifiable video stream"),
        ([_VIDEO, {**_VIDEO, "index": 3}], "multiple video streams"),
        ([{**_VIDEO, "width": None}], "Source video dimensions could not be verified"),
        ([{**_VIDEO, "height": 0}], "Source video dimensions are out of bounds"),
        ([{**_VIDEO, "coded_width": None}], "Coded source video dimensions could not be verified"),
        ([{**_VIDEO, "coded_height": 0}], "Coded source video dimensions are out of bounds"),
        ([{**_VIDEO, "coded_width": 7680, "coded_height": 4321}], "33,177,600 pixels total"),
        ([_VIDEO, {**_COVER, "coded_width": 7681}], "7,680 pixels per axis"),
    ],
)
def test_admission_rejects_unsupported_headers(
    video: Path,
    monkeypatch: pytest.MonkeyPatch,
    streams: list[dict[str, object]],
    message: str,
) -> None:
    monkeypatch.setattr(
        admission_module, "probe_admission_headers", lambda *_args, **_kwargs: (streams, {})
    )

    with pytest.raises(ValueError, match=message):
        admit_source(video, abort_check=lambda: None)


def test_admission_rejects_source_changed_during_header_probe(
    video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def probe(
        path: Path, *_args: object, **_kwargs: object
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        path.write_bytes(b"new file contents")
        return [_VIDEO], {}

    monkeypatch.setattr(admission_module, "probe_admission_headers", probe)

    with pytest.raises(ValueError, match="Source video changed during admission"):
        admit_source(video, abort_check=lambda: None)


def test_decoder_options_replace_the_callers_pixel_limit() -> None:
    limit = f"max_pixels={MAX_CANVAS_PIXELS}"
    assert bounded_decoder_options() == limit
    assert bounded_decoder_options("threads=2 max_pixels=999999999 MAX_PIXELS='0'") == (
        f"threads=2 {limit}"
    )
    assert bounded_decoder_options(r"quoted='a max_pixels=1' escaped=a\ b") == (
        rf"quoted='a max_pixels=1' escaped=a\ b {limit}"
    )


@pytest.mark.parametrize(
    "options",
    ["key", "key='unterminated", "key=''", "key=value\\", "key=value\nother=value", "key=\0"],
)
def test_decoder_options_reject_ambiguous_syntax(options: str) -> None:
    with pytest.raises(ValueError, match="complete key=value pairs"):
        bounded_decoder_options(options)
