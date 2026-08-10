from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.utils.ffmpeg_errors import FFmpegError
from frame_compare.vs.hdr_probe import probe_hdr_metadata


def _completed(stdout: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=b"")


def test_probe_hdr_metadata_maps_pq_bt2020_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    run_subprocess = MagicMock(
        return_value=_completed(
            b'{"streams":[{"color_transfer":"smpte2084",'
            b'"color_primaries":"bt2020","color_space":"bt2020nc"}]}'
        )
    )
    monkeypatch.setattr("frame_compare.vs.hdr_probe.run_subprocess", run_subprocess)

    metadata = probe_hdr_metadata(Path("hdr.mkv"))

    assert metadata is not None
    assert metadata.transfer == 16
    assert metadata.color_primaries == 9
    assert metadata.matrix == 9
    run_subprocess.assert_called_once_with(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=color_transfer,color_primaries,color_space",
            "-of",
            "json",
            "hdr.mkv",
        ],
        timeout_seconds=15.0,
    )


def test_probe_hdr_metadata_preserves_explicit_sdr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "frame_compare.vs.hdr_probe.run_subprocess",
        lambda _argv, *, timeout_seconds: _completed(
            b'{"streams":[{"color_transfer":"bt709",'
            b'"color_primaries":"bt709","color_space":"bt709"}]}'
        ),
    )

    metadata = probe_hdr_metadata(Path("sdr.mkv"))

    assert metadata is not None
    assert metadata.transfer == 1
    assert metadata.color_primaries == 1
    assert metadata.matrix == 1


@pytest.mark.parametrize("payload", [b'{"streams":[]}', b'{"streams":[{}]}'])
def test_probe_hdr_metadata_returns_none_without_recognized_signal(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    monkeypatch.setattr(
        "frame_compare.vs.hdr_probe.run_subprocess",
        lambda _argv, *, timeout_seconds: _completed(payload),
    )

    assert probe_hdr_metadata(Path("unknown.mkv")) is None


@pytest.mark.parametrize(
    ("payload", "expected_transfer", "expected_primaries"),
    [
        (
            b'{"streams":[{"color_transfer":"unknown","color_primaries":"bt2020"}]}',
            2,
            9,
        ),
        (
            b'{"streams":[{"color_transfer":"smpte2084","color_primaries":"unknown"}]}',
            16,
            2,
        ),
    ],
)
def test_probe_hdr_metadata_preserves_recognized_partial_signal(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    expected_transfer: int,
    expected_primaries: int,
) -> None:
    monkeypatch.setattr(
        "frame_compare.vs.hdr_probe.run_subprocess",
        lambda _argv, *, timeout_seconds: _completed(payload),
    )

    metadata = probe_hdr_metadata(Path("partial.mkv"))

    assert metadata is not None
    assert metadata.transfer == expected_transfer
    assert metadata.color_primaries == expected_primaries
    assert metadata.matrix == 2


@pytest.mark.parametrize("payload", [b"not-json", b"[]"])
def test_probe_hdr_metadata_rejects_malformed_payload(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    monkeypatch.setattr(
        "frame_compare.vs.hdr_probe.run_subprocess",
        lambda _argv, *, timeout_seconds: _completed(payload),
    )

    with pytest.raises(FFmpegError):
        probe_hdr_metadata(Path("malformed.mkv"))
