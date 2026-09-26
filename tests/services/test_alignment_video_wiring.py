"""Focused proof that computed alignment is gated by the video stage."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from frame_compare.services import alignment as alignment_service
from frame_compare.services import alignment_audio, alignment_video
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.alignment_evidence import VideoCheckObservation
from frame_compare.utils.types import AlignmentRequest
from frame_compare.vs.loader import VSLoader
from tests.services.alignment_request_test_support import alignment_request
from tests.services.alignment_synthetic_audio import insert_program, make_program
from tests.services.test_alignment_workflow import (
    _DURATION_SECONDS,
    _media,
    _selection,
    _stub_transport,
)


def _observed_video(confirmed_offset: int) -> alignment_video.VideoCheckResult:
    return alignment_video.VideoCheckResult(
        observation=VideoCheckObservation(
            observation="observed",
            scored_offsets=tuple(range(confirmed_offset - 2, confirmed_offset + 3)),
            confirmed_offset=confirmed_offset,
            index_build_seconds=0.0,
            positions=(),
        )
    )


def _run(
    request: AlignmentRequest,
    config: AlignmentConfig,
    *,
    loader: VSLoader | None = None,
) -> list[AlignmentResult]:
    return asyncio.run(
        align_clips_from_request(
            request,
            config,
            reference_fps=Fraction(24, 1),
            vs_loader=loader,
        )
    )


def test_global_audio_lag_runs_video_and_only_confirmation_applies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(11, _DURATION_SECONDS)
    _stub_transport(
        monkeypatch,
        tmp_path,
        reference_samples=program,
        comparison_samples=program,
    )
    config = AlignmentConfig(cache_results=True)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path / "generated",
    )
    loader = cast(VSLoader, object())
    seen: list[VSLoader | None] = []
    saved: list[object] = []

    def check_video(
        *, loader: VSLoader | None, **_kwargs: object
    ) -> alignment_video.VideoCheckResult:
        seen.append(loader)
        return _observed_video(0)

    monkeypatch.setattr(alignment_video, "check_video_alignment", check_video)
    monkeypatch.setattr(
        alignment_service,
        "save_reusable_offsets",
        lambda request, provenances: saved.append((request, provenances)),
    )

    (result,) = _run(request, config, loader=loader)

    assert seen == [loader]
    assert result.applied is True
    assert result.frame_offset == 0
    assert result.diagnostic == "audio_video_confirmed"
    assert result.audio_attempt is not None
    assert result.audio_attempt.video_check.observation == "observed"
    assert len(saved) == 1


def test_missing_loader_is_a_video_unavailable_provisional_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = _media(tmp_path)
    program = make_program(11, _DURATION_SECONDS)
    _stub_transport(
        monkeypatch,
        tmp_path,
        reference_samples=program,
        comparison_samples=program,
    )
    config = AlignmentConfig(cache_results=True)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path / "generated",
    )

    saved: list[object] = []
    monkeypatch.setattr(
        alignment_service,
        "save_reusable_offsets",
        lambda request, provenances: saved.append((request, provenances)),
    )

    (result,) = _run(request, config)

    assert result.applied is False
    assert result.frame_offset is None
    assert result.diagnostic == "video_check_unavailable"
    assert result.audio_attempt is not None
    assert result.audio_attempt.video_check.observation == "not_observed"
    assert saved == []


def test_raw_no_single_offset_still_runs_video_when_a_global_lag_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = _media(tmp_path)
    reference_program = make_program(11, 70.0)
    _stub_transport(
        monkeypatch,
        tmp_path,
        reference_samples=reference_program,
        comparison_samples=insert_program(11, 70.0, 999),
    )
    monkeypatch.setattr(
        alignment_audio,
        "select_reference_audio_stream",
        lambda *_args, **_kwargs: _selection(duration_seconds=70.0),
    )
    monkeypatch.setattr(
        alignment_audio,
        "select_matching_audio_stream",
        lambda *_args, **_kwargs: _selection(duration_seconds=74.0),
    )
    config = AlignmentConfig(cache_results=False)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path / "generated",
    )
    loader = cast(VSLoader, object())
    seen: list[VSLoader | None] = []

    def check_video(
        *, loader: VSLoader | None, **_kwargs: object
    ) -> alignment_video.VideoCheckResult:
        seen.append(loader)
        return _observed_video(0)

    monkeypatch.setattr(alignment_video, "check_video_alignment", check_video)

    (result,) = _run(request, config, loader=loader)

    assert seen == [loader]
    assert result.audio_attempt is not None
    assert result.audio_attempt.audio.status == "no_single_offset"
    assert result.audio_attempt.video_check.observation == "observed"
