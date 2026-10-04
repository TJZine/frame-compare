from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.utils.ffmpeg_errors import FFmpegError
from frame_compare.vs.hdr_probe import probe_hdr_metadata


def _completed(stdout: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=b"")


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


@pytest.mark.parametrize(
    "payload, filename, expected, check_command",
    [
        pytest.param(
            b'{"streams":[{"color_transfer":"smpte2084","color_primaries":"bt2020","color_space":"bt2020nc"}]}',
            "hdr.mkv",
            (16, 9, 9),
            True,
            id="pq_bt2020",
        ),
        pytest.param(
            b'{"streams":[{"color_transfer":"bt709","color_primaries":"bt709","color_space":"bt709"}]}',
            "sdr.mkv",
            (1, 1, 1),
            False,
            id="explicit_sdr",
        ),
        pytest.param(b'{"streams":[]}', "unknown.mkv", None, False, id="empty_streams"),
        pytest.param(b'{"streams":[{}]}', "unknown.mkv", None, False, id="empty_signal"),
        pytest.param(
            b'{"streams":[{"color_transfer":"unknown","color_primaries":"bt2020"}]}',
            "partial.mkv",
            (2, 9, 2),
            False,
            id="partial_primaries",
        ),
        pytest.param(
            b'{"streams":[{"color_transfer":"smpte2084","color_primaries":"unknown"}]}',
            "partial.mkv",
            (16, 2, 2),
            False,
            id="partial_transfer",
        ),
    ],
)
def test_probe_hdr_signal_cases(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    filename: str,
    expected: tuple[int, int, int] | None,
    check_command: bool,
) -> None:
    run_subprocess = MagicMock(return_value=_completed(payload))
    monkeypatch.setattr("frame_compare.vs.hdr_probe.run_subprocess", run_subprocess)
    metadata = probe_hdr_metadata(Path(filename))
    if expected is None:
        assert metadata is None
    else:
        assert metadata is not None
        assert (metadata.transfer, metadata.color_primaries, metadata.matrix) == expected
    if check_command:
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
