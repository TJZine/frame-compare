"""FFmpeg and ffprobe audio alignment tests."""

# pyright: reportPrivateUsage=false

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.services.alignment_audio import (
    AudioStreamInfo,
    AudioStreamTimeline,
    _PacketTailParser,
    collection_argv,
    measure_selected_audio_duration,
    probe_streams,
    retime_rates,
    select_audio_pair,
)
from frame_compare.services.alignment_audio import (
    probe_fps as _probe_fps,
)
from frame_compare.services.errors import AudioAlignmentCancellationError, AudioAlignmentError
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError


@pytest.mark.parametrize(
    "stdout, expected",
    [
        pytest.param(b"24000/1001\n", Fraction(24000, 1001), id="probe_fps_fraction"),
        pytest.param(
            b"24000/1001,\r\n", Fraction(24000, 1001), id="probe_fps_accepts_single_trailing_comma"
        ),
        pytest.param(b"24\n", Fraction(24, 1), id="probe_fps_integer"),
    ],
)
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_success(mock_run: MagicMock, stdout: bytes, expected: Fraction) -> None:
    mock_run.return_value.stdout = stdout
    assert _probe_fps(Path("test.mkv")) == expected
    assert mock_run.call_args.args[0] == [
        "ffprobe",
        "-v",
        "quiet",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate",
        "-of",
        "csv=p=0",
        "test.mkv",
    ]
    assert mock_run.call_args.kwargs["timeout_seconds"] == 15.0


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_empty_output_is_alignment_parse_error(mock_run: MagicMock) -> None:
    mock_run.return_value.stdout = b""

    with pytest.raises(AudioAlignmentError) as exc_info:
        _probe_fps(Path("test.mkv"))

    assert "empty" in str(exc_info.value)


@pytest.mark.parametrize("stdout", [b"not-a-rate\n", b"24000/1001,extra\n", b"24000/0\n"])
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_malformed_output_is_alignment_parse_error(
    mock_run: MagicMock, stdout: bytes
) -> None:
    mock_run.return_value.stdout = stdout

    with pytest.raises(AudioAlignmentError) as exc_info:
        _probe_fps(Path("test.mkv"))

    assert "ffprobe FPS output" in str(exc_info.value)
    assert stdout.decode("utf-8").strip() in str(exc_info.value.context.details)


@pytest.mark.parametrize(
    "failure, expected_error, details, no_traceback, returncode",
    [
        pytest.param(
            FileNotFoundError(),
            FFmpegNotFoundError,
            (),
            False,
            None,
            id="probe_fps_not_found_raises",
        ),
        pytest.param(
            CalledProcessError(1, ["ffprobe"], stderr=b"error"),
            FFmpegError,
            (),
            False,
            None,
            id="probe_fps_nonzero_exit_raises",
        ),
        pytest.param(
            OSError("permission denied"),
            FFmpegError,
            ("ffprobe", "could not start", "permission denied"),
            True,
            None,
            id="probe_fps_oserror_raises_ffmpeg_error",
        ),
        pytest.param(
            CalledProcessError(1, ["ffprobe"], stderr=b"\xfferror"),
            FFmpegError,
            ("\ufffderror",),
            False,
            None,
            id="probe_fps_non_utf8_stderr_is_replaced",
        ),
        pytest.param(
            TimeoutExpired(cmd=["ffprobe"], timeout=15.0),
            FFmpegError,
            ("timed out",),
            False,
            124,
            id="probe_fps_timeout_raises",
        ),
    ],
)
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_failure(
    mock_run: MagicMock,
    failure: Exception,
    expected_error: type[FFmpegError],
    details: tuple[str, ...],
    no_traceback: bool,
    returncode: int | None,
) -> None:
    mock_run.side_effect = failure
    with pytest.raises(expected_error) as exc_info:
        _probe_fps(Path("test.mkv"))
    if no_traceback:
        assert "traceback" not in str(exc_info.value).lower()
    if details:
        assert exc_info.value.context.details is not None
        for detail in details:
            assert detail in str(exc_info.value.context.details).lower()
    if returncode is not None:
        assert exc_info.value.context.details is not None
        assert exc_info.value.context.details.get("returncode") == returncode
        assert "timed out" in str(exc_info.value.context.details.get("stderr", ""))


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_prefers_non_commentary_default_then_channels(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 1,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 6,
          "channel_layout": "5.1",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 1},
          "tags": {"language": "eng"}
        },
        {
          "index": 2,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 2,
          "channel_layout": "stereo",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 0},
          "tags": {"language": "eng"}
        },
        {
          "index": 3,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 6,
          "channel_layout": "5.1",
          "sample_rate": "48000",
          "disposition": {"default": 0, "original": 1, "comment": 0},
          "tags": {"language": "eng"}
        }
      ]
    }
    """

    probed = probe_streams(Path("ref.mkv"))
    selected, _ = select_audio_pair(
        probed,
        probed,
        reference_path=Path("ref.mkv"),
        comparison_path=Path("ref.mkv"),
        reference_override=None,
        comparison_override=None,
    )

    assert selected.stream.audio_stream_index == 2
    assert selected.stream.absolute_stream_index == 3


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_streams_ffprobe_oserror_raises_ffmpeg_error(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = OSError("permission denied")

    with pytest.raises(FFmpegError) as exc_info:
        probe_streams(Path("reference.mkv"))

    assert "traceback" not in str(exc_info.value).lower()
    assert exc_info.value.context.details is not None
    message = str(exc_info.value.context.details).lower()
    assert "ffprobe" in message
    assert "could not start" in message
    assert "permission denied" in message


@pytest.mark.parametrize(
    "stdout, expected",
    [
        pytest.param(b"[]", ("invalid json", "object"), id="non-object-list"),
        pytest.param(b"null", ("invalid json", "object"), id="non-object-null"),
        pytest.param(b'"oops"', ("invalid json", "object"), id="non-object-string"),
        pytest.param(b'{"streams": {}}', ("stream list",), id="malformed-stream-list"),
        pytest.param(b'{"streams": [null]}', ("stream data",), id="malformed-stream-data"),
    ],
)
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_streams_rejects_invalid_json(
    mock_run: MagicMock, stdout: bytes, expected: tuple[str, ...]
) -> None:
    mock_run.return_value = MagicMock(stdout=stdout, returncode=0)
    with pytest.raises(FFmpegError) as exc_info:
        probe_streams(Path("reference.mkv"))
    assert exc_info.value.context.details is not None
    message = str(exc_info.value.context.details).lower()
    assert "ffprobe" in message
    for detail in expected:
        assert detail in message


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_treats_text_commentary_tag_as_commentary(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 1,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 6,
          "channel_layout": "5.1",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 0},
          "tags": {"language": "eng", "comment": "Director commentary"}
        },
        {
          "index": 2,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 2,
          "channel_layout": "stereo",
          "sample_rate": "48000",
          "disposition": {"default": 0, "original": 1, "comment": 0},
          "tags": {"language": "eng"}
        }
      ]
    }
    """

    probed = probe_streams(Path("ref.mkv"))
    selected, _ = select_audio_pair(
        probed,
        probed,
        reference_path=Path("ref.mkv"),
        comparison_path=Path("ref.mkv"),
        reference_override=None,
        comparison_override=None,
    )

    assert selected.stream.audio_stream_index == 1
    assert selected.stream.absolute_stream_index == 2


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_override_uses_audio_ordinal_not_absolute_index(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 5,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 2,
          "channel_layout": "stereo",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 0},
          "tags": {"language": "eng"}
        },
        {
          "index": 6,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 6,
          "channel_layout": "5.1",
          "sample_rate": "48000",
          "disposition": {"default": 0, "original": 0, "comment": 0},
          "tags": {"language": "jpn"}
        }
      ]
    }
    """

    probed = probe_streams(Path("ref.mkv"))
    selected, _ = select_audio_pair(
        probed,
        probed,
        reference_path=Path("ref.mkv"),
        comparison_path=Path("ref.mkv"),
        reference_override=1,
        comparison_override=None,
    )

    assert selected.stream.audio_stream_index == 1
    assert selected.stream.absolute_stream_index == 6


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_override_rejects_absolute_index(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 5,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 2,
          "channel_layout": "stereo",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 0},
          "tags": {"language": "eng"}
        }
      ]
    }
    """

    with pytest.raises(AudioAlignmentError, match="available audio stream ordinals: 0"):
        probed = probe_streams(Path("ref.mkv"))
        select_audio_pair(
            probed,
            probed,
            reference_path=Path("ref.mkv"),
            comparison_path=Path("ref.mkv"),
            reference_override=5,
            comparison_override=None,
        )


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_matches_reference_metadata_over_default_flag(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = [
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 1,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 0},
                  "tags": {"language": "eng"}
                }
              ]
            }
            """
        ),
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 7,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 0},
                  "tags": {"language": "jpn"}
                },
                {
                  "index": 8,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 0, "original": 0, "comment": 0},
                  "tags": {"language": "eng"}
                }
              ]
            }
            """
        ),
    ]

    reference_probe = probe_streams(Path("reference.mkv"))
    comparison_probe = probe_streams(Path("comparison.mkv"))
    reference_stream, selected = select_audio_pair(
        reference_probe,
        comparison_probe,
        reference_path=Path("reference.mkv"),
        comparison_path=Path("comparison.mkv"),
        reference_override=None,
        comparison_override=None,
    )

    assert reference_stream.stream.language == "eng"
    assert selected.stream.audio_stream_index == 1
    assert selected.stream.absolute_stream_index == 8


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_override_wins_over_metadata_match(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = [
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 1,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 0},
                  "tags": {"language": "eng"}
                }
              ]
            }
            """
        ),
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 7,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 0},
                  "tags": {"language": "eng"}
                },
                {
                  "index": 8,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 6,
                  "channel_layout": "5.1",
                  "sample_rate": "48000",
                  "disposition": {"default": 0, "original": 0, "comment": 1},
                  "tags": {"language": "jpn"}
                }
              ]
            }
            """
        ),
    ]

    reference_probe = probe_streams(Path("reference.mkv"))
    comparison_probe = probe_streams(Path("comparison.mkv"))
    _reference_stream, selected = select_audio_pair(
        reference_probe,
        comparison_probe,
        reference_path=Path("reference.mkv"),
        comparison_path=Path("comparison.mkv"),
        reference_override=None,
        comparison_override=1,
    )

    assert selected.stream.audio_stream_index == 1
    assert selected.stream.absolute_stream_index == 8


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_matches_commentary_reference(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = [
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 1,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 1},
                  "tags": {"language": "eng"}
                }
              ]
            }
            """
        ),
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 7,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 0},
                  "tags": {"language": "eng"}
                },
                {
                  "index": 8,
                  "codec_type": "audio",
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 0, "original": 0, "comment": 1},
                  "tags": {"language": "eng"}
                }
              ]
            }
            """
        ),
    ]

    reference_probe = probe_streams(Path("reference.mkv"))
    comparison_probe = probe_streams(Path("comparison.mkv"))
    reference_stream, selected = select_audio_pair(
        reference_probe,
        comparison_probe,
        reference_path=Path("reference.mkv"),
        comparison_path=Path("comparison.mkv"),
        reference_override=None,
        comparison_override=None,
    )

    assert reference_stream.stream.is_commentary
    assert selected.stream.is_commentary
    assert selected.stream.audio_stream_index == 1
    assert selected.stream.absolute_stream_index == 8


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_skips_non_audio_streams(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 0,
          "codec_type": "video",
          "codec_name": "h264",
          "start_time": "0.000000",
          "disposition": {"attached_pic": 0}
        },
        {
          "index": 1,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 2,
          "channel_layout": "stereo",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 0},
          "tags": {"language": "eng"}
        }
      ]
    }
    """

    probed = probe_streams(Path("ref.mkv"))
    selected, _ = select_audio_pair(
        probed,
        probed,
        reference_path=Path("ref.mkv"),
        comparison_path=Path("ref.mkv"),
        reference_override=None,
        comparison_override=None,
    )

    assert selected.stream.audio_stream_index == 0
    assert selected.stream.absolute_stream_index == 1
    assert selected.video_start.start_time == Fraction(0)
    assert selected.video_start.basis == "metadata"


@pytest.mark.parametrize(
    "stdout, filename, expected",
    [
        pytest.param(
            b'\n    {\n      "streams": [\n        {\n          "index": 0,\n          "codec_type": "video",\n          "codec_name": "h264",\n          "start_time": "0.041708",\n          "disposition": {"attached_pic": 0}\n        },\n        {\n          "index": 1,\n          "codec_type": "audio",\n          "codec_name": "aac",\n          "channels": 2,\n          "channel_layout": "stereo",\n          "sample_rate": "48000",\n          "start_time": "0.021333",\n          "disposition": {"default": 1, "original": 0, "comment": 0},\n          "tags": {"language": "eng"}\n        }\n      ],\n      "format": {"start_time": "0.000000"}\n    }\n    ',
            "ref.mkv",
            {
                "video_start": Fraction("0.041708"),
                "video_basis": "metadata",
                "audio_start": Fraction("0.021333"),
                "audio_basis": "metadata",
            },
            id="probe_reads_video_start_time_in_the_same_call",
        ),
        pytest.param(
            b'\n    {\n      "streams": [\n        {\n          "index": 0,\n          "codec_type": "video",\n          "codec_name": "mjpeg",\n          "start_time": "0.500000",\n          "disposition": {"attached_pic": 1}\n        },\n        {\n          "index": 1,\n          "codec_type": "video",\n          "codec_name": "h264",\n          "disposition": {"attached_pic": 0}\n        },\n        {\n          "index": 2,\n          "codec_type": "audio",\n          "codec_name": "aac",\n          "channels": 1,\n          "channel_layout": "mono",\n          "sample_rate": "48000",\n          "disposition": {"default": 0, "original": 0, "comment": 0},\n          "tags": {}\n        }\n      ]\n    }\n    ',
            "ref.mkv",
            {"video_start": Fraction(0), "video_basis": "default_zero"},
            id="probe_skips_attached_pic_and_defaults_missing_video_start",
        ),
        pytest.param(
            b'\n    {\n      "streams": [\n        {\n          "index": 0,\n          "codec_type": "audio",\n          "codec_name": "aac",\n          "channels": 2,\n          "channel_layout": "stereo",\n          "sample_rate": "48000",\n          "disposition": {"default": 0, "original": 0, "comment": 0},\n          "tags": {}\n        }\n      ]\n    }\n    ',
            "ref.mkv",
            {"video_start": Fraction(0), "video_basis": "default_zero"},
            id="probe_without_video_stream_defaults_video_start",
        ),
        pytest.param(
            b'{"streams":[{"index":1,"codec_type":"audio","time_base":"1/48000","duration_ts":1440000,"duration":"30.0"}],"format":{"duration":"600.0"}}',
            "short-audio.mkv",
            {"duration": Fraction(30), "duration_basis": "duration_ts"},
            id="stream_probe_prefers_selected_stream_duration_over_container",
        ),
        pytest.param(
            b'{"streams":[{"index":1,"codec_type":"audio","time_base":"1/48000"}],"format":{"duration":"7200.0"}}',
            "unknown-audio.mkv",
            {"duration": None, "duration_basis": "unavailable"},
            id="stream_probe_does_not_substitute_long_container_duration",
        ),
        pytest.param(
            b'{"streams":[{"index":1,"codec_type":"audio","start_time":"-1.25","time_base":"1/48000","duration_ts":192000}]}',
            "negative-start.mkv",
            {"audio_start": Fraction(-5, 4), "duration": Fraction(4)},
            id="stream_probe_preserves_negative_selected_stream_start",
        ),
        pytest.param(
            b'{"streams":[{"index":1,"codec_type":"audio","start_time":"Infinity","duration":"Infinity","time_base":"1/48000"}]}',
            "invalid-time.mkv",
            {"audio_start": Fraction(0), "duration": None},
            id="stream_probe_ignores_non_finite_timing_metadata",
        ),
    ],
)
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_stream_timing(
    mock_run: MagicMock, stdout: bytes, filename: str, expected: dict[str, Fraction | str | None]
) -> None:
    mock_run.return_value.stdout = stdout
    probed = probe_streams(Path(filename))
    timeline = probed.audio[0].timeline
    actual = {
        "video_start": probed.video_start.start_time,
        "video_basis": probed.video_start.basis,
        "audio_start": timeline.start_time,
        "audio_basis": timeline.start_time_basis,
        "duration": timeline.duration,
        "duration_basis": timeline.duration_basis,
    }
    assert {key: actual[key] for key in expected} == expected


@pytest.mark.parametrize(
    ("tag", "start", "encoder", "statistics", "duration"),
    [
        pytest.param(
            "00:05:00.000000000", "90", None, True, 300, id="mkvmerge-duration-is-elapsed"
        ),
        pytest.param("00:06:30.000000000", "90", "Lavf", False, 300, id="ffmpeg-tag-is-endpoint"),
        pytest.param(
            "00:06:30.000000000", "90", "Lavf61.7.100", True, 300, id="ffmpeg-keeps-stats-markers"
        ),
        pytest.param(
            "00:05:00.000000000", "90", "Lavf-compatible", False, None, id="unrecognized-muxer"
        ),
        pytest.param(
            "00:05:00.000000000", "90", None, False, None, id="ambiguous-tag-needs-packets"
        ),
        pytest.param("00:00:1e309", "0", None, False, None, id="exponent"),
        pytest.param("00:60:01", "0", None, False, None, id="minutes-out-of-range"),
        pytest.param("00:01:60.1", "0", None, False, None, id="seconds-out-of-range"),
        pytest.param("01:-1:01", "0", None, False, None, id="signed-minutes"),
        pytest.param("01:02:-1", "0", None, False, None, id="signed-seconds"),
        pytest.param("1234567890123:02:01", "0", None, False, None, id="overlong-hours"),
    ],
)
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_duration_tag_clock_and_provenance(
    mock_run: MagicMock,
    tag: str,
    start: str,
    encoder: str | None,
    statistics: bool,
    duration: int | None,
) -> None:
    tags = {"DURATION": tag}
    if statistics:
        tags.update(
            _STATISTICS_WRITING_APP="mkvmerge v90.0",
            _STATISTICS_TAGS="BPS DURATION NUMBER_OF_FRAMES NUMBER_OF_BYTES",
        )
    mock_run.return_value.stdout = json.dumps(
        {
            "streams": [{"index": 1, "codec_type": "audio", "start_time": start, "tags": tags}],
            "format": {
                "format_name": "matroska,webm",
                "tags": {"encoder": encoder} if encoder else {},
            },
        }
    ).encode()
    timeline = probe_streams(Path("tagged.mkv")).audio[0].timeline
    assert timeline.duration == duration
    assert timeline.duration_basis == ("stream_tag" if duration is not None else "unavailable")


def test_probe_with_no_audio_streams_is_alignment_error() -> None:
    with patch("frame_compare.services.alignment_audio.run_subprocess") as mock_run:
        mock_run.return_value.stdout = b'{"streams": [{}]}'
        with pytest.raises(AudioAlignmentError, match="no audio streams found"):
            probe_streams(Path("ref.mkv"))


def test_collection_argv_is_whole_track_mono_8khz() -> None:
    downmix = collection_argv(
        Path("comparison.mkv"),
        _test_stream(),
        channel_strategy="mono_downmix",
        timeline_scale=Fraction(1),
    )
    assert downmix[:3] == ["ffmpeg", "-i", "comparison.mkv"]
    assert downmix[3:6] == ["-map", "0:a:2", "-vn"]
    assert "-ac" in downmix and "1" in downmix
    assert "aresample=8000" in downmix[downmix.index("-af") + 1]
    assert downmix[-3:] == ["-f", "f32le", "-"]
    assert "atrim" not in " ".join(downmix)

    best = collection_argv(
        Path("comparison.mkv"),
        _test_stream(),
        channel_strategy="best_channel",
        timeline_scale=Fraction(1),
    )
    assert "-ac" not in best
    assert "pan=mono" in best[best.index("-af") + 1]
    assert "aresample=8000" in best[best.index("-af") + 1]


@pytest.mark.parametrize(
    ("scale", "expected"),
    [
        (Fraction(1), None),
        (Fraction(1001, 1000), (8008, 8000)),
        (Fraction(25, 24), (8350, 8016)),
        (Fraction(25025, 24000), (9009, 8640)),
        (Fraction(1001, 1200), (8008, 9600)),
        (Fraction(400001, 400000), "unsupported"),
    ],
)
def test_retime_rates_are_exact(scale: Fraction, expected: tuple[int, int] | None | str) -> None:
    if expected == "unsupported":
        with pytest.raises(AudioAlignmentError) as exc_info:
            retime_rates(scale)
        assert exc_info.value.category == "retime_rate_unsupported"
        return
    assert retime_rates(scale) == expected


def test_collection_argv_retime_filters_stretch_audio_time() -> None:
    argv = collection_argv(
        Path("comparison.mkv"),
        _test_stream(),
        channel_strategy="mono_downmix",
        timeline_scale=Fraction(1001, 1000),
    )
    assert argv[argv.index("-af") + 1].endswith("aresample=8008,asetrate=8000,aresample=8000")


def _test_stream() -> AudioStreamInfo:
    return AudioStreamInfo(
        audio_stream_index=2,
        absolute_stream_index=3,
        codec_name="aac",
        channels=2,
        channel_layout="stereo",
        sample_rate=48000,
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        timeline=AudioStreamTimeline(
            start_time=Fraction(0),
            duration=Fraction(20),
            time_base=Fraction(1, 48000),
            duration_basis="stream_duration",
        ),
    )


@pytest.mark.parametrize(
    (
        "reference",
        "comparison",
        "reference_override",
        "comparison_override",
        "expected",
    ),
    [
        pytest.param(
            (("jpn", True, False), ("eng", False, False)),
            (("eng", False, False),),
            None,
            None,
            ("eng", "eng"),
            id="shared-language-wins",
        ),
        pytest.param(
            (("jpn", True, False), ("eng", False, False)),
            (("jpn", False, False), ("eng", False, False)),
            None,
            None,
            ("jpn", "jpn"),
            id="default-language-is-shared",
        ),
        pytest.param(
            ((None, True, False), ("eng", False, False)),
            (("eng", False, False),),
            None,
            None,
            (None, "eng"),
            id="unknown-default-language-keeps-default",
        ),
        pytest.param(
            (("und", True, False), ("eng", False, False)),
            (("eng", False, False),),
            None,
            None,
            (None, "eng"),
            id="ffprobe-und-default-keeps-ordinal-zero",
        ),
        pytest.param(
            (("und", True, False),),
            (("und", False, False),),
            None,
            None,
            (None, None),
            id="two-und-tags-are-unknown",
        ),
        pytest.param(
            (("/private/generated/cut.mkv", True, False),),
            (("ZH-hant-TW", False, False),),
            None,
            None,
            (None, "zh-hant-tw"),
            id="path-like-language-is-unknown",
        ),
        pytest.param(
            (("en" + "-abcdefgh" * 7, True, False),),
            (("en", False, False),),
            None,
            None,
            (None, "en"),
            id="overlong-language-is-unknown",
        ),
        pytest.param(
            (("jpn", True, False),),
            (("eng", False, False),),
            None,
            None,
            ("jpn", "eng"),
            id="no-shared-language-keeps-default",
        ),
        pytest.param(
            (("jpn", True, False), ("eng", False, False)),
            (("eng", False, False),),
            0,
            None,
            ("jpn", "eng"),
            id="reference-override-disables-exception",
        ),
        pytest.param(
            (("jpn", True, False), ("eng", False, False)),
            (("jpn", False, False), ("eng", False, False)),
            None,
            1,
            ("eng", "eng"),
            id="comparison-override-narrows-shared-set",
        ),
        pytest.param(
            (("jpn", True, False), ("eng", False, True)),
            (("eng", False, False),),
            None,
            None,
            ("jpn", "eng"),
            id="commentary-is-not-shared",
        ),
    ],
)
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_audio_pair_prefers_a_shared_language(
    mock_run: MagicMock,
    reference: tuple[tuple[str | None, bool, bool], ...],
    comparison: tuple[tuple[str | None, bool, bool], ...],
    reference_override: int | None,
    comparison_override: int | None,
    expected: tuple[str | None, str | None],
) -> None:
    reference_path = Path("reference.mkv")
    comparison_path = Path("comparison.mkv")

    def probe(path: Path, tracks: tuple[tuple[str | None, bool, bool], ...]):
        mock_run.return_value.stdout = json.dumps(
            {
                "streams": [
                    {
                        "index": index + 1,
                        "codec_type": "audio",
                        "disposition": {"default": int(default), "comment": int(commentary)},
                        "tags": {"language": language} if language is not None else {},
                    }
                    for index, (language, default, commentary) in enumerate(tracks)
                ]
            }
        ).encode()
        return probe_streams(path)

    reference_selection, comparison_selection = select_audio_pair(
        probe(reference_path, reference),
        probe(comparison_path, comparison),
        reference_path=reference_path,
        comparison_path=comparison_path,
        reference_override=reference_override,
        comparison_override=comparison_override,
    )

    assert reference_selection.stream.language == expected[0]
    assert comparison_selection.stream.language == expected[1]


@pytest.mark.parametrize(
    "chunks, reached_seek, latest_end",
    [
        ([b"30000,1000\n89900,100\n"], True, Fraction(90)),
        ([b"300", b"00,100", b"0\n89900,100"], True, Fraction(90)),
        ([b"29999,1000\n"], False, Fraction(30999, 1000)),
        ([b"90000,0\r\n30000,100\r\n"], True, Fraction(90)),
        ([b"30000,1000,\n89900,100", b",\n"], True, Fraction(90)),
        ([], False, None),
    ],
)
def test_selected_audio_packet_tail_parser(
    chunks: list[bytes], reached_seek: bool, latest_end: Fraction | None
) -> None:
    parser = _PacketTailParser(Fraction(1, 1000), Fraction(30))
    for chunk in chunks:
        parser.feed(chunk)
    parser.finish()
    assert parser.reached_seek == reached_seek
    assert parser.latest_end == latest_end


@pytest.mark.parametrize(
    "row",
    [
        b"\n",
        b"30000\n",
        b"N/A,100\n",
        b"true,100\n",
        b"30000,-1\n",
        b"1_000,10\n",
        b"30000,,\n",
        b"N/A,100,\n",
        b"30000,N/A,\n",
    ],
)
def test_selected_audio_packet_tail_parser_rejects_malformed_rows(row: bytes) -> None:
    parser = _PacketTailParser(Fraction(1, 1000), Fraction(30))
    with pytest.raises(ValueError):
        parser.feed(row)
        parser.finish()


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_selected_audio_tail_timeout_stays_unavailable(mock_run: MagicMock) -> None:
    stream = replace(
        _test_stream(),
        timeline=AudioStreamTimeline(
            start_time=Fraction(0),
            duration=None,
            time_base=Fraction(1, 1000),
            duration_basis="unavailable",
        ),
    )
    mock_run.side_effect = TimeoutExpired("ffprobe", 15)
    assert (
        measure_selected_audio_duration(
            Path("movie.mkv"),
            stream,
            video_seconds=Fraction(90),
            video_start=Fraction(0),
            cancellation=None,
        )
        == stream
    )
    cancellation = Event()
    cancellation.set()
    mock_run.reset_mock()
    with pytest.raises(AudioAlignmentCancellationError):
        measure_selected_audio_duration(
            Path("movie.mkv"),
            stream,
            video_seconds=Fraction(90),
            video_start=Fraction(0),
            cancellation=cancellation,
        )
    mock_run.assert_not_called()


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_selected_audio_tail_skips_known_duration_and_missing_time_base(
    mock_run: MagicMock,
) -> None:
    known = _test_stream()
    assert (
        measure_selected_audio_duration(
            Path("movie.mkv"),
            known,
            video_seconds=Fraction(90),
            video_start=Fraction(0),
            cancellation=None,
        )
        == known
    )
    unknown = replace(
        known,
        timeline=replace(
            known.timeline, duration=None, time_base=None, duration_basis="unavailable"
        ),
    )
    assert (
        measure_selected_audio_duration(
            Path("movie.mkv"),
            unknown,
            video_seconds=Fraction(90),
            video_start=Fraction(0),
            cancellation=None,
        )
        == unknown
    )
    mock_run.assert_not_called()
