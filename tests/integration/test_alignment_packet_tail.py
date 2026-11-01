"""Real live-Matroska duration fallback and unchanged alignment authority."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from threading import Event
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from frame_compare.services import alignment_audio
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_audio import measure_selected_audio_duration, probe_streams
from frame_compare.services.errors import AudioAlignmentCancellationError
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils import subproc
from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    audio_attempt_payload,
    evidence_from_payload,
)
from frame_compare.utils.alignment_review_projection import audio_evidence_rows
from frame_compare.vs.env import detect_plugins, ensure_vs_environment
from frame_compare.vs.loader import DefaultVSLoader
from tests.integration.alignment_u4_media_store import open_u4_media
from tests.services.alignment_request_test_support import alignment_request

if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
    pytest.skip("ffmpeg/ffprobe not available", allow_module_level=True)


@pytest.mark.parametrize("early_end", [False, True], ids=["known-offset", "audio-before-tail"])
def test_live_matroska_packet_tail(tmp_path: Path, early_end: bool) -> None:
    vs_mod = pytest.importorskip("vapoursynth")
    if isinstance(vs_mod, MagicMock):
        pytest.skip("vapoursynth is mocked")
    if not detect_plugins(ensure_vs_environment()).get("lsmas", False):
        pytest.skip("lsmas plugin not available")
    with open_u4_media(tmp_path / "media", cache_root=None, full_matrix=False) as media:
        reference, comparison = media.pair("packet-tail-early-end" if early_end else "packet-tail")
        for path in (reference, comparison):
            assert probe_streams(path).audio[0].timeline.duration is None
        request = alignment_request(
            reference=reference, comparisons=[comparison], generated_dir=tmp_path / "generated"
        )
        request = replace(
            request,
            reference=replace(request.reference, source_frame_count=90 * 24),
            comparisons=[
                replace(request.comparisons[0], source_frame_count=(90 if early_end else 88) * 24)
            ],
        )
        (result,) = asyncio.run(
            align_clips_from_request(
                request, AlignmentConfig(cache_results=False), vs_loader=DefaultVSLoader()
            )
        ).results
        attempt = result.audio_attempt
        assert attempt is not None
        assert (
            evidence_from_payload(AudioAlignmentAttempt, audio_attempt_payload(attempt)) == attempt
        )
        if early_end:
            assert result.applied is False
            assert result.frame_offset is None
            assert result.diagnostic == "selected_audio_timeline_unavailable"
            assert attempt.status == "preanalysis_rejection"
            assert attempt.collection_observation == "not_observed"
            assert attempt.decision.candidate is None
            assert attempt.selected_streams[1].duration_basis == "unavailable"
        else:
            assert attempt.collection_observation == "observed"
            assert all(
                stream.duration_basis == "packet_tail" for stream in attempt.selected_streams
            )
            assert attempt.decision.candidate is not None
            assert attempt.decision.candidate.frame_offset == 48
            assert result.applied is True
            assert result.frame_offset == 48
            assert attempt.decision.primary_reason == "audio_video_confirmed"
            rows = audio_evidence_rows(attempt)
            assert all(
                "(packet_tail)" in row.value for row in rows if row.key.startswith("Stream ")
            )


@pytest.fixture
def packet_tail_media(tmp_path: Path, audio_codec: str) -> Path:
    path = tmp_path / "live.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=white:s=32x24:r=24:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v",
            "ffv1",
            "-c:a",
            audio_codec,
            "-live",
            "1",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    return path


@pytest.mark.parametrize("audio_codec", ["pcm_s16le", "libopus"])
@pytest.mark.parametrize(
    "stop", ["cap", "cancel", "timeout", "complete", "before-seek", "nonpositive"]
)
def test_packet_tail_probe_lifecycle(
    packet_tail_media: Path, monkeypatch: pytest.MonkeyPatch, stop: str, audio_codec: str
) -> None:
    stream = probe_streams(packet_tail_media).audio[0]
    # Read independent timestamp facts from this small fixture. FFmpeg versions
    # differ in Opus priming/padding and stream start; CSV must agree with JSON.
    packet_probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "packet=pts_time,duration_time",
            "-of",
            "json",
            str(packet_tail_media),
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    packet_facts = cast(dict[str, list[dict[str, str]]], json.loads(packet_probe.stdout))
    latest_end = max(
        Fraction(packet["pts_time"]) + Fraction(packet["duration_time"])
        for packet in packet_facts["packets"]
    )
    expected_duration = latest_end - stream.timeline.start_time
    # ffprobe versions may derive metadata duration even for live Matroska.
    # Exercise the fallback explicitly against the real packet timestamps.
    stream = replace(
        stream,
        timeline=replace(
            stream.timeline,
            duration=None,
            duration_basis="unavailable",
            start_time=latest_end if stop == "nonpositive" else stream.timeline.start_time,
        ),
    )
    cancellation = Event()
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen

    def popen(
        argv: list[str], *, cwd: Path | None, stdout: Any, stderr: Any, shell: bool
    ) -> subprocess.Popen[bytes]:
        process = original_popen(argv, cwd=cwd, stdout=stdout, stderr=stderr, shell=shell)
        processes.append(process)
        if stop == "cancel":
            cancellation.set()
        return process

    monkeypatch.setattr(subproc, "Popen", popen)
    if stop == "cap":
        monkeypatch.setattr(alignment_audio, "_PACKET_TAIL_MAX_BYTES", 16, raising=False)
    if stop == "timeout":
        monkeypatch.setattr(alignment_audio, "_FFPROBE_TIMEOUT_SECONDS", 0.000001)
    if stop == "cancel":
        with pytest.raises(AudioAlignmentCancellationError):
            measure_selected_audio_duration(
                packet_tail_media,
                stream,
                video_seconds=Fraction(2),
                cancellation=cancellation,
            )
    else:
        measured = measure_selected_audio_duration(
            packet_tail_media,
            stream,
            video_seconds=Fraction(90 if stop == "before-seek" else 2),
            cancellation=cancellation,
        )
        if stop in {"cap", "timeout", "before-seek", "nonpositive"}:
            assert measured == stream
        else:
            assert measured.timeline.duration is not None
            assert measured.timeline.duration == expected_duration
            assert measured.timeline.duration_basis == "packet_tail"
    assert len(processes) == 1
    assert processes[0].returncode is not None
