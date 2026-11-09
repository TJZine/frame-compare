from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import frame_compare.vs.source_admission as admission_module
from frame_compare.utils.canvas import MAX_CANVAS_PIXELS
from frame_compare.vs.source_admission import admit_source, bounded_decoder_options


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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "video.mkv"
    video.touch()
    command: list[str] = []

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        command.extend(argv)
        consumer = kwargs["stdout_consumer"]
        assert callable(consumer)
        consumer(_record(0, 64, 64)[:31])
        consumer(_record(0, 64, 64)[31:])
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(admission_module, "run_subprocess", run)
    admission_module._scan_video_frames(video, {0}, lambda: False)

    assert "-show_entries" in command
    assert (
        "frame=stream_index,width,height,crop_top,crop_bottom,crop_left,crop_right:frame_side_data="
        in command
    )
    assert "-max_pixels" in command


def test_admission_scans_every_video_stream_but_selects_one_real_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "video.mkv"
    video.write_bytes(b"fixture")
    streams = [
        {
            "index": 0,
            "width": 64,
            "height": 64,
            "disposition": {"attached_pic": 1},
        },
        {"index": 2, "width": 1920, "height": 1080, "disposition": {}},
    ]
    probe = MagicMock(return_value=streams)
    scan = MagicMock()
    monkeypatch.setattr(admission_module, "resolve_optional_executable", lambda _name: "/ffprobe")
    monkeypatch.setattr(admission_module, "probe_video_streams", probe)
    monkeypatch.setattr(admission_module, "_scan_video_frames", scan)

    admitted = admit_source(video, abort_check=lambda: None)

    assert admitted.streams == (streams[1],)
    probe.assert_called_once()
    assert probe.call_args.kwargs["include_attached"] is True
    scan.assert_called_once()
    assert scan.call_args.args[:2] == (video.absolute(), {0, 2})
    admitted.verify(video)


def test_decoder_options_keep_the_owned_pixel_limit_last() -> None:
    assert bounded_decoder_options() == f"max_pixels={MAX_CANVAS_PIXELS}"
    assert bounded_decoder_options("threads=2 max_pixels=999999999") == (
        f"threads=2 max_pixels=999999999 max_pixels={MAX_CANVAS_PIXELS}"
    )


@pytest.mark.parametrize("options", ["key", "key='unterminated", "key=value\nother=value"])
def test_decoder_options_reject_ambiguous_syntax(options: str) -> None:
    with pytest.raises(ValueError, match="complete key=value pairs"):
        bounded_decoder_options(options)
