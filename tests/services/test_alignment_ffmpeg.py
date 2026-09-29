"""FFmpeg and ffprobe audio alignment tests."""

# pyright: reportPrivateUsage=false

from fractions import Fraction
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.services.alignment_audio import (
    AudioStreamInfo,
    AudioStreamTimeline,
    ProbedStreams,
    VideoStreamStart,
    collection_argv,
    probe_streams,
    retime_rates,
    select_audio_pair,
)
from frame_compare.services.alignment_audio import (
    probe_fps as _probe_fps,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_fraction(mock_run: MagicMock):
    """Test probing FPS when it returns a fraction."""
    mock_run.return_value.stdout = b"24000/1001\n"
    res = _probe_fps(Path("test.mkv"))
    assert res == Fraction(24000, 1001)
    mock_run.assert_called_once_with(
        [
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
        ],
        timeout_seconds=15.0,
    )


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_accepts_single_trailing_comma(mock_run: MagicMock) -> None:
    mock_run.return_value.stdout = b"24000/1001,\r\n"

    res = _probe_fps(Path("test.mkv"))

    assert res == Fraction(24000, 1001)


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_integer(mock_run: MagicMock):
    """Test probing FPS when it returns an integer."""
    mock_run.return_value.stdout = b"24\n"
    res = _probe_fps(Path("test.mkv"))
    assert res == Fraction(24, 1)


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


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_not_found_raises(mock_run: MagicMock):
    """Test probing FPS when ffprobe is missing."""
    mock_run.side_effect = FileNotFoundError()
    with pytest.raises(FFmpegNotFoundError):
        _probe_fps(Path("test.mkv"))


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_nonzero_exit_raises(mock_run: MagicMock):
    """Test probing FPS when ffprobe fails."""
    mock_run.side_effect = CalledProcessError(1, ["ffprobe"], stderr=b"error")
    with pytest.raises(FFmpegError):
        _probe_fps(Path("test.mkv"))


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_oserror_raises_ffmpeg_error(mock_run: MagicMock) -> None:
    mock_run.side_effect = OSError("permission denied")

    with pytest.raises(FFmpegError) as exc_info:
        _probe_fps(Path("test.mkv"))

    assert "traceback" not in str(exc_info.value).lower()
    assert exc_info.value.context.details is not None
    message = str(exc_info.value.context.details).lower()
    assert "ffprobe" in message
    assert "could not start" in message
    assert "permission denied" in message


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_non_utf8_stderr_is_replaced(mock_run: MagicMock) -> None:
    mock_run.side_effect = CalledProcessError(1, ["ffprobe"], stderr=b"\xfferror")

    with pytest.raises(FFmpegError) as exc_info:
        _probe_fps(Path("test.mkv"))

    assert "\ufffderror" in str(exc_info.value.context.details)


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_fps_timeout_raises(mock_run: MagicMock):
    """Test probing FPS timeout surfaces as FFmpegError."""
    mock_run.side_effect = TimeoutExpired(cmd=["ffprobe"], timeout=15.0)
    with pytest.raises(FFmpegError) as exc_info:
        _probe_fps(Path("test.mkv"))
    assert exc_info.value.context.details is not None
    assert exc_info.value.context.details.get("returncode") == 124
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


@pytest.mark.parametrize("stdout", [b"[]", b"null", b'"oops"'])
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_streams_rejects_non_object_ffprobe_json(
    mock_run: MagicMock,
    stdout: bytes,
) -> None:
    mock_run.return_value = MagicMock(stdout=stdout, returncode=0)

    with pytest.raises(FFmpegError) as exc_info:
        probe_streams(Path("reference.mkv"))

    assert exc_info.value.context.details is not None
    message = str(exc_info.value.context.details).lower()
    assert "ffprobe" in message
    assert "invalid json" in message
    assert "object" in message


@pytest.mark.parametrize(
    "stdout, expected",
    [
        (b'{"streams": {}}', "stream list"),
        (b'{"streams": [null]}', "stream data"),
    ],
)
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_streams_rejects_malformed_object_ffprobe_json(
    mock_run: MagicMock,
    stdout: bytes,
    expected: str,
) -> None:
    mock_run.return_value = MagicMock(stdout=stdout, returncode=0)

    with pytest.raises(FFmpegError) as exc_info:
        probe_streams(Path("reference.mkv"))

    assert exc_info.value.context.details is not None
    message = str(exc_info.value.context.details).lower()
    assert "ffprobe" in message
    assert expected in message


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


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_reads_video_start_time_in_the_same_call(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 0,
          "codec_type": "video",
          "codec_name": "h264",
          "start_time": "0.041708",
          "disposition": {"attached_pic": 0}
        },
        {
          "index": 1,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 2,
          "channel_layout": "stereo",
          "sample_rate": "48000",
          "start_time": "0.021333",
          "disposition": {"default": 1, "original": 0, "comment": 0},
          "tags": {"language": "eng"}
        }
      ],
      "format": {"start_time": "0.000000"}
    }
    """

    probed = probe_streams(Path("ref.mkv"))

    assert mock_run.call_count == 1
    argv = mock_run.call_args[0][0]
    assert "-select_streams" not in argv
    assert probed.video_start.start_time == Fraction("0.041708")
    assert probed.video_start.basis == "metadata"
    assert probed.audio[0].timeline.start_time == Fraction("0.021333")
    assert probed.audio[0].timeline.start_time_basis == "metadata"


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_skips_attached_pic_and_defaults_missing_video_start(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 0,
          "codec_type": "video",
          "codec_name": "mjpeg",
          "start_time": "0.500000",
          "disposition": {"attached_pic": 1}
        },
        {
          "index": 1,
          "codec_type": "video",
          "codec_name": "h264",
          "disposition": {"attached_pic": 0}
        },
        {
          "index": 2,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 1,
          "channel_layout": "mono",
          "sample_rate": "48000",
          "disposition": {"default": 0, "original": 0, "comment": 0},
          "tags": {}
        }
      ]
    }
    """

    probed = probe_streams(Path("ref.mkv"))

    assert probed.video_start.start_time == Fraction(0)
    assert probed.video_start.basis == "default_zero"


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_probe_without_video_stream_defaults_video_start(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 0,
          "codec_type": "audio",
          "codec_name": "aac",
          "channels": 2,
          "channel_layout": "stereo",
          "sample_rate": "48000",
          "disposition": {"default": 0, "original": 0, "comment": 0},
          "tags": {}
        }
      ]
    }
    """

    probed = probe_streams(Path("ref.mkv"))

    assert probed.video_start.start_time == Fraction(0)
    assert probed.video_start.basis == "default_zero"


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
        assert exc_info.value.category == "selected_audio_timeline_unavailable"
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


def test_stream_probe_prefers_selected_stream_duration_over_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ported U3-R M6: the stream duration basis wins over the container duration."""
    from frame_compare.services import alignment_audio

    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"codec_type":"audio","time_base":"1/48000",'
        b'"duration_ts":1440000,"duration":"30.0"}],"format":{"duration":"600.0"}}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    probed = probe_streams(Path("short-audio.mkv"))

    assert probed.audio[0].timeline.duration == 30
    assert probed.audio[0].timeline.duration_basis == "duration_ts"


def test_stream_probe_does_not_substitute_long_container_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ported U3-R M6: a long container duration never fills an unknown stream duration."""
    from frame_compare.services import alignment_audio

    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"codec_type":"audio","time_base":"1/48000"}],'
        b'"format":{"duration":"7200.0"}}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    probed = probe_streams(Path("unknown-audio.mkv"))

    assert probed.audio[0].timeline.duration is None
    assert probed.audio[0].timeline.duration_basis == "unavailable"


def test_stream_probe_preserves_negative_selected_stream_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ported U3-R M6: a negative audio start time is preserved, not clamped."""
    from frame_compare.services import alignment_audio

    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"codec_type":"audio","start_time":"-1.25",'
        b'"time_base":"1/48000","duration_ts":192000}]}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    probed = probe_streams(Path("negative-start.mkv"))

    assert probed.audio[0].timeline.start_time == Fraction(-5, 4)
    assert probed.audio[0].timeline.duration == 4


def test_stream_probe_ignores_non_finite_timing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ported U3-R M6: non-finite start/duration fall back to zero/unknown."""
    from frame_compare.services import alignment_audio

    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"codec_type":"audio","start_time":"Infinity",'
        b'"duration":"Infinity","time_base":"1/48000"}]}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    probed = probe_streams(Path("invalid-time.mkv"))

    assert probed.audio[0].timeline.start_time == 0
    assert probed.audio[0].timeline.duration is None


def _pair_stream(
    index: int,
    language: str | None,
    *,
    default: bool = False,
    commentary: bool = False,
) -> AudioStreamInfo:
    return AudioStreamInfo(
        audio_stream_index=index,
        absolute_stream_index=index + 1,
        codec_name="aac",
        channels=2,
        channel_layout="stereo",
        sample_rate=48000,
        language=language,
        is_default=default,
        is_original=False,
        is_commentary=commentary,
    )


def _pair_probe(*languages: tuple[str | None, bool, bool]) -> ProbedStreams:
    return ProbedStreams(
        audio=tuple(
            _pair_stream(index, language, default=default, commentary=commentary)
            for index, (language, default, commentary) in enumerate(languages)
        ),
        video_start=VideoStreamStart(start_time=Fraction(0), basis="default_zero"),
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
def test_select_audio_pair_prefers_a_shared_language(
    reference: tuple[tuple[str | None, bool, bool], ...],
    comparison: tuple[tuple[str | None, bool, bool], ...],
    reference_override: int | None,
    comparison_override: int | None,
    expected: tuple[str | None, str | None],
) -> None:
    reference_selection, comparison_selection = select_audio_pair(
        _pair_probe(*reference),
        _pair_probe(*comparison),
        reference_path=Path("reference.mkv"),
        comparison_path=Path("comparison.mkv"),
        reference_override=reference_override,
        comparison_override=comparison_override,
    )

    assert reference_selection.stream.language == expected[0]
    assert comparison_selection.stream.language == expected[1]
