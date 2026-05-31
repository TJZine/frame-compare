"""FFmpeg and ffprobe audio alignment tests."""

# pyright: reportPrivateUsage=false

from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.services.alignment_audio import (
    extract_audio as _extract_audio,
)
from frame_compare.services.alignment_audio import (
    extract_matching_audio as _extract_matching_audio,
)
from frame_compare.services.alignment_audio import (
    extract_reference_audio as _extract_reference_audio,
)
from frame_compare.services.alignment_audio import (
    probe_fps as _probe_fps,
)
from frame_compare.services.alignment_audio import (
    select_matching_audio_stream,
    select_reference_audio_stream,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
from frame_compare.utils.subproc import CalledProcessError, TimeoutExpired


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
def test_probe_fps_non_utf8_stderr_is_replaced(mock_run: MagicMock) -> None:
    mock_run.side_effect = CalledProcessError(1, ["ffprobe"], stderr=b"\xfferror")

    with pytest.raises(FFmpegError) as exc_info:
        _probe_fps(Path("test.mkv"))

    assert "\ufffderror" in str(exc_info.value.context.details)


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_audio_ffmpeg_not_found(mock_run: MagicMock):
    """Test audio extraction when ffmpeg is missing."""
    mock_run.side_effect = FileNotFoundError()
    with pytest.raises(FFmpegNotFoundError):
        _extract_audio(Path("test.mkv"), 8000, audio_stream_index=0)


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
def test_extract_audio_ffmpeg_fails(mock_run: MagicMock):
    """Test audio extraction when ffmpeg fails."""
    mock_run.side_effect = CalledProcessError(1, ["ffmpeg"], stderr=b"error")
    with pytest.raises(FFmpegError):
        _extract_audio(Path("test.mkv"), 8000, audio_stream_index=0)


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_audio_non_utf8_stderr_is_replaced(mock_run: MagicMock) -> None:
    mock_run.side_effect = CalledProcessError(1, ["ffmpeg"], stderr=b"\xfferror")

    with pytest.raises(FFmpegError) as exc_info:
        _extract_audio(Path("test.mkv"), 8000, audio_stream_index=0)

    assert "\ufffderror" in str(exc_info.value.context.details)


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_audio_timeout_raises(mock_run: MagicMock):
    """Test audio extraction timeout surfaces as FFmpegError."""
    mock_run.side_effect = TimeoutExpired(cmd=["ffmpeg"], timeout=120.0)
    with pytest.raises(FFmpegError) as exc_info:
        _extract_audio(Path("test.mkv"), 8000, audio_stream_index=0)
    assert exc_info.value.context.details is not None
    assert exc_info.value.context.details.get("returncode") == 124
    assert "timed out" in str(exc_info.value.context.details.get("stderr", ""))


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_audio_oserror_raises_ffmpeg_error(mock_run: MagicMock) -> None:
    mock_run.side_effect = OSError("permission denied")

    with pytest.raises(FFmpegError) as exc_info:
        _extract_audio(Path("test.mkv"), 8000, audio_stream_index=0)

    assert "could not start" in str(exc_info.value.context.details)
    assert "permission denied" in str(exc_info.value.context.details)
    assert exc_info.value.context.details is not None
    assert exc_info.value.context.details.get("returncode") == 1


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_audio_unexpected_exceptions_propagate(mock_run: MagicMock) -> None:
    mock_run.side_effect = RuntimeError("unexpected bug")

    with pytest.raises(RuntimeError, match="unexpected bug"):
        _extract_audio(Path("test.mkv"), 8000, audio_stream_index=0)


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_audio_empty_raises(mock_run: MagicMock):
    """Test audio extraction when output is empty."""
    mock_run.return_value.stdout = b""
    with pytest.raises(AudioAlignmentError, match="empty audio"):
        _extract_audio(Path("test.mkv"), 8000, audio_stream_index=1)
    mock_run.assert_called_once_with(
        [
            "ffmpeg",
            "-i",
            "test.mkv",
            "-map",
            "0:a:1",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "f32le",
            "-",
        ],
        timeout_seconds=120.0,
    )


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_audio_invalid_float32_payload_raises(mock_run: MagicMock) -> None:
    mock_run.return_value.stdout = b"abc"

    with pytest.raises(AudioAlignmentError, match="test.mkv.*3 bytes"):
        _extract_audio(Path("test.mkv"), 8000, audio_stream_index=0)


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_reference_audio_stream_prefers_non_commentary_default_then_channels(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 1,
          "codec_name": "aac",
          "channels": 6,
          "channel_layout": "5.1",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 1},
          "tags": {"language": "eng"}
        },
        {
          "index": 2,
          "codec_name": "aac",
          "channels": 2,
          "channel_layout": "stereo",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 0},
          "tags": {"language": "eng"}
        },
        {
          "index": 3,
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

    selected = select_reference_audio_stream(Path("ref.mkv"))

    assert selected.audio_stream_index == 2
    assert selected.absolute_stream_index == 3


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_reference_audio_stream_treats_text_commentary_tag_as_commentary(
    mock_run: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 1,
          "codec_name": "aac",
          "channels": 6,
          "channel_layout": "5.1",
          "sample_rate": "48000",
          "disposition": {"default": 1, "original": 0, "comment": 0},
          "tags": {"language": "eng", "comment": "Director commentary"}
        },
        {
          "index": 2,
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

    selected = select_reference_audio_stream(Path("ref.mkv"))

    assert selected.audio_stream_index == 1
    assert selected.absolute_stream_index == 2


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_matching_audio_stream_matches_reference_metadata_over_default_flag(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = [
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 1,
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
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 0},
                  "tags": {"language": "jpn"}
                },
                {
                  "index": 8,
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

    reference_stream = select_reference_audio_stream(Path("reference.mkv"))
    selected = select_matching_audio_stream(
        Path("comparison.mkv"),
        reference_stream=reference_stream,
    )

    assert reference_stream.language == "eng"
    assert selected.audio_stream_index == 1
    assert selected.absolute_stream_index == 8


@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_select_matching_audio_stream_matches_commentary_reference(
    mock_run: MagicMock,
) -> None:
    mock_run.side_effect = [
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 1,
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
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 0},
                  "tags": {"language": "eng"}
                },
                {
                  "index": 8,
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

    reference_stream = select_reference_audio_stream(Path("reference.mkv"))
    selected = select_matching_audio_stream(
        Path("comparison.mkv"),
        reference_stream=reference_stream,
    )

    assert reference_stream.is_commentary
    assert selected.is_commentary
    assert selected.audio_stream_index == 1
    assert selected.absolute_stream_index == 8


@patch("frame_compare.services.alignment_audio.extract_audio")
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_reference_audio_returns_selected_stream(
    mock_run: MagicMock,
    mock_extract_audio: MagicMock,
) -> None:
    mock_run.return_value.stdout = b"""
    {
      "streams": [
        {
          "index": 5,
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
    mock_extract_audio.return_value = "audio"

    audio, stream = _extract_reference_audio(Path("ref.mkv"), 8000)

    assert audio == "audio"
    assert stream.audio_stream_index == 0
    mock_extract_audio.assert_called_once_with(
        Path("ref.mkv"),
        8000,
        audio_stream_index=0,
    )


@patch("frame_compare.services.alignment_audio.extract_audio")
@patch("frame_compare.services.alignment_audio.run_subprocess")
def test_extract_matching_audio_uses_reference_matched_stream(
    mock_run: MagicMock,
    mock_extract_audio: MagicMock,
) -> None:
    mock_run.side_effect = [
        MagicMock(
            stdout=b"""
            {
              "streams": [
                {
                  "index": 1,
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
                  "index": 5,
                  "codec_name": "aac",
                  "channels": 2,
                  "channel_layout": "stereo",
                  "sample_rate": "48000",
                  "disposition": {"default": 1, "original": 0, "comment": 0},
                  "tags": {"language": "jpn"}
                },
                {
                  "index": 6,
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
    mock_extract_audio.return_value = "audio"
    reference_stream = select_reference_audio_stream(Path("reference.mkv"))

    audio = _extract_matching_audio(
        Path("comparison.mkv"),
        8000,
        reference_stream=reference_stream,
    )

    assert audio == "audio"
    mock_extract_audio.assert_called_once_with(
        Path("comparison.mkv"),
        8000,
        audio_stream_index=1,
    )
