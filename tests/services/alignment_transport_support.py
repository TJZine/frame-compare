"""PCM transport fixtures for the whole-track alignment workflow."""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from frame_compare.services import alignment_audio
from frame_compare.services.alignment_audio import (
    AudioStreamInfo,
    AudioStreamSelection,
    AudioStreamTimeline,
    ProbedStreams,
    VideoStreamStart,
)

DURATION_SECONDS = 35.0


def _payload(values: np.ndarray) -> bytes:
    return np.ascontiguousarray(values, dtype="<f4").tobytes()


def _writer_argv(pcm_path: Path) -> list[str]:
    return [
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(open(sys.argv[1], 'rb').read())",
        str(pcm_path),
    ]


def audio_selection(*, duration_seconds: float = DURATION_SECONDS) -> AudioStreamSelection:
    return AudioStreamSelection(
        stream=AudioStreamInfo(
            audio_stream_index=0,
            absolute_stream_index=1,
            codec_name="pcm",
            channels=1,
            channel_layout="mono",
            sample_rate=8000,
            language=None,
            is_default=True,
            is_original=False,
            is_commentary=False,
            timeline=AudioStreamTimeline(
                start_time=Fraction(0),
                duration=Fraction(duration_seconds),
                time_base=Fraction(1, 8000),
                duration_basis="stream_duration",
            ),
        ),
        video_start=VideoStreamStart(start_time=Fraction(0), basis="default_zero"),
    )


def probed_streams(*, duration_seconds: float = DURATION_SECONDS) -> ProbedStreams:
    selection = audio_selection(duration_seconds=duration_seconds)
    return ProbedStreams(audio=(selection.stream,), video_start=selection.video_start)


def stub_pcm_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    reference_samples: np.ndarray,
    comparison_samples: np.ndarray,
) -> None:
    reference_pcm = tmp_path / "reference.f32"
    comparison_pcm = tmp_path / "comparison.f32"
    reference_pcm.write_bytes(_payload(reference_samples))
    comparison_pcm.write_bytes(_payload(comparison_samples))
    monkeypatch.setattr(
        alignment_audio,
        "probe_streams",
        lambda *args, **kwargs: probed_streams(),
    )

    def argv(
        path: Path, stream: object, *, channel_strategy: str, timeline_scale: Fraction
    ) -> list[str]:
        pcm = reference_pcm if Path(path).stem == "reference" else comparison_pcm
        return _writer_argv(pcm)

    monkeypatch.setattr(alignment_audio, "collection_argv", argv)


def write_media_pair(tmp_path: Path) -> tuple[Path, Path]:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.write_bytes(b"reference")
    comparison.write_bytes(b"comparison")
    return reference, comparison
