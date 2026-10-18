"""Real live-Matroska duration fallback and unchanged alignment authority."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_audio import probe_streams
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

vs_mod = pytest.importorskip("vapoursynth")
if isinstance(vs_mod, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)
if not detect_plugins(ensure_vs_environment()).get("lsmas", False):
    pytest.skip("lsmas plugin not available", allow_module_level=True)


@pytest.mark.parametrize("early_end", [False, True], ids=["known-offset", "audio-before-tail"])
def test_live_matroska_packet_tail(tmp_path: Path, early_end: bool) -> None:
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
