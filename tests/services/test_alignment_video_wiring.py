"""Focused proof that computed alignment is gated by the video stage."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.services import alignment as alignment_service
from frame_compare.services import alignment_video
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkObservation,
    ChunkPlan,
    ChunkRun,
)
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.alignment_evidence import (
    VideoCheckObservation,
    VideoTargetEvidence,
    VideoTargetPosition,
)
from frame_compare.utils.types import AlignmentRequest
from frame_compare.vs.loader import VSLoader
from tests.services.alignment_request_test_support import alignment_request
from tests.services.alignment_synthetic_audio import make_program
from tests.services.test_alignment_workflow import (
    _DURATION_SECONDS,
    _media,
    _stub_transport,
)


def _observed_video(
    confirmed_offset: int,
    *,
    targets: tuple[VideoTargetEvidence, ...] = (),
) -> alignment_video.VideoCheckResult:
    return alignment_video.VideoCheckResult(
        observation=VideoCheckObservation(
            observation="observed",
            scored_offsets=tuple(range(confirmed_offset - 2, confirmed_offset + 3)),
            confirmed_offset=confirmed_offset,
            index_build_seconds=0.0,
            positions=(),
            targets=targets,
        )
    )


def _target(
    kind: str,
    first_index: int,
    last_index: int,
    resolution: str,
    *,
    chunk_samples: int = 240_000,
    credible: bool = True,
) -> VideoTargetEvidence:
    positions = (
        ()
        if resolution == "unexamined"
        else (
            VideoTargetPosition(
                position_index=0,
                reference_frame=0,
                confirmed_score=1.0,
                alternative_score=0.1 if resolution == "alternative_confirmed" else 1.0,
                winner="alternative" if resolution == "alternative_confirmed" else "neither",
                alternative_offset=1 if resolution == "alternative_confirmed" else None,
            ),
        )
    )
    return VideoTargetEvidence(
        kind=kind,  # type: ignore[arg-type]
        first_chunk_index=first_index,
        last_chunk_index=last_index,
        credible=credible,
        start_sample=first_index * chunk_samples,
        end_sample=(last_index + 1) * chunk_samples,
        target_offset=1,
        alternative_offsets=(1, 2),
        resolution=resolution,  # type: ignore[arg-type]
        positions=positions,
    )


def _fixed_estimate(plan: ChunkPlan, mode: str) -> ChunkedAudioEstimate:
    observations: list[ChunkObservation] = []
    for index, (start, count) in enumerate(plan.chunks):
        if mode == "unresolved_run":
            lag = 1600 if index >= 18 else 0
            credible = True
            agrees = index < 18
        elif mode == "unexamined_chunk":
            lag = 1600 if index == len(plan.chunks) - 1 else 0
            credible = True
            agrees = index != len(plan.chunks) - 1
        else:
            lag = 1600 if index == 19 else 0
            credible = index != 19
            agrees = credible
        observations.append(
            ChunkObservation(
                index=index,
                reference_start=start,
                reference_count=count,
                active=True,
                lag=lag,
                psr=30.0 if credible else 5.0,
                credible=credible,
                agrees=agrees,
            )
        )

    if mode == "unresolved_run":
        runs = (
            ChunkRun(first_index=0, last_index=17, lag=0, chunk_count=18),
            ChunkRun(
                first_index=18,
                last_index=19,
                lag=1600,
                chunk_count=2,
            ),
        )
        outcome = "no_single_offset"
    elif mode == "unexamined_chunk":
        runs = (
            ChunkRun(
                first_index=0,
                last_index=len(plan.chunks) - 2,
                lag=0,
                chunk_count=len(plan.chunks) - 1,
            ),
        )
        outcome = "agreed"
    else:
        runs = (
            ChunkRun(
                first_index=0,
                last_index=len(plan.chunks) - 2,
                lag=0,
                chunk_count=len(plan.chunks) - 1,
            ),
        )
        outcome = "agreed"
    return ChunkedAudioEstimate(
        outcome=outcome,  # type: ignore[arg-type]
        global_lag=0,
        observations=tuple(observations),
        runs=runs,
        active_count=len(observations),
        credible_count=sum(item.credible for item in observations),
        agreeing_count=sum(item.agrees for item in observations),
    )


class _FixedCorrelation:
    def __init__(self, plan: ChunkPlan, mode: str) -> None:
        self._estimate = _fixed_estimate(plan, mode)

    def add(self, index: int, *_args: object) -> ChunkObservation:
        return self._estimate.observations[index]

    def finish(self) -> ChunkedAudioEstimate:
        return self._estimate


def _twenty_chunk_plan(*_args: object) -> ChunkPlan:
    chunk_samples = 14_000
    return ChunkPlan(
        chunk_samples=chunk_samples,
        lag_samples=8_000,
        chunks=tuple((index * chunk_samples, chunk_samples) for index in range(20)),
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
