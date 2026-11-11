from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from time import time_ns
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from vapoursynth import Core

import frame_compare.vs.source_admission as admission_module
from frame_compare.utils.canvas import MAX_CANVAS_PIXELS
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.errors import SourceLoadError
from frame_compare.vs.source import load_source
from frame_compare.vs.source_admission import (
    SourceGeometryError,
    admit_source,
    bounded_decoder_options,
    source_identity,
)

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


def test_source_identity_distinguishes_an_immediate_same_size_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"original")
    before = source.stat()

    identity = source_identity(source)
    # NTFS and Linux without multigrain timestamps can give two changes within one
    # clock interval the same change time. Local filesystems with fine-grained change
    # times cannot reproduce that, so check that the interval has passed as well.
    assert time_ns() - identity.change_time >= admission_module._CHANGE_TIME_SETTLE_NS
    with source.open("r+b") as handle:
        handle.write(b"replaced")
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = source.stat()

    assert os.path.samestat(before, after)
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert source_identity(source) != identity


def test_source_identity_refuses_a_change_time_ahead_of_the_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"video")

    def unexpected_sleep(_seconds: float) -> None:
        raise AssertionError("a future change time must not block")

    # A share whose server clock leads this machine reports such change times.
    monkeypatch.setattr(admission_module, "time_ns", lambda: 0)
    monkeypatch.setattr(admission_module, "sleep", unexpected_sleep)

    with pytest.raises(OSError, match="ahead of the system clock"):
        source_identity(source)


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

    assert command == [
        str(executable),
        "-v",
        "error",
        "-max_pixels",
        str(MAX_CANVAS_PIXELS),
        "-threads",
        "0",
        "-apply_cropping",
        "0",
        "-select_streams",
        "v",
        "-show_entries",
        "frame=stream_index,width,height,crop_top,crop_bottom,crop_left,crop_right:frame_side_data=",
        "-of",
        "compact=p=1:nk=0",
        str(video),
    ]


@pytest.mark.parametrize("decoration", [b"", b" [1;31m"], ids=["plain", "forced-color"])
def test_scan_refuses_probe_pixel_limit_diagnostic_on_zero_exit(
    video: Path, executable: Path, monkeypatch: pytest.MonkeyPatch, decoration: bytes
) -> None:
    # Place the verified libavutil message beyond the user-facing excerpt.
    preceding = b"[h264 @ 0x123] non-existing PPS 0 referenced\n" * 20
    stderr = (
        preceding
        + b"[h264 @ 0x123] [IMGUTILS @ 0x456] "
        + decoration
        + (
            b"Picture size 8192x4320 exceeds specified max pixel "
            b"count 33177600, see the documentation if you wish to increase it\n"
        )
    )

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        consumer = kwargs["stdout_consumer"]
        assert callable(consumer)
        consumer(_record(0, 64, 64))
        return subprocess.CompletedProcess(argv, 0, b"", stderr)

    monkeypatch.setattr(admission_module, "run_subprocess", run)
    reason = "FFprobe rejected a source video picture at its pixel limit"
    with pytest.raises(ValueError, match=reason) as error:
        admission_module._scan_video_frames(video, {0}, lambda: False, executable)

    assert str(error.value) == f"{reason}: {preceding[:512].decode().strip()}"


@pytest.fixture
def encode_ts() -> Callable[[Path, str, int, int], None]:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg tools are unavailable")

    def encode(path: Path, size: str, seconds: int, gop: int) -> None:
        run_subprocess(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={size}:rate=24",
                "-t",
                str(seconds),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-g",
                str(gop),
                "-sc_threshold",
                "0",
                "-f",
                "mpegts",
                str(path),
            ],
            timeout_seconds=30,
        )

    return encode


def test_scan_admits_mpegts_cut_mid_gop(
    tmp_path: Path, encode_ts: Callable[[Path, str, int, int], None]
) -> None:
    original = tmp_path / "full.ts"
    encode_ts(original, "1280x720", 8, 96)
    data = original.read_bytes()
    packet_bytes = 188
    start = len(data) // (3 * packet_bytes) * packet_bytes
    cut = tmp_path / "cut.ts"
    cut.write_bytes(data[start:])

    admission = admit_source(cut, abort_check=lambda: None)
    admission.scan(cut, abort_check=lambda: None)


def test_scan_refuses_mixed_resolution_mpegts_before_native_open(
    tmp_path: Path, encode_ts: Callable[[Path, str, int, int], None]
) -> None:
    first, second = tmp_path / "720p.ts", tmp_path / "1080p.ts"
    encode_ts(first, "1280x720", 1, 24)
    encode_ts(second, "1920x1080", 1, 24)
    joined = tmp_path / "joined.ts"
    joined.write_bytes(first.read_bytes() + second.read_bytes())
    loader = MagicMock()

    with pytest.raises(SourceLoadError, match="dimensions change within a stream"):
        load_source(joined, cast(Core, SimpleNamespace(lsmas=loader)))

    loader.LWLibavSource.assert_not_called()


@pytest.mark.skipif(os.name == "nt", reason="The sleeping ffprobe fixture uses a POSIX executable")
@pytest.mark.parametrize(
    ("stop", "reason"),
    [
        ("stall", "Source video frame scan made no progress for 0.5 seconds"),
        ("stdout-cap", "Source video frame scan exceeded its output limit"),
        ("invalid-frame", "Source video frame dimensions could not be verified"),
    ],
)
def test_scan_reports_bounded_diagnostics_when_stopped(
    video: Path, executable: Path, monkeypatch: pytest.MonkeyPatch, stop: str, reason: str
) -> None:
    secret = "fixture-signing-secret"
    marker = executable.with_suffix(".finished")
    script = f"#!/bin/sh\nprintf 'diagnostic \\033\\007{secret} {'x' * 2048}\\n' >&2\n"
    if stop == "stall":
        monkeypatch.setattr(admission_module, "_SCAN_STALL_SECONDS", 0.5, raising=False)
    else:
        script += "sleep 0.2\nprintf 'invalid frame\\n'\n"
    if stop == "stdout-cap":
        monkeypatch.setattr(admission_module, "_SCAN_STDOUT_BYTES", 4)
    script += 'sleep 2\n: > "$0.finished"\n'
    executable.write_text(script, encoding="ascii")
    executable.chmod(0o700)
    monkeypatch.setenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", str(executable))
    monkeypatch.setenv("WINDOWS_UPDATE_SIGNING_KEY_XML", secret)

    with pytest.raises(ValueError, match=reason) as error:
        admission_module._scan_video_frames(video, {0}, lambda: False, executable)

    assert not marker.exists()
    excerpt = str(error.value).removeprefix(f"{reason}: ")
    assert excerpt.startswith("diagnostic   <redacted> ")
    assert len(excerpt.encode()) == 512
    assert secret not in excerpt
    assert "\x1b" not in excerpt and "\x07" not in excerpt


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
                    "format": {"format_name": "matroska,webm"},
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
        "color_space:stream_disposition=attached_pic:format=format_name",
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
        "format": {"format_name": "matroska,webm"},
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
    "format_facts",
    [
        pytest.param({}, id="missing-format"),
        pytest.param({"format": "matroska,webm"}, id="malformed-format"),
        pytest.param({"format": {}}, id="missing-format-name"),
        pytest.param({"format": {"format_name": ["matroska,webm"]}}, id="malformed-format-name"),
        pytest.param({"format": {"format_name": "concat"}}, id="referencing-demuxer"),
        pytest.param({"format": {"format_name": "matroska,webm,other"}}, id="unknown-demuxer"),
    ],
)
def test_admission_refuses_unrecognized_or_missing_format(
    video: Path, monkeypatch: pytest.MonkeyPatch, format_facts: dict[str, object]
) -> None:
    payload = {
        **format_facts,
        "program_version": {"version": "7.1.5"},
        "library_versions": [{"name": "libavcodec", "version": 61}],
    }
    monkeypatch.setattr(
        admission_module, "probe_admission_headers", lambda *_args, **_kwargs: ([_VIDEO], payload)
    )

    with pytest.raises(ValueError, match="container format is not supported"):
        admit_source(video, abort_check=lambda: None)


@pytest.mark.parametrize(
    ("frames", "message"),
    [
        pytest.param(_record(2, 64, 72) * 2, None, id="complete"),
        pytest.param(b"", "could not be verified", id="missing"),
        pytest.param(_record(2, 7681, 72), "7,680 pixels per axis", id="oversize"),
    ],
)
def test_unknown_coded_header_requires_fresh_frame_geometry(
    video: Path,
    monkeypatch: pytest.MonkeyPatch,
    frames: bytes,
    message: str | None,
) -> None:
    stream = {**_VIDEO, "coded_width": 0, "coded_height": 0}
    payload = {
        "format": {"format_name": "mpegvideo"},
        "program_version": {"version": "7.1.5"},
        "library_versions": [{"name": "libavcodec", "version": 61}],
    }
    monkeypatch.setattr(
        admission_module, "probe_admission_headers", lambda *_args, **_kwargs: ([stream], payload)
    )

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        consumer = kwargs["stdout_consumer"]
        assert callable(consumer)
        consumer(frames)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(admission_module, "run_subprocess", run)
    admission = admit_source(video, abort_check=lambda: None)
    assert admission.geometry_probe_token is None
    if message is None:
        admission.scan(video, abort_check=lambda: None)
    else:
        with pytest.raises(SourceGeometryError, match=message):
            admission.scan(video, abort_check=lambda: None)


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
        ([_VIDEO, {**_COVER, "coded_width": 0, "coded_height": 0}], "dimensions are out of bounds"),
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
        admission_module,
        "probe_admission_headers",
        lambda *_args, **_kwargs: (streams, {"format": {"format_name": "matroska,webm"}}),
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
        return [_VIDEO], {"format": {"format_name": "matroska,webm"}}

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


@pytest.mark.parametrize("caller", ["source", "preview"])
@pytest.mark.parametrize("format_name", ["concat", "unknown", "", None, ["avi"]])
def test_native_callers_refuse_unverifiable_formats_before_scan_or_open(
    video: Path, monkeypatch: pytest.MonkeyPatch, caller: str, format_name: object
) -> None:
    from typing import Any

    from frame_compare.vsview.session_runtime import load_preview_source

    monkeypatch.setattr(
        admission_module,
        "probe_admission_headers",
        lambda *_args, **_kwargs: (
            [_VIDEO],
            {"format": {"format_name": format_name}},
        ),
    )
    scan = MagicMock(side_effect=AssertionError("refused formats must never scan"))
    monkeypatch.setattr(admission_module, "_scan_video_frames", scan)
    loader = MagicMock()
    with pytest.raises((ValueError, SourceLoadError), match="container format is not supported"):
        if caller == "preview":
            load_preview_source(loader, video, None)
        else:
            core = MagicMock(lsmas=loader)
            load_source(video, cast(Any, core))
    scan.assert_not_called()
    loader.LWLibavSource.assert_not_called()


@pytest.mark.parametrize("caller", ["source", "preview"])
@pytest.mark.parametrize("coded_header", [False, True], ids=["unknown-coded", "known-coded"])
def test_elementary_mpeg2_scans_before_private_native_open(
    video: Path, monkeypatch: pytest.MonkeyPatch, caller: str, coded_header: bool
) -> None:
    from typing import Any

    from frame_compare.vs.source_index_cache import ManagedSourceIndexCache
    from frame_compare.vsview.session_runtime import load_preview_source

    stream = dict(_VIDEO) if coded_header else {**_VIDEO, "coded_width": 0, "coded_height": 0}
    monkeypatch.setattr(
        admission_module,
        "probe_admission_headers",
        lambda *_args, **_kwargs: (
            [stream],
            {"format": {"format_name": "mpegvideo"}},
        ),
    )
    scanned: list[Path] = []
    monkeypatch.setattr(
        admission_module, "_scan_video_frames", lambda path, *_args: scanned.append(path)
    )
    clip = MagicMock(
        width=62, height=66, num_frames=2, fps=SimpleNamespace(numerator=24, denominator=1)
    )
    clip.get_frame.return_value.props = {}
    indices: list[Path] = []

    def open_source(path: str, **kwargs: object):
        assert scanned == [video] * (len(indices) + 1)
        assert kwargs["cache"] == 0
        index = Path(cast(str, kwargs["cachefile"]))
        assert index.name == "disabled.lwi" and not index.exists()
        indices.append(index)
        return clip

    loader = MagicMock()
    loader.LWLibavSource.side_effect = open_source
    for _ in range(2):
        if caller == "preview":
            _, admitted = load_preview_source(loader, video, None)
            assert admitted.format_name == "mpegvideo"
            assert admitted.geometry_probe_token is None
        else:
            load_source(
                video,
                cast(Any, SimpleNamespace(lsmas=loader)),
                index_cache=ManagedSourceIndexCache(video.parent / "generated"),
            )
    assert len(indices) == 2
    assert all(not index.parent.exists() for index in indices)
