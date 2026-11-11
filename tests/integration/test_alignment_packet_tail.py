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


@pytest.mark.parametrize(
    ("recipe", "early_end", "comparison_origin"),
    [
        ("packet-tail", False, 0),
        ("packet-tail-early-end", True, 0),
        ("packet-tail-early-end", True, 120),
    ],
    ids=["known-offset", "audio-before-tail", "audio-before-tail-shifted"],
)
def test_live_matroska_packet_tail(
    tmp_path: Path, recipe: str, early_end: bool, comparison_origin: int
) -> None:
    vs_mod = pytest.importorskip("vapoursynth")
    if isinstance(vs_mod, MagicMock):
        pytest.skip("vapoursynth is mocked")
    if not detect_plugins(ensure_vs_environment()).get("lsmas", False):
        pytest.skip("lsmas plugin not available")
    with open_u4_media(tmp_path / "media", cache_root=None, full_matrix=False) as media:
        reference, comparison = media.pair(recipe)
        if comparison_origin:
            shifted = tmp_path / "shifted.mkv"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    comparison,
                    "-c",
                    "copy",
                    "-output_ts_offset",
                    str(comparison_origin),
                    "-live",
                    "1",
                    shifted,
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
            comparison = shifted
        for path in (reference, comparison):
            probed = probe_streams(path)
            assert probed.audio[0].timeline.duration is None
            origin = comparison_origin if path == comparison else 0
            assert probed.audio[0].timeline.start_time == probed.video_start.start_time == origin
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


def test_ffmpeg_remux_rewrites_duration_and_keeps_statistics_markers(tmp_path: Path) -> None:
    original = tmp_path / "statistics.mkv"
    remuxed = tmp_path / "remuxed.mkv"
    markers = {
        "_STATISTICS_WRITING_APP": "mkvmerge v90.0",
        "_STATISTICS_TAGS": "BPS DURATION NUMBER_OF_FRAMES NUMBER_OF_BYTES",
    }
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=32x24:rate=24:duration=120",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=8000:cl=mono:d=35",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-metadata:s:a:0",
            f"_STATISTICS_WRITING_APP={markers['_STATISTICS_WRITING_APP']}",
            "-metadata:s:a:0",
            f"_STATISTICS_TAGS={markers['_STATISTICS_TAGS']}",
            str(original),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(original),
            "-itsoffset",
            "2",
            "-i",
            str(original),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c",
            "copy",
            str(remuxed),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    for path, end in ((original, 35), (remuxed, 37)):
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream_tags:format_tags=ENCODER",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
        facts = json.loads(probe.stdout)
        tags = facts["streams"][0]["tags"]
        assert {key: tags[key] for key in markers} == markers
        assert tags["DURATION"] == f"00:00:{end}.000000000"
        format_tags = {key.lower(): value for key, value in facts["format"]["tags"].items()}
        assert format_tags["encoder"].startswith("Lavf")

    probed = probe_streams(remuxed)
    stream = probed.audio[0]
    if stream.timeline.duration is None:
        stream = measure_selected_audio_duration(
            remuxed,
            stream,
            video_seconds=Fraction(120),
            video_start=probed.video_start.start_time,
            cancellation=None,
        )
    assert stream.timeline.start_time == 2
    assert stream.timeline.duration == 35
    assert stream.timeline.duration_basis == "stream_tag"


def test_lavf_with_tag_only_statistics_measures_audio_packets(tmp_path: Path) -> None:
    path = tmp_path / "tag-edited.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=32x24:rate=1:duration=320",
            "-itsoffset",
            "2",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=8000:cl=mono:d=300",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-output_ts_offset",
            "120",
            # Under CPU load FFmpeg can write several video packets before the
            # delayed audio. The probe then copies container values into the
            # audio stream and takes the start-verification path instead of
            # the tag path this test covers. Strict interleaving fixes the layout.
            "-max_interleave_delta",
            "0",
            "-write_crc32",
            "0",
            "-metadata:s:a:0",
            "_STATISTICS_WRITING_APP=mkvpropedit v90.0",
            "-metadata:s:a:0",
            "_STATISTICS_TAGS=BPS DURATION NUMBER_OF_FRAMES NUMBER_OF_BYTES",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    # Model mkvpropedit's tag-only edit on real packets. Replace the audio
    # endpoint with the elapsed value without changing EBML sizes or muxer.
    data = path.read_bytes()
    endpoint = b"00:07:02.000000000"
    assert data.count(endpoint) == 1
    path.write_bytes(data.replace(endpoint, b"00:05:00.000000000"))

    probed = probe_streams(path)
    assert probed.video_start.start_time == 120
    stream = probed.audio[0]
    assert stream.timeline.start_time == 122
    if stream.timeline.duration is None:
        stream = measure_selected_audio_duration(
            path,
            stream,
            video_seconds=Fraction(320),
            video_start=probed.video_start.start_time,
            cancellation=None,
        )
    assert stream.timeline.duration == 300
    assert stream.timeline.duration_basis == "packet_tail"


def test_late_matroska_track_uses_packet_start_and_duration(tmp_path: Path) -> None:
    path = tmp_path / "late-audio.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=32x24:rate=24:duration=60",
            "-itsoffset",
            "15",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=8000:cl=mono:d=45",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    probed = probe_streams(path)
    stream = probed.audio[0]
    # The normal probe either sees the real start (version dependent) or must
    # withhold the apparent container duration before collection can use it.
    if stream.timeline.start_time != 15:
        assert stream.timeline.duration is None
    measured = measure_selected_audio_duration(
        path,
        stream,
        video_seconds=Fraction(60),
        video_start=probed.video_start.start_time,
        cancellation=None,
    )
    assert measured.timeline.start_time == 15
    assert measured.timeline.duration == 45


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
    probed = probe_streams(packet_tail_media)
    stream = probed.audio[0]
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
            verify_start=False,
            start_time=latest_end if stop == "nonpositive" else stream.timeline.start_time,
        ),
    )
    cancellation = Event()
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen

    def popen(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        process = cast("subprocess.Popen[bytes]", original_popen(argv, **kwargs))
        if kwargs.get("stdout") == subprocess.PIPE:
            processes.append(process)
            if stop == "cancel":
                cancellation.set()
        return process

    monkeypatch.setattr(subprocess, "Popen", popen)
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
                video_start=probed.video_start.start_time,
                cancellation=cancellation,
            )
    else:
        measured = measure_selected_audio_duration(
            packet_tail_media,
            stream,
            video_seconds=Fraction(90 if stop == "before-seek" else 2),
            video_start=probed.video_start.start_time,
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
